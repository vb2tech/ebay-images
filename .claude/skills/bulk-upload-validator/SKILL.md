---
name: bulk-upload-validator
description: Check a filled eBay Seller Hub bulk upload file (.xlsx category template or .csv) for errors before it's uploaded, and report PASS / PASS WITH WARNINGS / FAIL with a fix for each problem. Use whenever the user asks to check, validate, verify or proof an eBay upload file, and always after create-bulk-upload builds one.
---

# Bulk upload validator

Checks a filled eBay upload file against eBay's rules and our project bar, then reports what to fix.

## Where things live
Repo `vb2tech/ebay-images` (clone to `/home/claude/ebay-images` if it isn't attached):
- Script: `.claude/skills/bulk-upload-validator/scripts/validate.py`
- Rules per listing group: `templates/registry.json` → `templates/<group>/field_rules.json`
- Human field guide: `docs/templates/<group>-fields.md` (comics: `comics-259104-fields.md`)

## Run it
```bash
cd /home/claude/ebay-images
python3 -I .claude/skills/bulk-upload-validator/scripts/validate.py <file> \
  [--strict] [--repo /home/claude/ebay-images] [--check-urls] \
  --md <out>/validation.md --json <out>/validation.json
```
- The group (and so the rules + dropdown lists) is detected from the file's Category ID. Override with `--group`.
- A `.csv` has no hidden lookup sheets; the group's template supplies them automatically.
- `--strict`: project-standard fields become errors. Use it for files **we** generated; use plain mode for a file the user filled by hand, and mention which mode ran.
- `--repo`: checks every photo URL that points at the image repo exists as a file in the clone **and shows the slab its listing names** (photo-label check below). Use it whenever the repo is available.
- `--check-urls`: HTTP check of each photo URL. Only if network allows; failures to connect are warnings.
- Needs `python-calamine` (`pip install python-calamine --break-system-packages`). Exit 0 = pass, 1 = fail, 2 = unreadable.

## What it checks
1. **eBay minimum** (always errors): Action, Category, Title ≤ 80, Start price format, Quantity, photo URLs (https, no spaces, image extension, ≤ 24, ≤ 2048 chars), Condition ID allowed for the category, Description (≤ 32,765, no scripts), Format/Duration pairing, Location (required for Add; note only for Draft), shipping/returns/payment either as saved policies (must match the template's dropdown exactly) or as legacy columns, never both.
2. **Formats and lists**: closed item-specific lists (Format, Era, Grade, Professional Grader), 65-char aspect values, Buy It Now ≥ 30% over an auction start, best-offer prices below Start price, schedule time in the next 3 weeks.
3. **Project standard** (errors in `--strict`): SKU and the 14 item specifics we can read off a slab.
4. **Photo shows the right slab** (with `--repo`): every photo must have a recorded label read whose cert matches the listing (see below). Errors: the label read shows another slab; the picture is the same as a photo in a different listing; (strict) the photo was never read or has changed since. Warning: the same picture repeated inside one listing.
5. **Consistency**: duplicate SKU/cert (errors), title grade = C:Grade, condition fits grade, year fits era, SKU matches grader/cert/photo filenames.

## Photo-label check (`scripts/photo_check.py`)
File names can't prove a photo shows the right book. In Nov 2026, 20 of 110 photos sat in the wrong item's folder, so **every photo needs a label read on record** before it can go into an upload file.
- Each item's `listing.json` keeps `photo_checks`: per file, the label read (title, issue, grade, cert), the result, the date, and a picture fingerprint. A read stays valid while the file still looks the same: brightening or re-saving is fine, but a different picture makes it `changed` and it has to be read again.
- Match rule: the label's cert equals the listing cert (and the grade agrees). If the cert is unreadable, series, issue and grade must all match (`match-no-cert`).

Workflow when the check reports unverified, changed or mismatched photos:
```bash
python3 -I .claude/skills/bulk-upload-validator/scripts/photo_check.py pending [--sku ...] --out <scratch>/worklist.json
```
1. Look at every photo in the worklist with Read, and write down **only what the label says** (never copy from the listing): one JSON line per photo, `{"path", "title", "issue", "grade", "cert", "notes"}`, with cert `"UNREADABLE"` if you truly can't read it. For more than ~25 photos, split the list between subagents that only read labels.
2. `photo_check.py record <scratch>/reads.jsonl`. It saves the reads and lists every MISMATCH (also added to the item's `needs_review`).
3. For a mismatch, find which item the photo really belongs to (its cert), copy the correct image to the wrong path (**keep paths; live listings link to them**), read the labels again and record. Drop exact repeats from `listing.json` `photos`.
4. `photo_check.py audit` checks the whole repo (or `--sku`, `--status`); it must end with `0 problem(s)` before building.

## Report to the user
Lead with the verdict line and counts, then the errors (they block eBay), then warnings. Show the markdown report (or its key tables) in the reply; for long reports, send `validation.md` as a file. Don't paste the field coverage table unless asked; mention any "ready to raise the bar" line, since that's how the project standard grows.

When it FAILS on a file we built: fix the item data (`listing.json`) or the group's `listing_defaults.json`, rebuild, and re-validate. Don't hand over a failing file as ready.

## Raising the bar
When the report shows an item specific filled on every row that isn't standard yet, and we can fill it confidently for every book, move it to `"tier": "standard"` in the group's `field_rules.json` and add a dated line to `threshold_history`. Tell the user in one line when you do this.
