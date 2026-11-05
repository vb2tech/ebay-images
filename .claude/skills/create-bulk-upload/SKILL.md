---
name: create-bulk-upload
description: Build the eBay Seller Hub bulk upload .xlsx for every item in the vb2tech/ebay-images repo that is priced but not yet uploaded, using the listing group's eBay template, validate it with the bulk-upload-validator, hand the file to the user, and track upload status in the repo. Use when the user asks for the upload file, the next batch, or says a batch was uploaded (or shares eBay's upload results).
---

# Create bulk upload

Step 3 of the pipeline (**upload-lot-photos → pricing-proposal → create-bulk-upload**). Reads the repo, finds what hasn't gone to eBay yet, and makes the file.

## How "already uploaded" is tracked
Each item's `listing.json` has a `status`: `new` → `priced` → `exported` → `uploaded` (plus `hold`, `sold`), with a `history` of events and batch ids. Each batch lives in `uploads/<batch>/` (the .xlsx, `validation.md/json`, `manifest.json`). `index.csv` shows status for every book. Books from before this system have no listing.json and show as `legacy` until backfilled (`tools/backfill_from_index.py`).

## Setup
Repo at `/home/claude/ebay-images` (attach/clone, then `git pull --ff-only`). Needs `python-calamine`.
Item location is always **Hartford, CT** (`location` in `templates/<group>/listing_defaults.json`). Don't ask; only pass `--location` if the user names a different place for a batch.

## Photo gate (always, before building)
Every photo in the file must be confirmed to show the slab its listing names:
```bash
python3 -I .claude/skills/bulk-upload-validator/scripts/photo_check.py audit --sku <the SKUs you'll build>   # or --status priced
```
If it reports anything other than `0 problem(s)`, run the read-and-record workflow in the bulk-upload-validator SKILL.md (`pending` → read each label → `record`), fix mismatches, and audit again. The strict validation in the build repeats this check and FAILS the file on any unverified, changed, mismatched or duplicated photo, so a wrong picture can't reach eBay.

## Build
```bash
cd /home/claude/ebay-images
python3 -I .claude/skills/create-bulk-upload/scripts/build_bulk_upload.py [--group comics-259104] [--sku ...] [--location "City, ST"] [--action Draft|Add] [--dry-run]
```
- Default picks every item with status `priced` (approved price, never exported). `--sku` builds specific items.
- Fills the group's eBay template (one row per item, rows 5+), keeps eBay's dropdowns and hidden sheets intact, and writes `uploads/<date>_<group>_<n>/`.
- Runs the **bulk-upload-validator** in `--strict` mode with `--repo` (photo files must exist on `main`).
- Only on PASS / PASS WITH WARNINGS are items marked `exported`. On FAIL nothing is marked: fix the item data or defaults and rebuild. Never hand over a failing file as ready.
- Items in different listing groups go in separate files (one per group's template).

## Deliver
1. Push the batch folder and status changes:
   `git add -A uploads photos index.csv README.md && git commit -m "Batch <id>" && git fetch origin main && git rebase origin/main && git push origin HEAD:main`
2. Send the upload file (the `_drafts.csv` for Draft batches, else the .xlsx) with SendUserFile (`display: attach`) plus the verdict line and any warnings in a sentence or two. Remind them: Seller Hub → Reports → Uploads → Upload template, then download the results file.

## After the user uploads
- "It went up" → `python3 -I .claude/skills/create-bulk-upload/scripts/mark_uploaded.py --batch <id>` (add `--failed SKU ...` for rows that failed).
- They share eBay's results CSV → `mark_uploaded.py --batch <id> --results <file>`; failed rows go back to `priced` with the error saved, so the next build retries them. Tell the user which failed and why.
- Commit and push the status change.

## Defaults worth knowing (comics)
FixedPrice, GTC, qty 1, Best Offer on, return policy "No returns accepted", payment "eBay Payments", shipping = the saved policy containing `($17.99)`. If the account has no such policy the builder falls back to legacy USPSParcel $17.99 columns, and the validator warns because eBay says not to mix legacy shipping with business policies. The fix is to create the $17.99 shipping policy on eBay and download a fresh template into `templates/comics-259104/template.xlsx`.
Extension item specifics (Issue Number, Features, Cover Artist…) are off (`include_extension_aspects: false`) until one upload with them succeeds.
