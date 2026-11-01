---
name: upload-lot-photos
description: Take a lot of item photos the user dropped in chat (graded comics today), group them into one item per slab, read the label and research the book to fill the listing fields, then save photos + a listing.json per item to the vb2tech/ebay-images GitHub repo. Use when the user uploads a batch of photos to list, says "here's a new lot", or asks to add items/photos to the repo.
---

# Upload a lot of pictures

Turns a pile of photos into one repo folder per item, each with a `listing.json` holding everything we know about it. This is step 1 of the pipeline: **upload-lot-photos → pricing-proposal → create-bulk-upload (→ bulk-upload-validator)**.

## Setup
- Repo `vb2tech/ebay-images` at `/home/claude/ebay-images` (attach and clone it if missing; pull first: `git -C /home/claude/ebay-images pull --ff-only`).
- Pick the listing group from `templates/registry.json` (today only `comics-259104`, graded comics). If the photos aren't comics, stop and say a new group is needed (see `docs/templates/README.md`).
- Read the group's field guide (`docs/templates/comics-259104-fields.md`) so you know which fields the project standard requires.

## Steps
1. **List the photos.** Glob the uploads. Look at every image (Read shows it).
2. **Group them.** One item = one slab. Front and back shots of the same slab share a cert number; put the front first. Photos that clearly show two slabs or nothing usable go in a "couldn't use" list for the user. If two slabs look identical (same book and grade), the cert number decides; never merge different certs.
3. **Read each label.** Grader (CGC/CBCS/PGX), grade, cert number, series, issue, publisher, cover date, page quality, key notes on the label (1st appearance, variant, newsstand, signature, "poly-bag removed"…).
4. **Research the gaps** (web search; don't guess from memory): writer / interior artist / cover artist, main characters, era, format (Single Issue vs Limited Series vs Trade Paperback), notable key facts. Match series and character names to eBay's lists where possible (the group template's Aspects sheet).
5. **Write a title** ≤ 80 chars in the shop's style: `<Series> #<issue> <Grader> <grade> <Variant/Pages> <key fact> <Publisher> <year>`, e.g. `Icon #1 CGC 9.2 Collector's Edition 1st Icon & Rocket Milestone DC 1993`.
6. **Write `lot.json`** in the scratchpad (format in the script's docstring). Anything not read or confirmed with confidence goes in that item's `needs_review` (e.g. `"cert: label glare, read as 4402325022"`). Never invent a cert number; leave it empty and the script makes a placeholder SKU that the validator will flag.
7. **Ingest:**
   ```bash
   cd /home/claude/ebay-images
   python3 -I .claude/skills/upload-lot-photos/scripts/ingest_lot.py <scratch>/lot.json --lot "lot-<date>"
   ```
   It converts photos to .jpg (HEIC ok), names them `<SKU>-<n>.jpg`, writes `photos/<Series>/<Series>-<issue>_<Grader>-<grade>[_<Variant>]_<cert>/listing.json` with `status: "new"`, appends photos to an item that already exists, and rebuilds `index.csv` + the README table. Fix anything under `problems` and re-run.
8. **Commit and push** (ask first only if the user said to review before pushing):
   ```bash
   git add -A photos index.csv README.md && git commit -m "Add lot <name>: <n> items" && git fetch origin main && git rebase origin/main && git push origin HEAD:main
   ```
   eBay reads photos from `raw.githubusercontent.com/vb2tech/ebay-images/main/...`, so they must be on `main`.

## Report back
A short table: #, SKU, title, photos, and any `needs_review` flags. Then offer the next step: pricing proposals for these items.

## Rules
- Don't rename or move existing photos in the repo; live listings link to those exact paths.
- One SKU per slab: `<Grader>-<cert>`.
- Item fields live under `item` in listing.json; keep names consistent with existing files (`series, issue, publisher, year, cover_date, grader, grade, pages, cert, format, era, characters[], writer, artist, cover_artist, credits, key_notes[], features[], team, variant_tag`).
- When the project standard in `field_rules.json` grows, gather those fields here too.
