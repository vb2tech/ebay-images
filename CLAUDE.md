# ebay-images: eBay listing pipeline

Photos of items for sale (graded comics today) plus everything needed to list them on eBay in bulk.
The photos are served to eBay from `https://raw.githubusercontent.com/vb2tech/ebay-images/main/...`, so anything a listing links to must be on `main`, and existing photo paths must never be renamed or moved.

## Pipeline (skills in `.claude/skills/`)
1. **upload-lot-photos**: photos from chat → one folder per item + `listing.json` (status `new`).
2. **pricing-proposal**: research sold comps → numbered review report → user approves → `pricing.final`, status `priced`.
3. **create-bulk-upload**: every `priced` item → eBay template .xlsx in `uploads/<batch>/`, validated, status `exported`; after the user uploads, `uploaded`.
4. **bulk-upload-validator**: checks any filled upload file (ours or hand-made) and reports PASS / WARN / FAIL.

## Layout
- `photos/<Series>/<Series>-<issue>_<Grader>-<grade>[_<Variant>]_<cert>/` → `<SKU>-<n>.jpg` + `listing.json` (source of truth for the item and its status).
- `templates/registry.json` → listing groups; `templates/<group>/` holds eBay's template, `field_rules.json` (validator rules, required vs optional tiers) and `listing_defaults.json` (seller choices: policies, format, condition mapping).
- `docs/templates/` → human field guides and how to fetch/add templates.
- `tools/ebaylib.py` → shared helpers; `index.csv` + README table are generated (`rebuild_index`).
- `uploads/<batch>/` → each generated file, its validation report and manifest. `pricing/` → review pages and number→SKU maps.

## Conventions
- SKU = `<Grader>-<cert>`; photo files keep the SKU name.
- Status: `new → priced → exported → uploaded` (+ `hold`, `sold`). Books from before listing.json show as `legacy` in index.csv.
- eBay's template has an invalid font setting: read it with `python-calamine`, write it by editing sheet XML (the builder does). Don't open/save it with openpyxl.
- Raise the project bar by moving fields to `"tier": "standard"` in the group's `field_rules.json` (log it in `threshold_history`).
- Run scripts with `python3 -I` from the repo root. Before pushing: `git fetch origin main && git rebase origin/main`.

## Ecosystem page (keep it current)
`docs/ecosystem.html` is published as the artifact https://claude.ai/artifact/XVkxtQwWWadWuUqVAtfYNN ("eBay Listing Ecosystem").
Whenever a skill, rule tier, listing group, default, open item or item-status count changes: edit `docs/ecosystem.html` (stats, status counts, skill chips, open items, add a changelog line, bump the version and date), commit it, and republish with the Artifact tool passing that `url` (read it first with `action: "read"`), so the link never changes. Also bump the "Last updated" line in the claude.ai project doc `claude/00-START-HERE.md`, which links to this page.
