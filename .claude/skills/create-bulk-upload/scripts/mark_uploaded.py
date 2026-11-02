#!/usr/bin/env python3
"""Record that an exported batch went up on eBay.

Usage (from the repo root):
  python3 -I .claude/skills/create-bulk-upload/scripts/mark_uploaded.py --batch <batch> [--results ebay_results.csv] [--failed SKU ...]

Without --results, every item in the batch becomes 'uploaded' except any --failed SKUs (which go back to 'priced'
so the next build picks them up). With eBay's upload results file (Seller Hub > Reports > Uploads > download results),
rows whose status/result column mentions failure/error go back to 'priced' with the error saved in history.
"""
import argparse, csv, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../tools"))
import ebaylib as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--results")
    ap.add_argument("--failed", nargs="*", default=[])
    a = ap.parse_args()
    man = json.load(open(os.path.join(L.ROOT, "uploads", a.batch, "manifest.json")))
    failed = {s: "marked failed by seller" for s in a.failed}
    if a.results:
        with open(a.results, newline="", encoding="utf-8-sig") as f:
            rows = [r for r in csv.reader(f)]
        # eBay's results file names the column "CustomLabel"; templates say "Custom label (SKU)".
        norm = lambda c: c.lower().replace(" ", "").replace("_", "")
        hi = next(i for i, r in enumerate(rows) if any("sku" in norm(c) or "customlabel" in norm(c) for c in r))
        h = [c.lower() for c in rows[hi]]
        sk = next(i for i, c in enumerate(h) if "sku" in norm(c) or "customlabel" in norm(c))
        st = [i for i, c in enumerate(h) if any(w in c for w in ("status", "result", "error", "message"))]
        for r in rows[hi + 1:]:
            if len(r) > sk and r[sk]:
                txt = " ".join(r[i] for i in st if i < len(r))
                if any(w in txt.lower() for w in ("fail", "error")):
                    failed[r[sk]] = txt.strip()[:300]
    by = {d["sku"]: d for d in L.load_items()}
    up, back = [], []
    for it in man["items"]:
        d = by.get(it["sku"])
        if not d:
            continue
        if it["sku"] in failed:
            d["status"] = "priced"; L.log(d, "upload_failed", batch=a.batch, reason=failed[it["sku"]]); back.append(it["sku"])
        else:
            d["status"] = "uploaded"; L.log(d, "uploaded", batch=a.batch); up.append(it["sku"])
        L.save_item(d)
    man["uploaded"] = up; man["failed"] = back; man["confirmed_at"] = L.today()
    json.dump(man, open(os.path.join(L.ROOT, "uploads", a.batch, "manifest.json"), "w"), indent=1)
    L.rebuild_index()
    print(f"{len(up)} uploaded, {len(back)} sent back to 'priced'" + (": " + ", ".join(back) if back else ""))


if __name__ == "__main__":
    main()
