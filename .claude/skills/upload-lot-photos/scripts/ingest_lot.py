#!/usr/bin/env python3
"""Put a lot of item photos into the repo, one folder per item, with a listing.json beside them.

Usage (from the repo root):
  python3 -I .claude/skills/upload-lot-photos/scripts/ingest_lot.py lot.json [--group comics-259104] [--lot NAME] [--dry-run]

lot.json is written by Claude after looking at the photos:
[
  {
    "photos": ["/abs/path/IMG_0412.jpg", "/abs/path/IMG_0413.jpg"],     # front first
    "item": {"series": "Icon", "issue": "1", "publisher": "DC / Milestone", "year": "1993",
             "cover_date": "5/93", "grader": "CGC", "grade": "9.2", "pages": "White",
             "cert": "4402325019", "format": "Single Issue", "era": "Modern Age (1992-Now)",
             "characters": ["Icon", "Rocket"], "writer": "...", "artist": "...", "cover_artist": "...",
             "credits": "...", "key_notes": ["..."], "features": ["Key Issue"], "variant_tag": null},
    "listing": {"title": "<= 80 chars"},
    "needs_review": ["cert: label blurry"]                                  # anything not read with confidence
  }
]
Photos are converted to .jpg (HEIC/PNG/WEBP too), long side capped at 2000px, EXIF orientation applied,
and named <SKU>-<n>.jpg in photos/<Series>/<Series>-<issue>_<Grader>-<grade>[_<Variant>]_<cert>/.
An item already in the repo (same SKU) gets the new photos appended, not overwritten.
"""
import argparse, json, os, re, shutil, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../tools"))
import ebaylib as L  # noqa: E402

try:
    from PIL import Image, ImageOps
    try:
        import pillow_heif  # noqa: F401
        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001
        pass
except ImportError:
    Image = None

REQUIRED_ITEM = ["series", "issue", "grader", "grade", "publisher", "year", "era", "format", "characters"]


def to_jpg(src, dst):
    if Image is None:
        if not src.lower().endswith((".jpg", ".jpeg")):
            sys.exit("Pillow is needed to convert non-JPEG photos: pip install pillow pillow-heif --break-system-packages")
        shutil.copyfile(src, dst); return
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if max(im.size) > 2000:
        im.thumbnail((2000, 2000))
    im.save(dst, "JPEG", quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lot")
    ap.add_argument("--group")
    ap.add_argument("--lot-name", "--lot", dest="lot_name")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    G = L.group(a.group)
    rules = G["rules_data"]
    grades = None
    try:
        from python_calamine import CalamineWorkbook
        for r in CalamineWorkbook.from_path(G["template_path"]).get_sheet_by_name("Aspects").to_python(skip_empty_area=False):
            if len(r) > 5 and r[1] == "C:Grade":
                grades = {str(v).split(" ")[0] for v in r[5:] if v}
    except Exception:  # noqa: BLE001
        pass

    lot = json.load(open(a.lot))
    lot_name = a.lot_name or f"lot-{L.today()}"
    existing = {d["sku"]: d for d in L.load_items()}
    summary, problems = [], []
    seen = set()
    for n, e in enumerate(lot, 1):
        it = e["item"]
        it["grade"] = str(it["grade"])
        if it.get("cert"):
            it["cert"] = str(it["cert"]).replace(" ", "")
        sku = e.get("sku") or (f"{it['grader']}-{it['cert']}" if it.get("cert")
                               else f"{it['grader']}-{L.slug(it['series']).upper()}{it['issue']}-{it['grade']}")
        gaps = [k for k in REQUIRED_ITEM if not it.get(k)]
        review = list(e.get("needs_review", []))
        if not it.get("cert"):
            review.append("cert: not read; SKU uses a placeholder, fix before upload")
        if grades and it["grade"].rstrip("0").rstrip(".") not in {g.rstrip("0").rstrip(".") for g in grades}:
            problems.append(f"#{n} {sku}: grade {it['grade']} isn't an eBay grade value")
        title = (e.get("listing") or {}).get("title", "")
        if len(title) > 80:
            problems.append(f"#{n} {sku}: title is {len(title)} chars (max 80)")
        if sku in seen:
            problems.append(f"#{n} {sku}: appears twice in this lot")
        seen.add(sku)
        missing_files = [p for p in e["photos"] if not os.path.isfile(p)]
        if missing_files:
            problems.append(f"#{n} {sku}: photo not found: {', '.join(missing_files)}")
            continue

        if sku in existing:
            d = existing[sku]
            folder = d["_folder"]
            action = "added photos to existing item"
        else:
            d = {"sku": sku, "template": G["name"], "status": "new", "lot": lot_name, "item": it,
                 "listing": e.get("listing") or {}, "photos": [], "pricing": {}, "needs_review": review}
            d["listing"].setdefault("title", L.build_title(d))
            folder = L.folder_for(d)
            d["_path"] = os.path.join(L.ROOT, folder, "listing.json")
            action = "new item"
            L.log(d, "ingested", lot=lot_name)
        start = len(d.get("photos") or [])
        names = [f"{sku}-{start + i + 1}.jpg" for i in range(len(e["photos"]))]
        if not a.dry_run:
            os.makedirs(os.path.join(L.ROOT, folder), exist_ok=True)
            for src, nm in zip(e["photos"], names):
                to_jpg(src, os.path.join(L.ROOT, folder, nm))
            d["photos"] = (d.get("photos") or []) + names
            L.save_item(d)
        summary.append({"#": n, "sku": sku, "folder": folder, "photos": len(names), "action": action,
                        "gaps": gaps, "needs_review": review})

    if not a.dry_run and summary:
        L.rebuild_index()
    print(json.dumps({"lot": lot_name, "items": summary, "problems": problems}, indent=1))
    std_aspects = [k for k, r in rules["fields"].items() if r.get("tier") == "standard"]
    print(f"\nProject standard for {G['name']} needs: {', '.join(std_aspects)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
