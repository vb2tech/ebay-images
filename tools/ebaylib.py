"""Shared helpers for the eBay listing skills.

Source of truth: one listing.json next to each book's photos:
  photos/<Series>/<Series>-<issue>_<Grader>-<grade>[_<Variant>]_<cert>/listing.json
Status flow (the 'what has been uploaded' marker):
  new -> priced -> exported -> uploaded        (also: hold, sold)
  new       ingested from photos, no approved price yet
  priced    price approved by the seller (pricing.final set)
  exported  written into a bulk upload file (history has the batch id); not yet confirmed on eBay
  uploaded  seller confirmed the batch went up on eBay
"""
import csv, datetime as dt, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_BASE = "https://raw.githubusercontent.com/vb2tech/ebay-images/main"
STATUSES = ["new", "priced", "exported", "uploaded", "hold", "sold"]

# ------------------------------------------------------------------ registry / config
def registry():
    return json.load(open(os.path.join(ROOT, "templates/registry.json")))

def group(name=None):
    reg = registry()
    name = name or reg["default"]
    g = dict(reg["groups"][name]); g["name"] = name
    for k in ("template", "rules", "defaults", "fields_doc"):
        g[k + "_path"] = os.path.join(ROOT, g[k])
    g["rules_data"] = json.load(open(g["rules_path"]))
    g["defaults_data"] = json.load(open(g["defaults_path"]))
    return g

def today():
    return dt.date.today().isoformat()

# ------------------------------------------------------------------ naming (matches the repo README)
VARIANT_TAGS = [("Poly-Bagged", "Poly-Bagged"), ("Collector's Edition", "Collectors-Edition"),
                ("Newsstand", "Newsstand"), ("Virgin", "Virgin-Variant"), ("Retailer Incentive", "Retailer-Incentive"),
                ("Variant", "Variant"), ("Trade Paperback", "TPB")]

def slug(s):
    s = s.replace("&", "and").replace("'", "")
    s = re.sub(r"^The\s+", "", s)
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")

def sku_of(item):
    it = item["item"] if "item" in item else item
    return item.get("sku") or it.get("sku") or f"{it['grader']}-{it['cert']}"

def variant_tag(it):
    if it.get("variant_tag") is not None:
        return it["variant_tag"]
    hay = " ".join([it.get("title_hint", ""), "|".join(it.get("features", [])), it.get("format", "")] + it.get("key_notes", []))
    for needle, tag in VARIANT_TAGS:
        if needle.lower() in hay.lower():
            return tag
    return ""

def folder_for(item):
    it = item["item"]
    series = slug(it["series"])
    ident = it.get("cert") or sku_of(item).split("-", 1)[1]
    parts = [f"{series}-{slug(str(it['issue']))}", f"{it['grader']}-{it['grade']}"]
    v = variant_tag(it)
    if v:
        parts.append(v)
    parts.append(ident)
    return f"photos/{series}/" + "_".join(parts)

def photo_url(folder, fname):
    return f"{RAW_BASE}/{folder}/{fname}"

# ------------------------------------------------------------------ item store
def item_paths():
    return sorted(glob.glob(os.path.join(ROOT, "photos", "*", "*", "listing.json")))

def load_items(status=None, sku=None, template=None):
    out = []
    for p in item_paths():
        d = json.load(open(p))
        d["_path"] = p
        d["_folder"] = os.path.relpath(os.path.dirname(p), ROOT)
        if status and d.get("status") not in (status if isinstance(status, (list, tuple, set)) else [status]):
            continue
        if sku and d.get("sku") not in (sku if isinstance(sku, (list, tuple, set)) else [sku]):
            continue
        if template and d.get("template") != template:
            continue
        out.append(d)
    return out

