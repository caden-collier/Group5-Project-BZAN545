# Milestone 06 - Product Migration Response

This workflow is independent of the weather enrichment work in Milestone 05.
It snapshots both product systems, creates an auditable draft crosswalk, reports
match-status counts, and generates a short Canvas-ready response.

## Confirmed cutover in orders

The preserved source files show the product-key migration directly:

- `data/bronze/orders/2026-07-27/orders.csv`: 98 rows using `product_id`
- `data/bronze/orders/2026-07-28/orders.csv`: 101 rows using `new_product_id`

The order ingestion validator now accepts either schema and reports which key it
found. This preserves the historical files while allowing post-migration orders
to continue through the same ingestion process.

## Build the deliverables

1. Place the existing gitignored `credentials.json` in the repository root.
   It must contain `username` and `password` keys. Never commit this file.
2. Snapshot both source tables:

   ```text
   python tools/export_product_sources.py --snapshot-date 2026-07-29
   ```

3. Build the crosswalk, counts, schema comparison, and Canvas response:

   ```text
   python tools/build_product_crosswalk.py data/bronze/products/2026-07-29/products.csv data/bronze/products/2026-07-29/new_products.csv
   ```

The generated milestone evidence is:

- `data/silver/product_crosswalk.csv`
- `data/silver/product_crosswalk_summary.json`
- `docs/milestones/milestone_06/Canvas_Submission.md`

## Match-status policy

- `matched_exact`: exact normalized name plus strong supporting similarity
- `matched_high_confidence`: strong multi-field match with a clear runner-up gap
- `review_ambiguous`: the two leading candidates are too close
- `review_low_confidence`: plausible, but below the automatic threshold
- `review_duplicate_candidate`: multiple new products point to one legacy row
- `unmatched`: no sufficiently similar legacy candidate

No review status is silently treated as a completed mapping. The crosswalk keeps
the leading candidate, runner-up, scores, compared fields, and a review note so
the group can resolve product splits, collisions, and uncertain renames.
