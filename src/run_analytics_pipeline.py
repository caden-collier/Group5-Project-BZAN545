"""Run the separate analytics stages in order."""

from bzan545.analytics.aggregate_sales import (
    build_daily_sales,
)
from bzan545.analytics.clean_orders import (
    build_clean_orders,
)
from bzan545.analytics.enrich_weather import (
    enrich_daily_sales,
)
from bzan545.analytics.reconcile_products import (
    reconcile_order_products,
)
from bzan545.analytics.validate_sales import (
    validate_and_publish,
)


def main() -> None:
    """Run each independent analytics stage."""

    print("\n1. Cleaning raw orders")
    build_clean_orders()

    print("\n2. Reconciling products")
    reconcile_order_products()

    print("\n3. Aggregating daily sales")
    build_daily_sales()

    print("\n4. Joining stores and weather")
    enrich_daily_sales()

    print("\n5. Validating and publishing")
    validate_and_publish()


if __name__ == "__main__":
    main()