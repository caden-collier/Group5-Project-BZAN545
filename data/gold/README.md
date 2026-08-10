# Gold layer

The gold layer contains the final analytics-ready daily sales and weather
dataset used for reporting:

- `group5_rto_daily_sales_weather.csv`
- `daily_sales_validation.json`

## Table grain and contents

One row in `group5_rto_daily_sales_weather.csv` represents one canonical
product at one store on one order date. The unique grain is:

- `order_date`
- `store_id`
- `canonical_product_id`

The table combines daily order counts, units sold, and net sales with canonical
product attributes, store details, and cached Open-Meteo weather. Store data is
joined on `store_id`; weather is joined on `store_id` and `order_date`.

The same dataset is published to MariaDB table
`group5_rto_daily_sales_weather` for the Tableau dashboard.

## Validation

`daily_sales_validation.json` records the checks performed before and after
publishing. The build verifies:

- no duplicate rows at the declared grain
- no missing store, weather, product-name, or product-attribute joins
- preservation of silver units and net sales after aggregation
- agreement between the gold CSV and MariaDB row counts

The current validated snapshot includes 2,852 silver order lines aggregated to
2,586 gold rows through `2026-08-09`. It preserves 5,608 units and
`$1,057,816.16` in net sales, has zero missing joins or product attributes, and
has the same 2,586 rows in the CSV and SQL table.

The pipeline stops before publishing when a prepublication validation fails.
Gold is currently published with a full table replacement rather than an
incremental update.
