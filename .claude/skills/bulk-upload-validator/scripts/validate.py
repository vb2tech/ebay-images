#!/usr/bin/env python3
"""Validate a filled eBay Seller Hub bulk upload file (category template .xlsx or .csv).

Usage:
  python3 -I validate.py <file.xlsx|file.csv> [--strict] [--template T.xlsx] [--rules R.json]
                         [--repo /path/to/ebay-images] [--check-urls] [--today YYYY-MM-DD]
                         [--md report.md] [--json report.json]

Exit code: 0 = PASS (maybe with warnings), 1 = FAIL (errors found), 2 = could not read the file.

Rules come from templates/registry.json: the group is detected from the file's Category ID (or --group / --rules).
Dropdown lists (categories + condition IDs, business policies, item-specific values) come from the
file's own hidden sheets; for a CSV, or a file missing them, pass --template.
--strict turns 'standard' (project-bar) misses into errors; create-bulk-upload always uses it.
"""
import argparse, csv, datetime as dt, json, os, re, sys, urllib.parse, urllib.request
from collections import Counter, defaultdict

try:
    from python_calamine import CalamineWorkbook
except ImportError:  # pragma: no cover
    sys.exit("python-calamine is required: pip install python-calamine --break-system-packages")

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".avif")


# ----------------------------------------------------------------------------- helpers
def find_up(rel):
    d = HERE
    for _ in range(8):
        p = os.path.join(d, rel)
        if os.path.exists(p):
            return p
        d = os.path.dirname(d)
    return None


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def norm(v):
    """Cell value -> trimmed string, numbers without a trailing .0."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return str(v)


def money(s):
    if not re.fullmatch(r"\d+(\.\d{1,2})?", s):
        return None
    return float(s)


def header_key(h):
    """'*Action(SiteID=US|...)' -> 'Action'; 'Item photo URL.' -> 'Item photo URL'."""
    h = h.strip().lstrip("*")
    if h.startswith("Action("):
        return "Action"
    return h.rstrip(".").strip()


# ----------------------------------------------------------------------------- loading
def read_rows(path):
    """Return (header list, [(excel_row_number, [values])], workbook-or-None)."""
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        wb = None
    else:
        wb = CalamineWorkbook.from_path(path)
        if "Listings" not in wb.sheet_names:
            raise ValueError(f"No 'Listings' sheet (sheets: {wb.sheet_names})")
        rows = wb.get_sheet_by_name("Listings").to_python(skip_empty_area=False)
    hdr_i = next((i for i, r in enumerate(rows[:20]) if r and "Action(" in norm(r[0])), None)
    if hdr_i is None:
        raise ValueError("Couldn't find the header row (first cell should start with '*Action(').")
    header = [norm(h) for h in rows[hdr_i]]
    body = []
    for i, r in enumerate(rows[hdr_i + 1:], start=hdr_i + 2):
        vals = [norm(v) for v in r] + [""] * (len(header) - len(r))
        if any(v for j, v in enumerate(vals) if not (header[j] == "Category ID" and v in ("0", ""))):
            body.append((i, vals))
    return header, body, wb


def load_lookups(wb, template):
    src = wb
    if src is None or "Categories" not in src.sheet_names:
        if not template:
            return None
        src = CalamineWorkbook.from_path(template)

    def sheet(name):
        return src.get_sheet_by_name(name).to_python(skip_empty_area=False) if name in src.sheet_names else []

    cats = {}
    for r in sheet("Categories")[1:]:
        if r and norm(r[0]):
            cats[norm(r[0])] = {"id": norm(r[1]), "conditions": [norm(x) for x in r[2:] if norm(x)]}
    pol = [[], [], []]
    for r in sheet("BusinessPolicy")[1:]:
        for c in range(3):
            if c < len(r) and norm(r[c]):
                pol[c].append(norm(r[c]))
    aspects = {}
    for r in sheet("Aspects"):
        if len(r) > 5 and re.fullmatch(r"\d+", norm(r[0])) and norm(r[1]).startswith("C:"):
            aspects[norm(r[1])] = {"level": norm(r[4]), "values": {norm(x) for x in r[5:] if norm(x)}}
    return {"categories": cats, "policies": pol, "aspects": aspects}


# ----------------------------------------------------------------------------- validator
class Report:
    def __init__(self):
        self.items = []

    def add(self, sev, row, sku, col, msg, fix=""):
        self.items.append({"severity": sev, "row": row, "sku": sku, "column": col, "message": msg, "fix": fix})

    def count(self, sev):
        return sum(1 for i in self.items if i["severity"] == sev)


def rule_for(rules, key):
    f = rules["fields"]
    if key in f:
        return f[key]
    for pat, r in f.items():
        if pat.endswith("*") and key.startswith(pat[:-1].rstrip()):
            return r
    if key.startswith("C:"):
        return {"tier": "extension", "type": "aspect", "closed": False, "_unknown": True}
    return None


def validate(path, rules, template=None, strict=False, repo=None, check_urls=False, today=None):
    rep = Report()
    header, body, wb = read_rows(path)
    keys = [header_key(h) for h in header]
    idx = {k: i for i, k in enumerate(keys) if k}
    look = load_lookups(wb, template)
    today = today or dt.date.today()
    tiers_seen = {}

    # --- file-level checks
    dupes = [k for k, n in Counter(k for k in keys if k).items() if n > 1]
    for k in dupes:
        rep.add("ERROR", 0, "", k, f"Column '{k}' appears more than once in the header.", "Delete the duplicate column.")
    for k in keys:
        if k and rule_for(rules, k) is None:
            rep.add("WARNING", 0, "", k, f"Unrecognized column '{k}'. eBay may reject the file or ignore it.",
                    "Remove it, or add it to this group's field_rules.json if it's a real eBay column.")
        elif k and (rule_for(rules, k) or {}).get("_unknown"):
            if look and look["aspects"] and k not in look["aspects"]:
                rep.add("WARNING", 0, "", k, f"'{k}' is not an item specific eBay lists for this category.",
                        "Check the spelling against the Aspects sheet.")
    for k, r in rules["fields"].items():
        if r["tier"] == "required" and k not in idx and not k.endswith("*"):
            rep.add("ERROR", 0, "", k, f"Required column '{k}' is missing from the header.", "Start from eBay's template.")
    if look is None:
        rep.add("WARNING", 0, "", "", "No dropdown lists available (CSV without --template): categories, condition IDs, "
                "policies and item-specific values were NOT checked.", "Re-run with --template templates/ebay-category-template-259104.xlsx")
    if not body:
        rep.add("ERROR", 0, "", "", "No listing rows found below the header.", "Fill rows starting at row 5.")

    def g(vals, k):
        i = idx.get(k)
        return vals[i].strip() if i is not None and i < len(vals) else ""

    seen = defaultdict(list)
    coverage = Counter()
    sev_std = "ERROR" if strict else "WARNING"
    sev_rec = "WARNING" if strict else "INFO"
    prefix = rules.get("project_checks", {}).get("photo_repo_prefix", "")

    for rown, vals in body:
        sku = g(vals, "Custom label (SKU)")
        A = lambda sev, col, msg, fix="": rep.add(sev, rown, sku, col, msg, fix)
        for k in idx:
            if g(vals, k):
                coverage[k] += 1
        action = g(vals, "Action")
        if not action:
            A("WARNING", "Action", "Row has data but no Action, so eBay will skip it.", "Set Action to Add or Draft, or clear the row.")
            continue

        # raw whitespace / formatting
        for k, i in idx.items():
            raw = vals[i] if i < len(vals) else ""
            if raw and raw != raw.strip() and k not in ("Description",):
                A("WARNING", k, "Value has leading or trailing spaces.", "Trim it.")

        # tier presence checks
        for k in idx:
            r = rule_for(rules, k) or {}
            t = r.get("tier")
            tiers_seen[k] = t
            v = g(vals, k)
            if t == "required" and not v:
                if k == "Location" and action == "Draft":
                    A("INFO", k, "Location is empty. Fine for a Draft, required before the draft can go live.")
                elif k == "Category ID" and g(vals, "Category name"):
                    pass  # formula not cached; checked below via name
                else:
                    A("ERROR", k, "Required field is empty.")
            elif t == "standard" and not v:
                A(sev_std, k, "Project-standard field is empty.", "Fill it (see this group's field guide in docs/templates/).")
            elif t == "recommended" and not v and k != "C:Superhero Team":
                A(sev_rec, k, "Recommended field is empty.")
            elif t == "not_used" and v:
                A("WARNING", k, "We don't use this column; it's filled.", "Clear it unless you meant to.")
        for k, r in rules["fields"].items():
            if r["tier"] == "standard" and k not in idx:
                A(sev_std, k, "Project-standard column is missing from the file.")

        # --- Action
        if action not in ("Add", "Draft"):
            A("ERROR", "Action", f"Action '{action}' isn't valid here.", "Use Add (publish) or Draft.")
        elif action == "Draft":
            A("INFO", "Action", "Draft: rows go to your Drafts folder (not this template's own dropdown value). "
              "Confirm the upload results show them as drafts.")

        # --- Category
        cid, cname = g(vals, "Category ID"), g(vals, "Category name")
        if look and look["categories"]:
            cat = look["categories"].get(cname)
            if cname and not cat:
                A("ERROR", "Category name", f"'{cname}' isn't in this template's Categories list.")
            ids = {c["id"] for c in look["categories"].values()}
            if cid and cid not in ids:
                A("ERROR", "Category ID", f"Category ID {cid} doesn't match this template ({', '.join(sorted(ids))}).")
            if cat and cid and cat["id"] != cid:
                A("ERROR", "Category ID", f"Category ID {cid} doesn't match Category name (expects {cat['id']}).")
            if not cid and not cat:
                A("ERROR", "Category ID", "No Category ID and no valid Category name.")
        elif cid and not re.fullmatch(r"\d{1,10}", cid):
            A("ERROR", "Category ID", f"Category ID '{cid}' must be a number up to 10 digits.")

        # --- Title
        title = g(vals, "Title")
        if len(title) > 80:
            A("ERROR", "Title", f"Title is {len(title)} characters (max 80).", "Shorten it.")
        if re.search(r"[<>]", title):
            A("WARNING", "Title", "Title contains < or >, which eBay strips or rejects.")
        if title:
            seen["Title"].append((title, rown))

        # --- price / qty
        sp = g(vals, "Start price")
        spv = None
        if sp:
            spv = money(sp)
            if spv is None:
                A("ERROR", "Start price", f"'{sp}' isn't a plain price (digits, up to 2 decimals, no $).")
            elif spv < 0.99:
                A("ERROR", "Start price", f"Price {sp} is below eBay's $0.99 minimum.")
        q = g(vals, "Quantity")
        if q:
            if not re.fullmatch(r"\d+", q) or int(q) < 1:
                A("ERROR", "Quantity", f"Quantity '{q}' must be a whole number of at least 1.")
            elif int(q) != rules["fields"]["Quantity"].get("project_expect", int(q)):
                A("WARNING", "Quantity", f"Quantity {q}: graded slabs are unique, expected 1.")

        # --- photos
        urls = g(vals, "Item photo URL")
        if urls:
            r = rules["fields"]["Item photo URL"]
            if len(urls) > r["max_len"]:
                A("ERROR", "Item photo URL", f"Photo cell is {len(urls)} characters (max {r['max_len']}).")
            parts = [u for u in urls.split("|")]
            if any(not u.strip() for u in parts):
                A("ERROR", "Item photo URL", "Empty photo entry (a doubled or trailing separator).")
            parts = [u.strip() for u in parts if u.strip()]
            if len(parts) > r["max_photos"]:
                A("ERROR", "Item photo URL", f"{len(parts)} photos (eBay max {r['max_photos']}).")
            elif len(parts) > r["warn_photos_over"]:
                A("WARNING", "Item photo URL", f"{len(parts)} photos; Seller Hub's template note says 12 per listing.")
            if len(set(parts)) < len(parts):
                A("WARNING", "Item photo URL", "The same photo URL is listed twice.")
            for u in parts:
                if " " in u:
                    A("ERROR", "Item photo URL", f"URL has a space (use %20): {u}")
                if not u.lower().startswith("https://"):
                    A("ERROR", "Item photo URL", f"URL must start with https:// : {u}")
                if not urllib.parse.urlparse(u).path.lower().endswith(IMG_EXT):
                    A("ERROR", "Item photo URL", f"URL doesn't end in an image extension: {u}")
                if prefix and not u.startswith(prefix):
                    A("WARNING", "Item photo URL", f"URL isn't in the photo repo: {u}")
                if repo and prefix and u.startswith(prefix):
                    local = os.path.join(repo, urllib.parse.unquote(u[len(prefix):]))
                    if not os.path.isfile(local):
                        A("ERROR", "Item photo URL", f"Photo not found in the repo: {u[len(prefix):]}",
                          "Push the photo, or fix the path.")
                if check_urls:
                    try:
                        req = urllib.request.Request(u, method="HEAD")
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            if resp.status >= 400:
                                A("ERROR", "Item photo URL", f"URL returns HTTP {resp.status}: {u}")
                    except Exception as e:  # noqa: BLE001
                        A("WARNING", "Item photo URL", f"Couldn't reach {u} ({e.__class__.__name__}).")
            if sku and prefix:
                for u in parts:
                    fn = os.path.basename(urllib.parse.urlparse(u).path)
                    if not fn.startswith(sku + "-"):
                        A("WARNING", "Item photo URL", f"Photo file {fn} doesn't match SKU {sku}.")

        # --- condition
        cond = g(vals, "Condition ID")
        cond_id = re.match(r"\d+", cond).group(0) if re.match(r"\d+", cond) else ""
        if cond:
            if not cond_id:
                A("ERROR", "Condition ID", f"'{cond}' doesn't start with a condition number.")
            elif look and look["categories"]:
                cat = look["categories"].get(cname) or next((c for c in look["categories"].values() if c["id"] == cid), None)
                if cat:
                    ok = {re.match(r"\d+", c).group(0) for c in cat["conditions"] if re.match(r"\d+", c)}
                    if cond_id not in ok:
                        A("ERROR", "Condition ID", f"Condition {cond_id} isn't allowed in this category "
                          f"(allowed: {', '.join(cat['conditions'])}).")

        # --- description
        desc = g(vals, "Description")
        if desc:
            if len(desc) > 32765:
                A("ERROR", "Description", f"Description is {len(desc)} characters (max 32,765).")
            if re.search(r"<\s*(script|iframe|object|embed|form)\b", desc, re.I):
                A("ERROR", "Description", "Description has active content (script/iframe/form), which eBay blocks.")
            if re.search(r"\bon(click|load|error|mouseover)\s*=", desc, re.I):
                A("ERROR", "Description", "Description has JavaScript event handlers, which eBay blocks.")
            if len(re.sub(r"<[^>]+>", "", desc).strip()) < 30:
                A("WARNING", "Description", "Description is very short.")

        # --- format / duration / BIN / best offer
        fmt, dur = g(vals, "Format"), g(vals, "Duration")
        if fmt and fmt not in ("Auction", "FixedPrice"):
            A("ERROR", "Format", f"Format '{fmt}' must be Auction or FixedPrice.")
        if fmt == "FixedPrice" and dur and dur != "GTC":
            A("ERROR", "Duration", f"Fixed-price listings must use GTC (got '{dur}').")
        if fmt == "Auction" and dur and dur not in ("1", "3", "5", "7", "10"):
            A("ERROR", "Duration", f"Auction duration must be 1, 3, 5, 7 or 10 (got '{dur}').")
        bin_ = g(vals, "Buy It Now price")
        if bin_:
            b = money(bin_)
            if fmt != "Auction":
                A("ERROR", "Buy It Now price", "Buy It Now price only applies to Auction format.")
            elif b is None:
                A("ERROR", "Buy It Now price", f"'{bin_}' isn't a plain price.")
            elif spv and b < round(spv * 1.3, 2):
                A("ERROR", "Buy It Now price", f"Buy It Now {b} must be at least 30% above Start price {spv} (≥ {spv*1.3:.2f}).")
        bo = g(vals, "Best Offer Enabled")
        if bo and bo.lower() not in ("1", "0", "true", "false"):
            A("ERROR", "Best Offer Enabled", f"'{bo}' must be 1/0 or True/False.")
        bo_on = bo.lower() in ("1", "true")
        aa, mn = g(vals, "Best Offer Auto Accept Price"), g(vals, "Minimum Best Offer Price")
        for k, v in (("Best Offer Auto Accept Price", aa), ("Minimum Best Offer Price", mn)):
            if v:
                m = money(v)
                if m is None:
                    A("ERROR", k, f"'{v}' isn't a plain price.")
                elif not bo_on:
                    A("WARNING", k, "Set, but Best Offer isn't enabled, so it does nothing.")
                elif spv and m >= spv:
                    A("ERROR", k, f"{m} must be below Start price {spv}.")
        if aa and mn and money(aa) and money(mn) and money(mn) >= money(aa):
            A("ERROR", "Minimum Best Offer Price", "Minimum offer must be below the auto-accept price.")
        ip = g(vals, "Immediate pay required")
        if ip and ip.lower() not in ("1", "0", "true", "false"):
            A("ERROR", "Immediate pay required", f"'{ip}' must be 1 or 0.")

        # --- schedule
        st = g(vals, "Schedule Time")
        if st:
            try:
                when = dt.datetime.fromisoformat(st.replace("Z", "+00:00").replace(" ", "T")).date()
                if when < today:
                    A("ERROR", "Schedule Time", f"Schedule time {st} is in the past.")
                elif (when - today).days > 21:
                    A("ERROR", "Schedule Time", f"Schedule time {st} is more than 3 weeks out.")
            except ValueError:
                A("ERROR", "Schedule Time", f"Can't read schedule time '{st}' (use YYYY-MM-DD HH:MM:SS).")

        # --- location
        loc = g(vals, "Location")
        if loc:
            if len(loc) > 45:
                A("ERROR", "Location", f"Location is {len(loc)} characters (max 45).")
            if re.search(r"\b\d{5}\b", loc):
                A("WARNING", "Location", "Location looks like it has a ZIP code; eBay wants City, ST.")
            elif not re.fullmatch(r"[^,]+,\s*[A-Z]{2}", loc):
                A("WARNING", "Location", f"'{loc}' isn't in City, ST form.")

        # --- shipping / returns / payment
        ship_p, ret_p, pay_p = g(vals, "Shipping profile name"), g(vals, "Return profile name"), g(vals, "Payment profile name")
        leg_ship = [k for k in ("Shipping service 1 option", "Shipping service 1 cost", "Max dispatch time") if g(vals, k)]
        leg_ret = [k for k in ("Returns accepted option", "Returns within option", "Refund option", "Return shipping cost paid by") if g(vals, k)]
        for k, v, c in (("Shipping profile name", ship_p, 0), ("Return profile name", ret_p, 1), ("Payment profile name", pay_p, 2)):
            if v and look and look["policies"][c]:
                names = look["policies"][c]
                if v not in names:
                    short = [n.rsplit(" - (ID:", 1)[0] for n in names]
                    if v in short:
                        A("WARNING", k, "Policy given by name only; the template's dropdown value includes the ID.",
                          f"Use: {names[short.index(v)]}")
                    else:
                        A("ERROR", k, f"'{v}' isn't one of your saved policies in this template.",
                          "Pick from the dropdown, or create the policy on eBay and download a fresh template.")
        if not ship_p and not leg_ship:
            A("ERROR", "Shipping profile name", "No shipping: set a Shipping profile name (or legacy shipping columns).")
        if ship_p and leg_ship:
            A("ERROR", "Shipping profile name", "Both a shipping policy and legacy shipping columns are filled.", "Use one or the other.")
        if leg_ship:
            for k in ("Shipping service 1 option", "Shipping service 1 cost", "Max dispatch time"):
                if not g(vals, k):
                    A("ERROR", k, "Legacy shipping needs service, cost and max dispatch time together.")
            c1 = g(vals, "Shipping service 1 cost")
            if c1 and money(c1) is None:
                A("ERROR", "Shipping service 1 cost", f"'{c1}' isn't a plain amount.")
            md = g(vals, "Max dispatch time")
            if md and md not in rules["fields"]["Max dispatch time"]["allowed"]:
                A("ERROR", "Max dispatch time", f"'{md}' must be one of {', '.join(rules['fields']['Max dispatch time']['allowed'])}.")
            if ret_p or pay_p:
                A("WARNING", "Shipping service 1 option",
                  "Legacy shipping columns are mixed with return/payment policies. eBay's template says not to use "
                  "these columns once you're on business policies; the row may fail or get an auto-made policy.",
                  "Create a shipping policy with this rate on eBay, download a fresh template, and use Shipping profile name.")
        if not ret_p and not leg_ret:
            A("ERROR", "Return profile name", "No return terms: set a Return profile name (or Returns accepted option).")
        if ret_p and leg_ret:
            A("ERROR", "Return profile name", "Both a return policy and legacy return columns are filled.", "Use one or the other.")
        if leg_ret:
            ra = g(vals, "Returns accepted option")
            for k in ("Returns accepted option", "Returns within option", "Refund option", "Return shipping cost paid by"):
                v = g(vals, k)
                allowed = rules["fields"][k].get("allowed", [])
                if v and allowed and v not in allowed:
                    A("ERROR", k, f"'{v}' must be one of {', '.join(allowed)}.")
                if ra == "ReturnsAccepted" and not v:
                    A("ERROR", k, "Needed when returns are accepted.")
        if (ship_p or ret_p) and not pay_p:
            A("ERROR", "Payment profile name", "Business policies are in use, so a Payment profile name is required.")

        # --- relationship
        rel = g(vals, "Relationship")
        if rel and rel not in ("Variation", "Compatibility"):
            A("ERROR", "Relationship", f"'{rel}' must be Variation or Compatibility.")
        if " " in g(vals, "Relationship details"):
            A("ERROR", "Relationship details", "Relationship details can't contain spaces.")

        # --- item specifics
        for k in idx:
            if not k.startswith("C:"):
                continue
            v = g(vals, k)
            if not v:
                continue
            r = rule_for(rules, k) or {}
            vals_ = [x.strip() for x in v.split("|")]
            lim = 800 if "Prop 65" in k else rules.get("aspect_value_max_len", 65)
            for x in vals_:
                if not x:
                    A("ERROR", k, "Empty value between pipes.")
                elif len(x) > lim:
                    A("ERROR", k, f"Value is {len(x)} characters (max {lim}): {x[:40]}…")
            if len(vals_) > 1 and not r.get("multi"):
                A("WARNING", k, f"{len(vals_)} values given; this item specific normally takes one.")
            if look and k in look["aspects"] and look["aspects"][k]["values"]:
                allowed = look["aspects"][k]["values"]
                bad = [x for x in vals_ if x and x not in allowed]
                low = {a.lower(): a for a in allowed}
                for x in bad:
                    hint = f"Did you mean '{low[x.lower()]}'?" if x.lower() in low else ""
                    if r.get("closed"):
                        A("ERROR" if r.get("tier") != "extension" else "WARNING", k,
                          f"'{x}' isn't one of eBay's allowed values.", hint or "Pick from the dropdown list.")
                    elif hint:
                        A("WARNING", k, f"'{x}' differs from eBay's value only by case.", hint)
                    elif k in ("C:Series Title", "C:Publisher"):
                        A("INFO", k, f"'{x}' is a custom value (not in eBay's list); matching eBay's name helps search.")
            if k in ("C:Certification Number", "Custom label (SKU)"):
                pass
            for uk in rules.get("project_checks", {}).get("unique", []):
                if uk == k:
                    seen[k].append((v, rown))

        if sku:
            seen["Custom label (SKU)"].append((sku, rown))
            pat = rules.get("project_checks", {}).get("sku_pattern")
            if pat and not re.match(pat, sku):
                A("WARNING", "Custom label (SKU)", f"SKU '{sku}' doesn't follow <Grader>-<cert>.")

        # --- project consistency (graded comics)
        grade_txt = g(vals, "C:Grade")
        m = re.match(r"(\d+(?:\.\d)?)", grade_txt)
        if m:
            gnum = float(m.group(1))
            if rules.get("project_checks", {}).get("title_mentions_grade") and title:
                tg = re.search(r"\b(CGC|CBCS|PGX|PSA)\s+(\d+(?:\.\d)?)\b", title)
                if not tg:
                    A("WARNING", "Title", "Title doesn't show the grader and grade (e.g. 'CGC 9.8').")
                elif abs(float(tg.group(2)) - gnum) > 0.001:
                    A("ERROR", "Title", f"Title says {tg.group(1)} {tg.group(2)} but C:Grade is {grade_txt}.")
            if cond_id:
                want = next(c for lo, c in rules["project_checks"]["condition_from_grade"] if gnum >= lo)
                if cond_id != want:
                    A("WARNING", "Condition ID", f"Grade {gnum} usually maps to condition {want}, not {cond_id}.")
        grader = g(vals, "C:Professional Grader")
        if grader and sku:
            short = re.search(r"\(([A-Z]+)\)", grader)
            if short and not sku.startswith(short.group(1) + "-"):
                A("WARNING", "Custom label (SKU)", f"SKU {sku} doesn't start with grader {short.group(1)}.")
        cert = g(vals, "C:Certification Number")
        if cert and sku and cert.replace(" ", "") not in sku:
            A("WARNING", "C:Certification Number", f"Cert {cert} doesn't appear in SKU {sku}.")
        year, era = g(vals, "C:Publication Year"), g(vals, "C:Era")
        ey = re.search(r"\((\d{4})-(\d{2,4}|Now)\)", era)
        if year.isdigit() and ey:
            lo = int(ey.group(1))
            hi = 9999 if ey.group(2) == "Now" else int(ey.group(2)) if len(ey.group(2)) == 4 else int(ey.group(1)[:2] + ey.group(2))
            if not lo <= int(year) <= hi:
                A("WARNING", "C:Era", f"Year {year} is outside {era}.")
        fmt_c, typ = g(vals, "C:Format"), g(vals, "C:Type")
        if fmt_c == "Trade Paperback" and typ == "Comic Book":
            A("WARNING", "C:Type", "Trade paperbacks are usually Type 'Graphic Novel'.")

    # --- cross-row uniqueness
    for k, lst in seen.items():
        c = Counter(v for v, _ in lst)
        for v, n in c.items():
            if n > 1:
                rows = [str(r) for x, r in lst if x == v]
                sev = "WARNING" if k == "Title" else "ERROR"
                rep.add(sev, int(rows[0]), "", k, f"'{v[:60]}' appears on {n} rows ({', '.join(rows)}).",
                        "Each listing needs its own value." if sev == "ERROR" else "Identical titles are allowed but make listings harder to tell apart.")

    n = len(body)
    cov = {k: coverage[k] for k in idx}
    promo = [k for k in idx if n and k.startswith("C:") and coverage[k] == n
             and (rule_for(rules, k) or {}).get("tier") in ("recommended", "extension", "optional")]
    return rep, {"rows": n, "header": [k for k in keys if k], "coverage": cov, "promotion_candidates": promo,
                 "tiers": {k: (rule_for(rules, k) or {}).get("tier") for k in idx}}


# ----------------------------------------------------------------------------- output
def verdict(rep):
    if rep.count("ERROR"):
        return "FAIL"
    return "PASS WITH WARNINGS" if rep.count("WARNING") else "PASS"


def markdown(path, rep, meta, strict):
    v = verdict(rep)
    icon = {"PASS": "✅", "PASS WITH WARNINGS": "⚠️", "FAIL": "❌"}[v]
    L = [f"# Bulk upload check: {icon} {v}", "",
         f"**File:** `{os.path.basename(path)}`  ",
         f"**Listings:** {meta['rows']}  ",
         f"**Mode:** {'strict (project standard enforced)' if strict else 'standard (eBay minimum enforced)'}  ",
         f"**Errors:** {rep.count('ERROR')} · **Warnings:** {rep.count('WARNING')} · **Notes:** {rep.count('INFO')}", ""]
    if v == "FAIL":
        L += ["Fix the errors below before uploading; eBay will reject those rows.", ""]
    elif v == "PASS WITH WARNINGS":
        L += ["Safe to upload. Review the warnings; they won't block eBay but may hurt the listing.", ""]
    else:
        L += ["Ready to upload.", ""]
    for sev, title in (("ERROR", "Errors (must fix)"), ("WARNING", "Warnings"), ("INFO", "Notes")):
        items = [i for i in rep.items if i["severity"] == sev]
        if not items:
            continue
        # collapse identical messages across rows
        groups = defaultdict(list)
        for i in items:
            groups[(i["column"], i["message"], i["fix"])].append(i)
        L += [f"## {title}", "", "| Rows | SKU | Column | Problem | Fix |", "|---|---|---|---|---|"]
        for (col, msg, fix), its in sorted(groups.items(), key=lambda kv: (kv[1][0]["row"], kv[0][0])):
            rows = sorted({i["row"] for i in its})
            rtxt = "file" if rows == [0] else (", ".join(map(str, rows[:8])) + (f" +{len(rows)-8} more" if len(rows) > 8 else ""))
            skus = sorted({i["sku"] for i in its if i["sku"]})
            stxt = skus[0] + (f" +{len(skus)-1}" if len(skus) > 1 else "") if skus else ""
            L.append(f"| {rtxt} | {stxt} | {col} | {msg.replace('|', '/')} | {fix.replace('|', '/')} |")
        L.append("")
    n = meta["rows"] or 1
    L += ["## Field coverage", "", "| Column | Tier | Filled |", "|---|---|---|"]
    order = {"required": 0, "conditional": 1, "standard": 2, "recommended": 3, "extension": 4, "optional": 5, "not_used": 6, None: 7}
    for k in sorted(meta["coverage"], key=lambda k: (order.get(meta["tiers"].get(k), 7), k)):
        t = meta["tiers"].get(k)
        if not meta["coverage"][k] and t not in ("required", "standard", "recommended"):
            continue
        L.append(f"| {k} | {t} | {meta['coverage'][k]}/{meta['rows']} |")
    if meta["promotion_candidates"]:
        L += ["", "**Ready to raise the bar:** these are filled on every row but aren't part of the project standard yet: "
              + ", ".join(f"`{k}`" for k in meta["promotion_candidates"])
              + ". Move them to `standard` in this group's field_rules.json if we can fill them every time."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--template")
    ap.add_argument("--rules")
    ap.add_argument("--repo")
    ap.add_argument("--check-urls", action="store_true")
    ap.add_argument("--today")
    ap.add_argument("--md")
    ap.add_argument("--json")
    ap.add_argument("--group", help="listing group from templates/registry.json (default: detect from Category ID)")
    a = ap.parse_args()
    rules_path, template = a.rules, a.template
    reg_path = find_up("templates/registry.json")
    if reg_path and not (rules_path and template):
        root = os.path.dirname(os.path.dirname(reg_path))
        reg = json.load(open(reg_path))
        group = a.group
        if not group:
            try:
                hdr, body, _ = read_rows(a.file)
                keys = [header_key(h) for h in hdr]
                ids = {r[keys.index("Category ID")] for _, r in body if "Category ID" in keys} - {"", "0"}
                names = {r[keys.index("Category name")] for _, r in body if "Category name" in keys} - {""}
                group = next((g for g, v in reg["groups"].items()
                              if ids & set(v["category_ids"]) or v.get("category_name") in names), None)
            except Exception:  # noqa: BLE001
                group = None
            group = group or reg["default"]
        g = reg["groups"][group]
        rules_path = rules_path or os.path.join(root, g["rules"])
        template = template or os.path.join(root, g["template"])
    if not rules_path or not os.path.exists(rules_path):
        sys.exit("Can't find the field rules; pass --rules or --group.")
    rules = json.load(open(rules_path))
    repo = a.repo
    today = dt.date.fromisoformat(a.today) if a.today else None
    try:
        rep, meta = validate(a.file, rules, template, a.strict, repo, a.check_urls, today)
    except Exception as e:  # noqa: BLE001
        print(f"Could not read {a.file}: {e}", file=sys.stderr)
        sys.exit(2)
    md = markdown(a.file, rep, meta, a.strict)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump({"verdict": verdict(rep), "errors": rep.count("ERROR"), "warnings": rep.count("WARNING"),
                   "notes": rep.count("INFO"), "findings": rep.items, **meta}, open(a.json, "w"), indent=1)
    print(md)
    sys.exit(1 if verdict(rep) == "FAIL" else 0)


if __name__ == "__main__":
    main()
