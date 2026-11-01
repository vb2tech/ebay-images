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
- `--repo`: checks every photo URL that points at the image repo exists as a file in the clone. Use it whenever the repo is available.
- `--check-urls`: HTTP check of each photo URL. Only if network allows; failures to connect are warnings.
- Needs `python-calamine` (`pip install python-calamine --break-system-packages`). Exit 0 = pass, 1 = fail, 2 = unreadable.

## What it checks
1. **eBay minimum** (always errors): Action, Category, Title ≤ 80, Start price format, Quantity, photo URLs (https, no spaces, image extension, ≤ 24, ≤ 2048 chars), Condition ID allowed for the category, Description (≤ 32,765, no scripts), Format/Duration pairing, Location (required for Add; note only for Draft), shipping/returns/payment either as saved policies (must match the template's dropdown exactly) or as legacy columns, never both.
2. **Formats and lists**: closed item-specific lists (Format, Era, Grade, Professional Grader), 65-char aspect values, Buy It Now ≥ 30% over an auction start, best-offer prices below Start price, schedule time in the next 3 weeks.
3. **Project standard** (errors in `--strict`): SKU and the 14 item specifics we can read off a slab.
4. **Consistency**: duplicate SKU/cert (errors), title grade = C:Grade, condition fits grade, year fits era, SKU matches grader/cert/photo filenames.

## Report to the user
Lead with the verdict line and counts, then the errors (they block eBay), then warnings. Show the markdown report (or its key tables) in the reply; for long reports, send `validation.md` as a file. Don't paste the field coverage table unless asked; mention any "ready to raise the bar" line, since that's how the project standard grows.

When it FAILS on a file we built: fix the item data (`listing.json`) or the group's `listing_defaults.json`, rebuild, and re-validate. Don't hand over a failing file as ready.

## Raising the bar
When the report shows an item specific filled on every row that isn't standard yet, and we can fill it confidently for every book, move it to `"tier": "standard"` in the group's `field_rules.json` and add a dated line to `threshold_history`. Tell the user in one line when you do this.
