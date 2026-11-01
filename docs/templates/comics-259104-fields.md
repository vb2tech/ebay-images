# eBay bulk upload: what each listing needs

Category template: **Comics & Graphic Novels, category 259104** (Seller Hub → Reports → Uploads → Download template). The template copy lives at `templates/comics-259104/template.xlsx`; the machine-readable version of this page is `templates/comics-259104/field_rules.json`, which the bulk-upload-validator reads.

## How the file works

- Sheet **Listings**: rows 1–3 are `#INFO` rows, **row 4 is the header**, listings start at **row 5**. One row = one listing.
- Hidden sheets hold the dropdown lists the validator checks against: **Categories** (category + its condition IDs), **BusinessPolicy** (your saved shipping/return/payment policies, account-specific), **Aspects** (allowed item-specific values).
- Item specifics are columns that start with `C:`. Several values in one cell are separated by `|` (e.g. `Spider-Man|Venom`). Each value is at most **65 characters**.
- Photos: several URLs in one cell separated by `|`, **https only**, no spaces (use `%20`), must end in an image extension. Seller Hub's tooltip says 12 per listing; eBay's limit is 24. Max cell length 2,048.
- eBay's template has a font setting `openpyxl` can't load; edit the sheet XML directly (our scripts do) or read with `python-calamine`.

## Tier 1 — eBay required (bare minimum; upload fails without these)

| Column | Rule |
|---|---|
| `*Action(...)` | `Add` publishes live (only value in this template's dropdown). `Draft` sends to the Drafts folder; it comes from eBay's drafts template and is what the earlier pipeline used. |
| Category ID | `259104`. In the template it's a formula off Category name, so keep the cached value. |
| Category name | `/Collectibles/Comic Books & Memorabilia/Comics/Comics & Graphic Novels` |
| Title | ≤ 80 characters |
| Start price | Number, no currency symbol, ≤ 16 characters |
| Quantity | Whole number ≥ 1 (our slabs: 1) |
| Item photo URL | At least one valid https image URL |
| Condition ID | For 259104 only: `1000` Brand New, `2750` Like New, `4000` Very Good, `5000` Good, `6000` Acceptable. There is no "Graded" condition in this category; the grade lives in `C:Grade`. |
| Description | Non-empty, ≤ 32,765 characters, simple HTML, no scripts |
| Format | `FixedPrice` or `Auction` |
| Duration | `GTC` for FixedPrice; `1`, `3`, `5`, `7`, `10` for Auction |
| Location | `City, ST` (no postal code), ≤ 45 characters |
| Shipping | **Either** Shipping profile name (exact name from BusinessPolicy sheet) **or** Shipping service 1 option + cost + Max dispatch time. Never both. |
| Returns | **Either** Return profile name **or** Returns accepted option (+ within / refund / paid-by when returns are accepted). Never both. |
| Payment profile name | Required whenever business policies are used. |

## Tier 2 — project standard (our raised bar)

eBay marks every item specific in this category **PREFERRED** (none are REQUIRED), but a graded slab tells us most of them, so we require them for anything our skills generate. The validator treats these as errors in `--strict` mode.

| Column | How we fill it | Strict list? |
|---|---|---|
| Custom label (SKU) | `<Grader>-<cert>`, e.g. `CGC-4402325019`; unique; matches photo filenames | – |
| Best Offer Enabled | `1` | – |
| C:Series Title | eBay's list name where one matches (e.g. `Cable - Blood and Metal`) | free text OK |
| C:Character | main characters, `|`-separated | free text OK |
| C:Genre | `Superheroes` for capes | free text OK |
| C:Artist/Writer | writer, artists, cover artist, `|`-separated | free text OK |
| C:Publisher | full name: `Marvel Comics`, `DC Comics`, `Milestone Media`, `Image Comics` | free text OK |
| C:Publication Year | 4-digit year from the cover date | free text OK |
| C:Format | `Single Issue` (also limited series) or `Trade Paperback` | **yes** |
| C:Era | e.g. `Copper Age (1984-1991)`; must agree with the year | **yes** |
| C:Type | `Comic Book` (`Graphic Novel` for TPBs) | free text OK |
| C:Grade | e.g. `9.8 Near Mint/Mint`; must agree with the title | **yes** |
| C:Tradition | `US Comics` | free text OK |
| C:Professional Grader | `Certified Guaranty Company (CGC)`, `Comic Book Certification Service (CBCS)`, `Professional Grading Experts (PGX)`, `Professional Sports Authenticator (PSA)` | **yes** |
| C:Certification Number | cert number from the label; unique | – |

Plus consistency checks: Condition ID matches the grade (≥ 9.0 → 2750, 6.0–8.5 → 4000, 4.0–5.5 → 5000, < 4.0 → 6000), title mentions the grade, SKUs and certs are unique, photo URLs point at the image repo and the files exist.

## Tier 3 — recommended (fill when the book has it)

- **C:Superhero Team** — only for team books (Avengers, X-Men, Alpha Flight…).

## Tier 4 — optional

Schedule Time, Buy It Now price (auction only, ≥ 30% over start), Best Offer auto-accept / minimum price (below Start price), Immediate pay required, second shipping service.

## Extension item specifics (next candidates to promote)

eBay accepts these aspects for 259104 but they aren't columns in the template; they'd be added as extra `C:` columns. Promote them into Tier 2 once one upload with extra columns has gone through cleanly:
`C:Issue Number`, `C:Features` (First Character Appearance, Key Issue, Newsstand…), `C:Cover Artist`, `C:Language` (English), `C:Signed` (No), `C:Vintage`, `C:Unit of Sale` (Single Unit), `C:Variant Type`, `C:Universe` (Marvel (MCU) / DC Universe), `C:Style` (Color), `C:Country of Origin`, `C:Story Title`, `C:Intended Audience`.

## Not used

Relationship / Relationship details (variations), P:EPID, VideoID, ProductCompliancePolicyID, Regional ProductCompliancePolicies, and the EU product-safety block (Product Safety *, Regulatory Document Ids, Manufacturer *, Responsible Person 1 *). Only needed for variation listings or EU compliance.

## Raising the bar

When a field can be filled confidently for every book, move it to `"tier": "standard"` in `templates/comics-259104/field_rules.json` and add a dated line to `threshold_history`. The validator, the photo-ingest skill and the bulk-upload builder all read that file, so the new bar applies everywhere at once.

## Sources

- eBay, [Inventory onboarding guide (Seller Hub bulk listings)](https://pages.ebay.com/sh/reports/help/create-listings-bulk/)
- eBay, [Uploadable templates](https://pages.ebay.com/sh/reports/help/uploadable-file-feeds)
- eBay Developers, [NameValueListType (item specific value length)](https://developer.ebay.com/devzone/xml/docs/Reference/ebay/types/NameValueListType.html)
- eBay Developers, [Buy It Now rules](https://developer.ebay.com/api-docs/user-guides/static/trading-user-guide/buy-it-now.html)
- eBay Developers, [Picture URL knowledge base](https://developer.ebay.com/support/knowledge-base/1240)
- The template's own header tooltips, dropdowns and conditional formatting.
