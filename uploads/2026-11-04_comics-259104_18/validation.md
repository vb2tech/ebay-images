# Bulk upload check: ⚠️ PASS WITH WARNINGS

**File:** `2026-11-04_comics-259104_18.xlsx`  
**Listings:** 18  
**Mode:** strict (project standard enforced)  
**Errors:** 0 · **Warnings:** 25 · **Notes:** 36

Safe to upload. Review the warnings; they won't block eBay but may hurt the listing.

## Warnings

| Rows | SKU | Column | Problem | Fix |
|---|---|---|---|---|
| 5 | CGC-4402566017 | C:Character | 'Pitt' differs from eBay's value only by case. | Did you mean 'PITT'? |
| 5, 6, 7, 8, 9, 10, 11, 12 +10 more | CGC-4395354006 +17 | Shipping service 1 option | Legacy shipping columns are mixed with return/payment policies. eBay's template says not to use these columns once you're on business policies; the row may fail or get an auto-made policy. | Create a shipping policy with this rate on eBay, download a fresh template, and use Shipping profile name. |
| 8 |  | Title | 'Punisher #77 CGC 8.5 White Pages Survival Part 1 Val Mayerik' appears on 2 rows (8, 9). | Identical titles are allowed but make listings harder to tell apart. |
| 18 | CGC-4402565008 | C:Era | Year 1991 is outside Modern Age (1992-Now). |  |
| 20, 21, 22 | CGC-4402325001 +2 | C:Artist/Writer | 'Sam de la Rosa' differs from eBay's value only by case. | Did you mean 'Sam De La Rosa'? |
| 20 |  | Title | 'Venom: Lethal Protector #1 CGC 9.0 White Pages Red Holo-Graf' appears on 2 rows (20, 21). | Identical titles are allowed but make listings harder to tell apart. |

## Notes

| Rows | SKU | Column | Problem | Fix |
|---|---|---|---|---|
| 5, 6, 7, 8, 9, 10, 11, 12 +10 more | CGC-4395354006 +17 | Action | Draft: rows go to your Drafts folder (not this template's own dropdown value). Confirm the upload results show them as drafts. |  |
| 5, 6, 7, 8, 9, 10, 11, 12 +10 more | CGC-4395354006 +17 | Location | Location is empty. Fine for a Draft, required before the draft can go live. |  |

## Field coverage

| Column | Tier | Filled |
|---|---|---|
| Action | required | 18/18 |
| Category ID | required | 18/18 |
| Category name | required | 18/18 |
| Condition ID | required | 18/18 |
| Description | required | 18/18 |
| Duration | required | 18/18 |
| Format | required | 18/18 |
| Item photo URL | required | 18/18 |
| Location | required | 0/18 |
| Quantity | required | 18/18 |
| Start price | required | 18/18 |
| Title | required | 18/18 |
| Max dispatch time | conditional | 18/18 |
| Payment profile name | conditional | 18/18 |
| Return profile name | conditional | 18/18 |
| Shipping service 1 cost | conditional | 18/18 |
| Shipping service 1 option | conditional | 18/18 |
| Best Offer Enabled | standard | 18/18 |
| C:Artist/Writer | standard | 18/18 |
| C:Certification Number | standard | 18/18 |
| C:Character | standard | 18/18 |
| C:Era | standard | 18/18 |
| C:Format | standard | 18/18 |
| C:Genre | standard | 18/18 |
| C:Grade | standard | 18/18 |
| C:Professional Grader | standard | 18/18 |
| C:Publication Year | standard | 18/18 |
| C:Publisher | standard | 18/18 |
| C:Series Title | standard | 18/18 |
| C:Tradition | standard | 18/18 |
| C:Type | standard | 18/18 |
| Custom label (SKU) | standard | 18/18 |
| C:Superhero Team | recommended | 0/18 |
| Shipping service 1 priority | optional | 18/18 |
