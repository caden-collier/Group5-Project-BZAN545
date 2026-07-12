# Milestone 02 - First Orders Captured

## Capture details

- Order date represented: `2026-07-12`
- Rows captured: `104`
- Columns captured: `9`
- Raw file: `data/raw/orders/2026-07-12/orders.csv`
- Inspection script: `src/inspect_orders.py`

## Raw-file storage convention

Future order files will be preserved unchanged under
`data/raw/orders/YYYY-MM-DD/orders.csv`, where `YYYY-MM-DD` is the date
represented by the orders in the source file. Each daily pull will be stored in
its own directory so an earlier raw file is never overwritten.

## Reproduce the inspection

From the repository root, run:

```text
python src/inspect_orders.py
```

The output reports the source path, row and column counts, column names, order
date, and the first three records. Paste that output or attach a small screenshot
to the Canvas milestone submission.

## Verified output

```text
File: data/raw/orders/2026-07-12/orders.csv
Rows: 104
Columns: 9
Column names: order_id, order_date, store_id, product_id, quantity, unit_price, discount_pct, sales_channel, loyalty_member
Order dates: 2026-07-12
```
