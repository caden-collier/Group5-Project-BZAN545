# Group5-Project-BZAN545
Repository for Final Project, Group 5 BZAN-545

## Daily orders automation

GitHub Actions runs the existing orders-preservation code twice each evening:
once at approximately 10:30 PM Eastern and once an hour later as a retry.
Each valid daily file is saved under `data/raw/orders/YYYY-MM-DD/` with its
SHA-256 checksum and committed by the GitHub Actions bot. Repeated runs are
safe and do not overwrite an earlier capture.

Validation recognizes both exact schemas already present in the raw history:
the original `product_id` column and the newer `new_product_id` column.

Run the same validation locally without writing data:

```powershell
python src/preserve_daily_orders.py --dry-run
```

Run the offline safety tests:

```powershell
python -m unittest discover -s tests -v
```
