---
name: pricing-proposal
description: Research current market prices (recent sold comps) for items in the vb2tech/ebay-images repo, propose a listing price per item, show a numbered pricing review report, and record the user's approved prices in the repo. Use after a lot is uploaded, when the user asks to price items, or when they reply to a pricing report ("approve all", "#3 = 45", "hold #5").
---

# Pricing proposal

Step 2 of the pipeline (**upload-lot-photos → pricing-proposal → create-bulk-upload**). Prices are proposed by research, decided by the user, and stored in each item's `listing.json` under `pricing`.

## Setup
Repo at `/home/claude/ebay-images` (attach/clone/pull as needed). Script: `.claude/skills/pricing-proposal/scripts/pricing.py`.

## Propose
1. `python3 -I .claude/skills/pricing-proposal/scripts/pricing.py todo` lists items with status `new` (or pass `--status`). The user may name specific SKUs instead.
2. **Research each item** with web search, item by item, exact grade first:
   - Recent **sold** prices (last ~6 months) for the same book, same grader, same grade; then the nearest grades above and below.
   - Same edition matters: newsstand vs direct, collector's/poly-bag vs regular, variant covers. Don't use a variant's comps for a regular cover.
   - Good sources: eBay sold listings, GoCollect, CovrPrice, Heritage auction results. Asking prices are not comps; use them only as a ceiling and say so.
   - CBCS/PGX usually trade below CGC at the same grade.
3. Set the proposal: around the median of recent same-grade sales; interpolate between neighbouring grades when the exact grade has no sales; the script snaps to the shop's `.99` price points. Confidence: **high** = 3+ recent same-grade sales; **medium** = few sales or interpolated; **low** = estimate with little data (say what's missing in `basis`).
4. Write `proposals.json` in the scratchpad (format in the script docstring, include the comp URLs), then:
   ```bash
   python3 -I .claude/skills/pricing-proposal/scripts/pricing.py propose <scratch>/proposals.json
   python3 -I .claude/skills/pricing-proposal/scripts/pricing.py report --out pricing/review.html
   ```
   `report` numbers the items (#1…#n), saves `pricing/review-<stamp>.json` mapping numbers to SKUs, and writes the HTML page.
5. **Show the report**: publish `pricing/review.html` as an artifact (it's a page the user will review and come back to), and in the reply give a compact table: #, title, proposed, range, confidence. Point out low-confidence rows. Tell the user how to answer: `approve all`, `#3 = 45`, `hold #5`, `approve all except #2`.

## Record the user's decision
Map their reply onto the latest `pricing/review-*.json`:
```bash
python3 -I .claude/skills/pricing-proposal/scripts/pricing.py apply --review pricing/review-<stamp>.json \
   [--accept-all] [--accept 1 4] [--set 3=45 CGC-4402325019=29.99] [--hold 5]
```
`--set` and `--hold` win over `--accept-all`. Approved items get `pricing.final` and status `priced`; held items get `hold`. Anything not mentioned stays as it was and is listed as undecided; ask about those. If the reply is ambiguous (e.g. a number not in the report), ask before applying.

Then commit and push:
```bash
git add -A photos pricing index.csv README.md && git commit -m "Pricing: <n> approved" && git fetch origin main && git rebase origin/main && git push origin HEAD:main
```
Offer the next step: build the bulk upload file for the priced items.

## Rules
- Never set `pricing.final` without the user's approval in chat.
- Re-pricing an item that's already exported/uploaded is fine, but say the eBay listing must be revised separately.
