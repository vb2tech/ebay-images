#!/usr/bin/env python3
"""Photo-to-listing check: proves every photo shows the slab its listing names.

Why: in Nov 2026, 20 of 110 photos sat in the wrong item's folder (a Punisher #77 behind the
Spider-Man 2099 9.8 link, etc.). File names can't catch that; only reading the slab label can.

How it works
  * Claude reads the label in each photo (title, issue, grade, cert) and records the read with `record`.
  * The read is saved in that item's listing.json under "photo_checks", keyed by file name, together
    with a picture fingerprint (256-bit difference hash). A read counts only while the file still
    looks like the picture that was read. Brightening or re-compressing keeps the fingerprint within
    a few bits; a different slab is 22+ bits away (calibrated on the repo: edits <= 12, different
    slabs >= 22), so FP_SAME = 14.
  * A read matches when its cert equals the listing's cert. If the cert is unreadable, the series,
    issue and grade must all match (accepted, flagged as 'match-no-cert').
  * The validator (validate.py --repo) calls row_issues() for every row, so a build fails if any photo
    is unverified, changed since it was verified, shows another slab, or is the same picture as a
    photo in another listing.

Commands (from the repo root)
  python3 -I .claude/skills/bulk-upload-validator/scripts/photo_check.py pending [--sku S ...] [--status priced ...] [--out worklist.json]
      Photos that still need a label read (never read, changed since, or last read didn't match).
  python3 -I .claude/skills/bulk-upload-validator/scripts/photo_check.py record reads.jsonl
      Save label reads. One JSON object per line:
      {"path": "photos/.../CGC-123-1.jpg", "title": "Spider-Man 2099", "issue": "1", "grade": "9.8", "cert": "4402325015", "notes": ""}
      cert may be "UNREADABLE". Exit 1 if any read shows a different slab (those are listed and
      added to the item's needs_review).
  python3 -I .claude/skills/bulk-upload-validator/scripts/photo_check.py audit [--sku S ...] [--status ...]
      Report for every listed photo: verified / unverified / changed / mismatch, plus duplicate pictures.
      Exit 1 on any problem.
"""
import argparse, datetime as dt, glob, json, os, re, sys

FP_SAME = 14          # max differing bits for "same picture"
FP_REPEAT = 2         # within one listing: two shots of the same slab differ by ~5; <= 2 is the same file repeated
FP_SIZE = 16          # 16x16 difference hash = 256 bits
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))


# ----------------------------------------------------------------------------- fingerprint
def fingerprint(path):
    from PIL import Image, ImageOps
    im = ImageOps.grayscale(Image.open(path)).resize((FP_SIZE + 1, FP_SIZE), Image.LANCZOS)
    w = FP_SIZE + 1
    px = im.tobytes()
    bits = 0
    for r in range(FP_SIZE):
        for c in range(FP_SIZE):
            if px[r * w + c] > px[r * w + c + 1]:
                bits |= 1 << (r * FP_SIZE + c)
    return f"{bits:064x}"


