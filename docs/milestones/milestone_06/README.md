# Milestone 06 - Product Migration Response

This workflow is independent of the weather enrichment work in Milestone 05.
It snapshots both product systems, creates a reviewable draft crosswalk, and
reports match-status counts.

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
   python docs/milestones/milestone_06/export_product_sources.py --snapshot-date 2026-07-29
   ```

3. Build the crosswalk and status summary:

   ```text
   bzan545 crosswalk
   ```

The generated milestone evidence is:

- `data/silver/product_crosswalk.csv`
- `data/silver/product_crosswalk_summary.json`
- `docs/milestones/milestone_06/Canvas_Submission.md` is the retained historical
  submission; rebuilding the crosswalk does not rewrite it.

## Match-status policy

- `exact_name_match`: normalized product names match and the proposed legacy ID
  is not shared with another new product.
- `review_required`: the name is not exact or multiple new products propose the
  same legacy product.

Non-exact candidates are ranked using product name (70%), brand (20%), and price
(10%). The crosswalk keeps the leading candidate, runner-up, scores, and a review
note so the group can resolve product splits, collisions, and uncertain renames.
