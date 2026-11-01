# Bulk upload check: ⚠️ PASS WITH WARNINGS

**File:** `2026-11-01_comics-259104_101.xlsx`  
**Listings:** 101  
**Mode:** strict (project standard enforced)  
**Errors:** 0 · **Warnings:** 124 · **Notes:** 206

Safe to upload. Review the warnings; they won't block eBay but may hurt the listing.

## Warnings

| Rows | SKU | Column | Problem | Fix |
|---|---|---|---|---|
| 5, 6, 7, 8, 9, 10, 11, 12 +93 more | CBCS-20-4052170-007 +100 | Shipping service 1 option | Legacy shipping columns are mixed with return/payment policies. eBay's template says not to use these columns once you're on business policies; the row may fail or get an auto-made policy. | Create a shipping policy with this rate on eBay, download a fresh template, and use Shipping profile name. |
| 9 | CGC-4390247010 | C:Character | 'Puma' differs from eBay's value only by case. | Did you mean 'PUMA'? |
| 26 | CGC-4402565025 | C:Artist/Writer | 'Marc McLaurin' differs from eBay's value only by case. | Did you mean 'Marc Mclaurin'? |
| 38 | CGC-4318030023 | C:Artist/Writer | 'Frank McLaughlin' differs from eBay's value only by case. | Did you mean 'Frank Mclaughlin'? |
| 43 |  | Title | 'Icon #1 CGC 9.2 Collector's Edition 1st Icon & Rocket Milest' appears on 4 rows (43, 44, 45, 46). | Identical titles are allowed but make listings harder to tell apart. |
| 48 | CGC-3803292017 | C:Artist/Writer | 'Don McGregor' differs from eBay's value only by case. | Did you mean 'Don Mcgregor'? |
| 55, 56 | CGC-4402566017 +1 | C:Character | 'Pitt' differs from eBay's value only by case. | Did you mean 'PITT'? |
| 67 |  | Title | 'Punisher #77 CGC 8.5 White Pages Survival Part 1 Val Mayerik' appears on 2 rows (67, 68). | Identical titles are allowed but make listings harder to tell apart. |
| 79 | CGC-4402565008 | C:Era | Year 1991 is outside Modern Age (1992-Now). |  |
| 90 |  | Title | 'Uncanny X-Men #304 CGC 9.6 White Pages Magneto Hologram Fata' appears on 2 rows (90, 91). | Identical titles are allowed but make listings harder to tell apart. |
| 93 |  | Title | 'Venom: Funeral Pyre #1 CGC 9.6 White Pages Holo-Grafx Cover ' appears on 2 rows (93, 94). | Identical titles are allowed but make listings harder to tell apart. |
| 95, 96, 97, 98, 99, 100, 101, 102 +1 more | CGC-4402325001 +8 | C:Artist/Writer | 'Sam de la Rosa' differs from eBay's value only by case. | Did you mean 'Sam De La Rosa'? |
| 95 |  | Title | 'Venom: Lethal Protector #1 CGC 9.0 White Pages Red Holo-Graf' appears on 2 rows (95, 96). | Identical titles are allowed but make listings harder to tell apart. |
| 97 |  | Title | 'Venom: Lethal Protector #1 CGC 9.4 White Pages Red Holo-Graf' appears on 2 rows (97, 98). | Identical titles are allowed but make listings harder to tell apart. |
| 99 |  | Title | 'Venom: Lethal Protector #1 CGC 9.6 White Pages Red Holo-Graf' appears on 4 rows (99, 100, 101, 102). | Identical titles are allowed but make listings harder to tell apart. |

## Notes

| Rows | SKU | Column | Problem | Fix |
|---|---|---|---|---|
| 5, 6, 7, 8, 9, 10, 11, 12 +93 more | CBCS-20-4052170-007 +100 | Action | Draft: rows go to your Drafts folder (not this template's own dropdown value). Confirm the upload results show them as drafts. |  |
| 5, 6, 7, 8, 9, 10, 11, 12 +93 more | CBCS-20-4052170-007 +100 | Location | Location is empty. Fine for a Draft, required before the draft can go live. |  |
| 52 | CGC-3918508010 | C:Series Title | 'Nine Rings of Wu-Tang' is a custom value (not in eBay's list); matching eBay's name helps search. |  |
| 78 | CGC-4402326010 | C:Series Title | 'Spider-Man: Carnage' is a custom value (not in eBay's list); matching eBay's name helps search. |  |
| 104, 105 | CGC-4395354008 +1 | C:Series Title | 'Wolverine' is a custom value (not in eBay's list); matching eBay's name helps search. |  |

## Field coverage

| Column | Tier | Filled |
|---|---|---|
| Action | required | 101/101 |
| Category ID | required | 101/101 |
| Category name | required | 101/101 |
| Condition ID | required | 101/101 |
| Description | required | 101/101 |
| Duration | required | 101/101 |
| Format | required | 101/101 |
| Item photo URL | required | 101/101 |
| Location | required | 0/101 |
| Quantity | required | 101/101 |
| Start price | required | 101/101 |
| Title | required | 101/101 |
| Max dispatch time | conditional | 101/101 |
| Payment profile name | conditional | 101/101 |
| Return profile name | conditional | 101/101 |
| Shipping service 1 cost | conditional | 101/101 |
| Shipping service 1 option | conditional | 101/101 |
| Best Offer Enabled | standard | 101/101 |
| C:Artist/Writer | standard | 101/101 |
| C:Certification Number | standard | 101/101 |
| C:Character | standard | 101/101 |
| C:Era | standard | 101/101 |
| C:Format | standard | 101/101 |
| C:Genre | standard | 101/101 |
| C:Grade | standard | 101/101 |
| C:Professional Grader | standard | 101/101 |
| C:Publication Year | standard | 101/101 |
| C:Publisher | standard | 101/101 |
| C:Series Title | standard | 101/101 |
| C:Tradition | standard | 101/101 |
| C:Type | standard | 101/101 |
| Custom label (SKU) | standard | 101/101 |
| C:Superhero Team | recommended | 5/101 |
| Shipping service 1 priority | optional | 101/101 |
