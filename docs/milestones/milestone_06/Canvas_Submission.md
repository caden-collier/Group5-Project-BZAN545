# Milestone 06 - Product Migration Response

## Source and schema changes

We loaded `data/bronze/products/2026-07-29/products.csv` (80 rows) and `data/bronze/products/2026-07-29/new_products.csv` (80 rows). The daily orders feed also changed its join key from `product_id` through 2026-07-27 to `new_product_id` beginning 2026-07-28.

- Columns removed/renamed from the legacy table: `base_price, brand, category, margin_rate, product_id, product_name, subcategory`
- Columns added in the migrated table: `brand_name, class, department, gross_margin, item_name, msrp, new_product_id`
- Columns retained in both tables: `active, launch_date`

Observed descriptive-value changes include:
- `brand` legacy-only values: `Blue Ridge Works, Moss & Mile, Rocky Top Outfitters`; new-only values: `Blue Ridge Outdoor Works, Moss and Mile, RTO House Brand`
- `category` legacy-only values: `emergency, hydration, outerwear`; new-only values: `apparel, drinkware, preparedness`
- `subcategory` legacy-only values: `battery pack, rain shell`; new-only values: `power storage, waterproof outerwear`

## Draft crosswalk sample

| New ID | New product | Proposed legacy ID | Status | Score |
|---|---|---|---|---:|
| NP5001 | SummitRunner Lightweight Jacket 200 | P1001 | matched_exact | 0.7675 |
| NP5002 | RidgeRover Mid Trail Shoes 201 | P1002 | matched_exact | 0.9997 |
| NP5003 | CreekRambler 2P Camp Chair 202 | P1003 | matched_exact | 0.9995 |
| NP5004 | Storm Nomad Compact Cooler 203 | P1004 | matched_exact | 0.9938 |
| NP5005 | EmberRunner Storm Kit Battery Pack 204 | P1005 | matched_exact | 0.8343 |

## Match progress

- `matched_exact`: 62
- `review_ambiguous`: 9
- `review_duplicate_candidate`: 8
- `review_low_confidence`: 1

## Ambiguous or unresolved decision

`NP5073` (FieldRunner Battery Pack), `NP5077` (FieldRunner Battery Pack Alt) both propose legacy product `P1077`. This could represent a deliberate product split, an alternate SKU, or a duplicate. We are keeping both rows in `review_duplicate_candidate` until the business rule for allocating historical sales is confirmed.

## Repository paths

- Crosswalk: `data/silver/product_crosswalk.csv`
- Counts/schema summary: `data/silver/product_crosswalk_summary.json`
- Historical source export: `docs/milestones/milestone_06/export_product_sources.py`
- Crosswalk builder: `src/bzan545/crosswalk.py`
- Order ingestion: `src/bzan545/orders.py`