def distance(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ----------------------------------------------------------------------------- listings
def load_listing(folder):
    p = os.path.join(folder, "listing.json")
    if not os.path.isfile(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    d["_path"] = p
    return d


def save_listing(d):
    clean = {k: v for k, v in d.items() if not k.startswith("_")}
    with open(d["_path"], "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=1, ensure_ascii=False)
        f.write("\n")


def all_listings(root=ROOT, skus=None, statuses=None):
    out = []
    for p in sorted(glob.glob(os.path.join(root, "photos/*/*/listing.json"))):
        d = load_listing(os.path.dirname(p))
        if skus and d.get("sku") not in skus:
            continue
        if statuses and d.get("status") not in statuses:
            continue
        out.append(d)
    return out


def listed_photos(d):
    folder = os.path.dirname(d["_path"])
    names = d.get("photos") or sorted(f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    return [os.path.join(folder, n) for n in names]


# ----------------------------------------------------------------------------- matching
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower().replace("&", "and"))


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))


def compare(read, item):
    """-> (result, reason). result: match | match-no-cert | mismatch"""
    want_cert = _digits(item.get("cert"))
    got_cert = _digits(read.get("cert"))
    grade_ok = _digits(read.get("grade")) == _digits(item.get("grade"))
    if got_cert and len(got_cert) >= 6:
        if got_cert == want_cert:
            return ("match", "") if grade_ok or not read.get("grade") else \
                ("mismatch", f"cert matches but label grade {read.get('grade')} != listing {item.get('grade')}")
        return "mismatch", f"label cert {read.get('cert')} != listing cert {item.get('cert')}"
    series_ok = _norm(item.get("series")) in _norm(read.get("title")) or _norm(read.get("title")) in _norm(item.get("series"))
    issue_ok = _norm(read.get("issue")) == _norm(item.get("issue")) if read.get("issue") else True
    if series_ok and issue_ok and grade_ok:
        return "match-no-cert", "cert unreadable; series, issue and grade match"
    return "mismatch", (f"label shows {read.get('title')} #{read.get('issue')} {read.get('grade')}, "
                        f"listing is {item.get('series')} #{item.get('issue')} {item.get('grade')}")


def photo_state(d, path, fp=None):
    """-> (state, detail). state: verified | unverified | changed | mismatch"""
    chk = (d.get("photo_checks") or {}).get(os.path.basename(path))
    if not chk:
        return "unverified", "no label read recorded"
    fp = fp or fingerprint(path)
    dist = distance(fp, chk["fp"])
    if dist > FP_SAME:
        return "changed", f"file changed since its label was read on {chk.get('date')} ({dist} bits)"
    if chk.get("result") == "mismatch":
        return "mismatch", chk.get("reason") or "label read didn't match the listing"
    return "verified", chk.get("result")


# ----------------------------------------------------------------------------- validator hook
_FP_INDEX = None


def _fp_index(root):
    """fingerprint of every listed photo in the repo -> [(sku, path)] (built once per run)."""
    global _FP_INDEX
    if _FP_INDEX is None:
        _FP_INDEX = []
        for d in all_listings(root):
            for p in listed_photos(d):
                if os.path.isfile(p):
                    _FP_INDEX.append((d.get("sku"), p, fingerprint(p)))
    return _FP_INDEX


def row_issues(repo, sku, local_paths, strict=True):
    """Problems for one upload row's photos -> [(severity, message, fix)]."""
    out = []
    sev_unv = "ERROR" if strict else "WARNING"
    seen = {}
    for p in local_paths:
        if not os.path.isfile(p):
            continue
        d = load_listing(os.path.dirname(p))
        fn = os.path.basename(p)
        if d is None:
            out.append((sev_unv, f"{fn}: no listing.json next to the photo, so it can't be checked.", ""))
            continue
        if sku and d.get("sku") != sku:
            out.append(("ERROR", f"{fn} lives in the folder of {d.get('sku')}, not {sku}.", "Link this listing's own photos."))
        fp = fingerprint(p)
        state, detail = photo_state(d, p, fp)
        if state == "mismatch":
            out.append(("ERROR", f"{fn} shows a different slab: {detail}.",
                        "Put the right photo at this path (keep the path), then re-read it with photo_check.py record."))
        elif state in ("unverified", "changed"):
            out.append((sev_unv, f"{fn}: photo not verified against its label ({detail}).",
                        "Run photo_check.py pending, read the labels, then photo_check.py record."))
        for other_fn, other_fp in seen.items():
            if distance(fp, other_fp) <= FP_REPEAT:
                out.append(("WARNING", f"{fn} is the same picture as {other_fn} in this listing.", "Drop the repeat from listing.json 'photos'."))
        seen[fn] = fp
        for osku, op, ofp in _fp_index(repo):
            if osku != (d.get("sku")) and distance(fp, ofp) <= FP_SAME:
                out.append(("ERROR", f"{fn} is the same picture as {os.path.relpath(op, repo)} ({osku}).",
                            "One of the two shows the wrong slab: read both labels and fix the misplaced file."))
    return out


# ----------------------------------------------------------------------------- commands
def cmd_pending(a):
    work = []
    for d in all_listings(ROOT, a.sku, a.status):
        it = d.get("item", {})
        for p in listed_photos(d):
            if not os.path.isfile(p):
                continue
            state, detail = photo_state(d, p)
            if state != "verified":
                work.append({"path": os.path.relpath(p, ROOT), "sku": d.get("sku"), "state": state, "detail": detail,
                             "expect": {k: it.get(k) for k in ("series", "issue", "grade", "cert")}})
    if a.out:
        json.dump(work, open(a.out, "w"), indent=1)
    for w in work:
        print(f"{w['state']:<10} {w['path']}")
    print(f"{len(work)} photo(s) need a label read" + (f" -> {a.out}" if a.out else ""))


def cmd_record(a):
    today = dt.date.today().isoformat()
    bad = 0
    for line in open(a.reads, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        path = r["path"]
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        d = load_listing(os.path.dirname(path))
        if d is None:
            print(f"SKIP     {path}: no listing.json"); continue
        result, reason = compare(r, d.get("item", {}))
        d.setdefault("photo_checks", {})[os.path.basename(path)] = {
            "fp": fingerprint(path), "date": today, "method": a.method, "result": result, "reason": reason,
            "label": {k: r.get(k, "") for k in ("title", "issue", "grade", "cert")}}
        if result == "mismatch":
            bad += 1
            flag = f"photo {os.path.basename(path)} shows another slab: {reason}"
            if flag not in d.setdefault("needs_review", []):
                d["needs_review"].append(flag)
        save_listing(d)
        print(f"{result.upper():<14} {os.path.relpath(path, ROOT)}  {reason}")
    print(f"{bad} mismatch(es)")
    return 1 if bad else 0


def cmd_audit(a):
    problems = 0
    counts = {}
    listings = all_listings(ROOT, a.sku, a.status)
    for d in listings:
        paths = [p for p in listed_photos(d) if os.path.isfile(p)]
        for p in listed_photos(d):
            if not os.path.isfile(p):
                problems += 1; print(f"MISSING    {os.path.relpath(p, ROOT)}")
        for p in paths:
            state, detail = photo_state(d, p)
            counts[state] = counts.get(state, 0) + 1
            if state != "verified":
                problems += 1; print(f"{state.upper():<10} {os.path.relpath(p, ROOT)}  {detail}")
        for sev, msg, _ in row_issues(ROOT, d.get("sku"), paths):
            if "not verified" in msg or "shows a different slab" in msg:
                continue  # already printed above
            problems += sev == "ERROR"
            print(f"{sev:<10} {d.get('sku')}: {msg}")
    print(f"{len(listings)} listings: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + f"; {problems} problem(s)")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pending", "audit"):
        s = sub.add_parser(name)
        s.add_argument("--sku", nargs="*")
        s.add_argument("--status", nargs="*")
        if name == "pending":
            s.add_argument("--out")
    s = sub.add_parser("record")
    s.add_argument("reads")
    s.add_argument("--method", default="label-read")
    a = ap.parse_args()
    return {"pending": cmd_pending, "record": cmd_record, "audit": cmd_audit}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
