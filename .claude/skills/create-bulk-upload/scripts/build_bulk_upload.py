#!/usr/bin/env python3
"""Build an eBay bulk upload .xlsx from items in the repo, validate it, and mark the items exported.

Usage (from the repo root):
  python3 -I .claude/skills/create-bulk-upload/scripts/build_bulk_upload.py
        [--group comics-259104] [--status priced] [--sku SKU ...] [--batch NAME]
        [--action Draft|Add] [--location "City, ST"] [--dry-run] [--allow-warnings]

Picks items whose listing.json has status 'priced' (approved price, never exported) unless --sku is given.
Writes uploads/<batch>/<batch>.xlsx + validation.md + validation.json + manifest.json.
With action Draft it also writes uploads/<batch>/<batch>_drafts.csv in eBay's drafts layout (first line
'#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US'): eBay's category template rejects Draft
(BAF.Error.5), so the CSV is the file to upload; the .xlsx stays as the validated source of the same rows.
Only when the strict validation passes (no errors) are the items marked 'exported' (skip with --dry-run).
Exit code: 0 ok, 1 validation failed, 3 nothing to build.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, tempfile, zipfile, io

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../tools"))
import ebaylib as L  # noqa: E402
from python_calamine import CalamineWorkbook  # noqa: E402

VALIDATOR = os.path.join(L.ROOT, ".claude/skills/bulk-upload-validator/scripts/validate.py")


def col_letter(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s


DRAFT_INFO = [
    "#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US",
    "#INFO Action and Category ID are required fields. Set Action to Draft.",
    "#INFO After the upload, finish the drafts at https://www.ebay.com/sh/lst/drafts",
]
DRAFT_ACTION = "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)"
# eBay's drafts file wants the condition as a word, not the numeric Condition ID.
DRAFT_CONDITION = {"1000": "NEW", "1500": "NEW_OTHER", "2750": "LIKE_NEW", "3000": "USED_EXCELLENT",
                   "4000": "USED_VERY_GOOD", "5000": "USED_GOOD", "6000": "USED_ACCEPTABLE"}


def write_drafts_csv(path, rows, cols):
    """rows: the same dicts that fill the .xlsx; cols: the C: item-specific columns in use."""
    import csv
    base = ["Custom label (SKU)", "Category ID", "Title", "Price", "Quantity", "Item photo URL", "Condition ID",
            "Description", "Format", "Duration", "Best Offer Enabled", "Location",
            "Shipping profile name", "Return profile name", "Payment profile name"]
    used = [c for c in base + cols if any(_plain(r.get(_src(c))) not in ("", None) for r in rows)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        for line in DRAFT_INFO:
            f.write(line + "\r\n")
        w = csv.writer(f)
        w.writerow([DRAFT_ACTION] + used)
        for r in rows:
            out = []
            for c in used:
                v = _plain(r.get(_src(c)))
                if c == "Condition ID":
                    v = DRAFT_CONDITION.get(str(v).split("-")[0], v)
                out.append("" if v is None else v)
            w.writerow(["Draft"] + out)


def _src(c):
    return "Start price" if c == "Price" else c


def _plain(v):
    return v[0] if isinstance(v, tuple) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group")
    ap.add_argument("--status", default="priced")
    ap.add_argument("--sku", nargs="*")
    ap.add_argument("--batch")
    ap.add_argument("--action")
    ap.add_argument("--location")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-warnings", action="store_true", help="kept for clarity; warnings never block")
    a = ap.parse_args()

    G = L.group(a.group)
    D = G["defaults_data"]
    items = L.load_items(sku=a.sku) if a.sku else L.load_items(status=a.status)
    items = [d for d in items if d.get("template", G["name"]) == G["name"]]
    if not items:
        print(f"Nothing to build: no items with status '{a.status}' in group {G['name']}.")
        sys.exit(3)
    missing_price = [d["sku"] for d in items if not (d.get("pricing") or {}).get("final")]
    if missing_price:
        print("These items have no approved price (pricing.final); run the pricing-proposal skill first:\n  " + "\n  ".join(missing_price))
        sys.exit(1)

    batch = a.batch or f"{L.today()}_{G['name']}_{len(items)}"
    outdir = os.path.join(L.ROOT, "uploads", batch)
    os.makedirs(outdir, exist_ok=True)
    out_xlsx = os.path.join(outdir, f"{batch}.xlsx")

    # ---- lookups from the template
    wb = CalamineWorkbook.from_path(G["template_path"])
    hdr = [str(h) for h in wb.get_sheet_by_name("Listings").to_python(skip_empty_area=False)[3]]
    hdr = [h for h in hdr if h]
    pol = [r for r in wb.get_sheet_by_name("BusinessPolicy").to_python()[1:]]
    asp = {}
    for r in wb.get_sheet_by_name("Aspects").to_python(skip_empty_area=False):
        if len(r) > 5 and str(r[1]).startswith("C:") and str(r[0]).isdigit():
            asp[str(r[1])] = [str(v) for v in r[5:] if v not in ("", None)]

    def pick(field, v):
        for x in asp.get(field, []):
            if x.lower() == str(v).lower():
                return x
        return None

    ship = next((r[0] for r in pol if r[0] and D["shipping"]["profile_contains"] in r[0]), "")
    ret = next((r[1] for r in pol if r[1] and r[1].startswith(D["return_profile_startswith"])), "")
    pay = next((r[2] for r in pol if r[2] and D["payment_profile_contains"] in r[2]), "")
    action = a.action or D["action"]
    location = a.location if a.location is not None else D.get("location", "")

    ext_cols = []
    if D.get("include_extension_aspects"):
        ext_cols = [k for k, r in G["rules_data"]["fields"].items() if r.get("tier") == "extension"]
    header = hdr + [c for c in ext_cols if c not in hdr]
    COL = {h: col_letter(i) for i, h in enumerate(header)}
    key = {h: ("Action" if "Action(" in h else h) for h in header}

    def grade_txt(g):
        g = str(g)
        g = "10" if g in ("10", "10.0") else g
        return next((x for x in asp["C:Grade"] if x.split(" ")[0] == g), g)

    def condition(g):
        g = float(g)
        return next(c for lo, c in D["condition_from_grade"] if g >= lo)

    def people(*names):
        out = []
        for n in names:
            for p in re.split(r"\s*(?:&|,| and )\s*", n or ""):
                p = p.strip()
                if p and p not in out:
                    out.append(p)
        return "|".join(out)

    rows, manifest = [], []
    for d in items:
        it = d["item"]
        fmt = it.get("format", "Single Issue")
        tpb = fmt == "Trade Paperback"
        series = D["series_aliases"].get(it["series"]) or pick("C:Series Title", it["series"]) \
            or pick("C:Series Title", re.sub(r"^The ", "", it["series"])) or it["series"]
        chars = it.get("characters") or []
        v = {
            "Action": action, "Custom label (SKU)": d["sku"], "Category name": D["category_name"],
            "Category ID": D["category_id"], "Title": L.build_title(d),
            "Start price": (L.money(d["pricing"]["final"]), True), "Quantity": (D["quantity"], True),
            "Item photo URL": "|".join(L.photos_of(d)),
            "Condition ID": condition(it["grade"]),
            "Description": d.get("listing", {}).get("description") or L.build_description(d, D["description_footer"]),
            "Format": D["format"], "Duration": D["duration"], "Best Offer Enabled": (D["best_offer_enabled"], True),
            "Location": location,
            "Shipping profile name": ship, "Return profile name": ret, "Payment profile name": pay,
            "C:Series Title": series, "C:Character": "|".join(chars) if isinstance(chars, list) else chars,
            "C:Genre": it.get("genre") or D["genre"],
            "C:Artist/Writer": people(it.get("writer"), it.get("artist"), it.get("cover_artist")),
            "C:Publisher": D["publisher_names"].get(it.get("publisher"), it.get("publisher", "")),
            "C:Superhero Team": it.get("team") or D["team_series"].get(it["series"], ""),
            "C:Publication Year": str(it.get("year", "")),
            "C:Format": "Trade Paperback" if tpb else "Single Issue",
            "C:Era": it.get("era", ""), "C:Type": "Graphic Novel" if tpb else "Comic Book",
            "C:Grade": grade_txt(it["grade"]), "C:Tradition": D["tradition"],
            "C:Professional Grader": D["grader_names"].get(it["grader"], it["grader"]),
            "C:Certification Number": it.get("cert", ""),
            # extension aspects (only written when include_extension_aspects is on)
            "C:Issue Number": str(it.get("issue", "")), "C:Features": "|".join(it.get("features", [])),
            "C:Cover Artist": people(it.get("cover_artist")), "C:Language": "English", "C:Signed": "No",
            "C:Unit of Sale": "Single Unit", "C:Vintage": "Yes" if str(it.get("year", "9999")) < "1992" else "No",
        }
        if not ship:
            fb = D["shipping"]["fallback_legacy"]
            v.update({"Shipping profile name": "", "Shipping service 1 option": fb["service"],
                      "Shipping service 1 cost": (L.money(fb["cost"]), True),
                      "Shipping service 1 priority": (fb["priority"], True), "Max dispatch time": (fb["max_dispatch"], True)})
        rows.append(v)
        manifest.append({"sku": d["sku"], "title": v["Title"], "price": d["pricing"]["final"], "folder": d["_folder"]})

    # ---- write the sheet XML into a copy of the template (openpyxl can't open eBay's styles)
    work = tempfile.mkdtemp()
    zin = zipfile.ZipFile(G["template_path"])
    zin.extractall(work)
    sp = os.path.join(work, "xl/worksheets/sheet3.xml")
    s = open(sp, encoding="utf-8").read()
    colstyle = {}
    for m in re.finditer(r'<col min="(\d+)" max="(\d+)"[^>]*?(?:style="(\d+)")?[^>]*/>', s[:s.index("</cols>")]):
        if m.group(3):
            for c in range(int(m.group(1)), int(m.group(2)) + 1):
                colstyle[col_letter(c - 1)] = m.group(3)

    def cell(ref, val, num=False):
        col = re.match(r"[A-Z]+", ref).group(0)
        st = f' s="{colstyle[col]}"' if col in colstyle else ""
        if num:
            return f'<c r="{ref}"{st} t="n"><v>{val}</v></c>'
        return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{html.escape(str(val), quote=False)}</t></is></c>'

    # extension headers
    if len(header) > len(hdr):
        extra = "".join(cell(f"{COL[h]}4", h) for h in header[len(hdr):])
        s = re.sub(r'(<row r="4"[^>]*>.*?)(</row>)', lambda m: m.group(1) + extra + m.group(2), s, count=1, flags=re.S)
    for i, v in enumerate(rows):
        n = 5 + i
        cells = []
        for h in header:
            k, ref = key[h], f"{COL[h]}{n}"
            if k == "Category ID":
                cells.append(f'<c r="{ref}" s="{colstyle.get("C", "28")}" t="n"><f>IF(NOT(ISBLANK(D{n})), VLOOKUP(D{n},Categories!$A$2:$B$51,2,FALSE), "")</f><v>{v["Category ID"]}</v></c>')
                continue
            if k in ("C:Issue Number", "C:Features", "C:Cover Artist", "C:Language", "C:Signed", "C:Unit of Sale", "C:Vintage") and h not in ext_cols:
                continue
            val = v.get(k, "")
            if val in ("", None):
                continue
            cells.append(cell(ref, *val) if isinstance(val, tuple) else cell(ref, val))
        rowxml = f'<row r="{n}">' + "".join(cells) + "</row>"
        s, cnt = re.subn(rf'<row r="{n}"[^>]*>.*?</row>', lambda m: rowxml, s, count=1, flags=re.S)
        if not cnt:
            sys.exit(f"Template has no row {n}")
    s = re.sub(r'<dimension ref="[^"]+"/>', f'<dimension ref="A1:{col_letter(len(header)-1)}{4+len(rows)}"/>', s)
    open(sp, "w", encoding="utf-8").write(s)
    wx = os.path.join(work, "xl/workbook.xml")
    w = open(wx, encoding="utf-8").read()
    if "fullCalcOnLoad" not in w:
        w = re.sub(r"<calcPr([^/]*)/>", r'<calcPr\1 fullCalcOnLoad="1"/>', w) if "<calcPr" in w else w.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
        open(wx, "w", encoding="utf-8").write(w)
    with zipfile.ZipFile(out_xlsx, "w", zipfile.ZIP_DEFLATED) as zo:
        zo.write(os.path.join(work, "[Content_Types].xml"), "[Content_Types].xml")
        for name in zin.namelist():
            if name != "[Content_Types].xml":
                zo.write(os.path.join(work, name), name)
    shutil.rmtree(work, ignore_errors=True)

    out_csv = None
    if action == "Draft":
        out_csv = os.path.join(outdir, f"{batch}_drafts.csv")
        cspec = [h for h in header if h.startswith("C:") and (h in hdr or h in ext_cols)
                 and (h not in ("C:Issue Number", "C:Features", "C:Cover Artist", "C:Language", "C:Signed",
                                "C:Unit of Sale", "C:Vintage") or h in ext_cols)]
        write_drafts_csv(out_csv, rows, cspec)

    # ---- validate (strict) against the repo
    md, js = os.path.join(outdir, "validation.md"), os.path.join(outdir, "validation.json")
    r = subprocess.run([sys.executable, "-I", VALIDATOR, out_xlsx, "--strict", "--group", G["name"],
                        "--repo", L.ROOT, "--md", md, "--json", js], capture_output=True, text=True)
    res = json.load(open(js))
    json.dump({"batch": batch, "group": G["name"], "action": action, "file": os.path.relpath(out_csv or out_xlsx, L.ROOT), "validated_xlsx": os.path.relpath(out_xlsx, L.ROOT),
               "verdict": res["verdict"], "items": manifest, "shipping_profile": ship or "(legacy columns)"},
              open(os.path.join(outdir, "manifest.json"), "w"), indent=1)
    print(f"{len(rows)} listings -> {os.path.relpath(out_xlsx, L.ROOT)}")
    if out_csv:
        print(f"Drafts upload file (upload this one) -> {os.path.relpath(out_csv, L.ROOT)}")
    print(f"Validation: {res['verdict']} ({res['errors']} errors, {res['warnings']} warnings) -> {os.path.relpath(md, L.ROOT)}")
    if res["verdict"] == "FAIL":
        print("Items NOT marked exported. Fix the listing.json files (or defaults) and rebuild.")
        sys.exit(1)
    if not a.dry_run:
        for d in items:
            d["status"] = "exported"
            L.log(d, "exported", batch=batch, action=action)
            L.save_item(d)
        L.rebuild_index()
        print(f"Marked {len(items)} items exported in batch {batch}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
