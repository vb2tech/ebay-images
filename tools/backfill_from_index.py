#!/usr/bin/env python3
"""One-time: give every book that predates listing.json a minimal listing.json, built from index.csv.

Usage (repo root): python3 -I tools/backfill_from_index.py --status uploaded|priced|new [--price-from books.json]
Only identity + title + photos are filled; richer fields (characters, creators, era...) come from books.json
when --price-from points at the old project file, otherwise they stay empty and the validator will say so.
"""
import argparse, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ebaylib as L  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--status", required=True, choices=L.STATUSES)
ap.add_argument("--price-from")
a = ap.parse_args()
old = {}
if a.price_from:
    for b in json.load(open(a.price_from)):
        old[b.get("sku") or f"{b['grader']}-{b['cert']}"] = b
n = 0
for r in csv.DictReader(open(os.path.join(L.ROOT, "index.csv"), encoding="utf-8")):
    folder = r["folder"].rstrip("/")
    p = os.path.join(L.ROOT, folder, "listing.json")
    if os.path.exists(p):
        continue
    b = old.get(r["sku"], {})
    item = {"series": r["series"], "issue": r["issue"], "grader": r["grader"], "grade": r["grade"],
            "cert": "" if r["cert"].startswith("(") else r["cert"]}
    for k in ("publisher", "year", "cover_date", "pages", "era", "writer", "artist", "cover_artist", "credits", "key_notes", "format"):
        if b.get(k):
            item[k] = b[k]
    if b.get("character"):
        item["characters"] = b["character"].split("|")
    if b.get("features"):
        item["features"] = [x for x in b["features"].split("|") if x]
    files = sorted(f for f in os.listdir(os.path.join(L.ROOT, folder)) if f.lower().endswith(".jpg"))
    d = {"sku": r["sku"], "template": "comics-259104", "status": a.status, "lot": "pre-2026-11 backfill", "item": item,
         "listing": {"title": r["ebay_title"]}, "photos": files,
         "pricing": ({"final": float(b["price"]), "basis": b.get("comp", "")} if b.get("price") else {}),
         "needs_review": [] if item["cert"] else ["cert: unreadable on label"], "_path": p}
    L.log(d, "backfilled", status=a.status)
    L.save_item(d); n += 1
L.rebuild_index()
print(f"Backfilled {n} books as '{a.status}'.")