def save_item(d):
    p = d.get("_path") or os.path.join(ROOT, folder_for(d), "listing.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    clean = {k: v for k, v in d.items() if not k.startswith("_")}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=1, ensure_ascii=False)
        f.write("\n")
    d["_path"] = p
    return p

def log(d, event, **kw):
    d.setdefault("history", []).append({"date": today(), "event": event, **kw})

def photos_of(d):
    folder = d.get("_folder") or folder_for(d)
    files = d.get("photos") or sorted(f for f in os.listdir(os.path.join(ROOT, folder)) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    num = lambda f: int(m.group(1)) if (m := re.search(r"-(\d+)\.\w+$", f)) else 0
    return [photo_url(folder, f) for f in sorted(files, key=num)]

# ------------------------------------------------------------------ index + README table
def rebuild_index():
    rows = []
    have = {d["_folder"] + "/" for d in load_items()}
    idx = os.path.join(ROOT, "index.csv")
    if os.path.exists(idx):  # keep books that don't have a listing.json yet
        for r in csv.DictReader(open(idx, encoding="utf-8")):
            if r.get("folder") and r["folder"] not in have and os.path.isdir(os.path.join(ROOT, r["folder"])):
                rows.append({"series": r["series"], "issue": r["issue"], "grader": r["grader"], "grade": r["grade"],
                             "cert": r["cert"], "sku": r["sku"], "ebay_title": r.get("ebay_title", ""),
                             "status": r.get("status") or "legacy", "price": r.get("price", ""), "folder": r["folder"]})
    for d in load_items():
        it = d["item"]
        rows.append({"series": it["series"], "issue": it["issue"], "grader": it["grader"], "grade": it["grade"],
                     "cert": it.get("cert") or "(unreadable)", "sku": d["sku"], "ebay_title": d.get("listing", {}).get("title", ""),
                     "status": d.get("status", ""), "price": (d.get("pricing") or {}).get("final") or "",
                     "folder": d["_folder"] + "/"})
    rows.sort(key=lambda r: (r["series"], str(r["issue"]), str(r["grade"])))
    with open(os.path.join(ROOT, "index.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["sku"])
        w.writeheader(); w.writerows(rows)
    readme = os.path.join(ROOT, "README.md")
    if os.path.exists(readme):
        txt = open(readme, encoding="utf-8").read()
        table = ["| Series | Issue | Grade | Cert | Status | Folder |", "|---|---|---|---|---|---|"]
        for r in rows:
            name = r["folder"].rstrip("/").split("/")[-1]
            table.append(f"| {r['series']} | {r['issue']} | {r['grader']} {r['grade']} | {r['cert']} | {r['status']} | [{name}]({r['folder']}) |")
        txt = re.sub(r"## Books \(\d+\)\n\n(\|.*\n)+", f"## Books ({len(rows)})\n\n" + "\n".join(table) + "\n", txt)
        open(readme, "w", encoding="utf-8").write(txt)
    return len(rows)

# ------------------------------------------------------------------ listing text
def money(x):
    return f"{float(x):.2f}"

def build_title(d):
    t = d.get("listing", {}).get("title")
    if t:
        return t
    it = d["item"]
    s = re.sub(r"^The\s+", "", it["series"])
    parts = [f"{s} #{it['issue']}", f"{it['grader']} {it['grade']}"]
    for k in it.get("key_notes", [])[:2]:
        parts.append(k)
    parts.append(str(it.get("year", "")))
    t = " ".join(p for p in parts if p)
    return t[:80].rsplit(" ", 1)[0] if len(t) > 80 else t

def build_description(d, footer):
    import html
    e = html.escape
    it = d["item"]
    keys = "".join(f"<li>{e(k)}</li>" for k in it.get("key_notes", []))
    pages = f" &nbsp; <b>Page quality:</b> {e(it['pages'])} Pages" if it.get("pages") else ""
    return (f"<h2>{e(it['series'])} #{e(str(it['issue']))} &ndash; {e(it['grader'])} {e(str(it['grade']))}</h2>"
            f"<p><b>Publisher:</b> {e(it.get('publisher',''))} &nbsp; <b>Cover date:</b> {e(it.get('cover_date',''))}{pages}</p>"
            + (f"<p><b>Certification #:</b> {e(it['cert'])}</p>" if it.get("cert") else "")
            + (f"<p><b>Credits:</b> {e(it['credits'])}</p>" if it.get("credits") else "")
            + (f"<ul>{keys}</ul>" if keys else "")
            + f"<p>{e(footer)}</p>")
