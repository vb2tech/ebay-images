# eBay templates (listing groups)

Each kind of item we sell gets a **listing group**: one eBay category template plus our rules for filling it. Groups are registered in `templates/registry.json`. Today there is one:

| Group | Category | Template | Status |
|---|---|---|---|
| `comics-259104` | Comics & Graphic Novels (259104) | `templates/comics-259104/template.xlsx` (downloaded 2026-10-28) | Active. **Comics only.** |

## Getting a template from eBay

1. Seller Hub → **Reports** → **Uploads** → **Download template**.
2. Choose the category (or several — see below) and download the .xlsx.
3. eBay bakes your current business policies, the category's condition IDs and its item-specific dropdowns into the file. **Re-download whenever you add or rename a shipping/return/payment policy**, otherwise the new policy won't be in the dropdown and the validator will flag it.

## Adding a new group (e.g. trading cards)

1. Download the template for the new category.
2. Make `templates/<group>/` with `template.xlsx`, `field_rules.json` (copy the comics one and adjust columns/tiers; the Aspects sheet lists the category's item specifics and their REQUIRED/PREFERRED/OPTIONAL level) and `listing_defaults.json`.
3. Add the group to `templates/registry.json` with its category ID(s).
4. Write `docs/templates/<group>-fields.md` (required vs optional for that category).
5. Items ingested for that group get `"template": "<group>"` in their `listing.json`; the bulk-upload builder groups items by template and makes one file per group.

Trading cards will differ a lot: eBay uses condition **4000 Ungraded / 2750 Graded** with *condition descriptors* (grader, grade, cert) instead of a plain condition ID, which the comics template doesn't have.

## One template for everything?

eBay's download page lets you pick **several categories in one template**; the file then lists all of them on the Categories sheet, and each row picks its category. A combined template could hold comics and cards in one upload, but each category still has its own item-specific columns and condition rules, so the file gets wide. Plan: keep one group per category until a second group exists, then try a combined download and, if it works cleanly, register it as a group with several `category_ids`. The validator already reads categories, conditions and aspects from whatever template the file came from.
