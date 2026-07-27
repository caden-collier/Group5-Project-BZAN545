import json
import pandas as pd
import sqlalchemy
from sqlalchemy import text


# ---------------------------------------------------------
# 1. Load local orders CSV
# ---------------------------------------------------------

orders = pd.read_csv(
    "data/raw/orders/2026-07-12/orders.csv"
)


# ---------------------------------------------------------
# 2. Function to create a MySQL connection
# ---------------------------------------------------------

def create_mysql_utk_engine(
    database,
    username,
    password,
    host="mariadb-compx0.oit.utk.edu",
    port=3306,
):
    connection_string = sqlalchemy.URL.create(
        "mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )

    return sqlalchemy.create_engine(connection_string)


# ---------------------------------------------------------
# 3. Load credentials
# ---------------------------------------------------------

with open("credentials.json") as file:
    credentials = json.load(file)


# ---------------------------------------------------------
# 4. Connect to the source database
#    This database contains stores and products
# ---------------------------------------------------------

source_engine = create_mysql_utk_engine(
    database="aspannba_bzan545",
    username=credentials["username"],
    password=credentials["password"],
)


# Confirm source database connection
source_database_check = pd.read_sql(
    "SELECT DATABASE() AS current_database;",
    source_engine,
)

display(source_database_check)


# Show source database tables
source_tables = pd.read_sql(
    "SHOW TABLES;",
    source_engine,
)

display(source_tables)


# ---------------------------------------------------------
# 5. Pull the full stores and products tables
#    from aspannba_bzan545
# ---------------------------------------------------------

stores = pd.read_sql(
    "SELECT * FROM stores;",
    source_engine,
)

products = pd.read_sql(
    "SELECT * FROM products;",
    source_engine,
)


display(stores.head())
display(products.head())


# Get source-table row counts
source_counts = pd.read_sql(
    """
    SELECT
        'stores' AS table_name,
        COUNT(*) AS row_count
    FROM stores

    UNION ALL

    SELECT
        'products' AS table_name,
        COUNT(*) AS row_count
    FROM products;
    """,
    source_engine,
)

display(source_counts)


# ---------------------------------------------------------
# 6. Review join columns
# ---------------------------------------------------------

print("Orders columns:")
print(orders.columns.tolist())

print("\nStores columns:")
print(stores.columns.tolist())

print("\nProducts columns:")
print(products.columns.tolist())


# ---------------------------------------------------------
# 7. Join orders to stores and products
# ---------------------------------------------------------

orders_with_stores = pd.merge(
    orders,
    stores,
    on="store_id",
    how="inner",
)

orders_with_stores_and_products = pd.merge(
    orders_with_stores,
    products,
    on="product_id",
    how="inner",
)

display(
    orders_with_stores_and_products.head(10)
)


# ---------------------------------------------------------
# 8. Connect to your destination database
# ---------------------------------------------------------

destination_engine = create_mysql_utk_engine(
    database="ltk528_bzan545",
    username=credentials["username"],
    password=credentials["password"],
)


# Confirm destination database connection
with destination_engine.connect() as connection:
    current_database = connection.execute(
        text("SELECT DATABASE();")
    ).scalar()

print("Currently connected to:", current_database)


if current_database != "ltk528_bzan545":
    raise RuntimeError(
        f"Connected to {current_database}, "
        "not ltk528_bzan545. "
        "Check the database name."
    )


# ---------------------------------------------------------
# 9. Write stores into ltk528_bzan545
# ---------------------------------------------------------

stores.to_sql(
    name="stores",
    con=destination_engine,
    if_exists="replace",
    index=False,
    chunksize=1000,
    method="multi",
)

print(
    "The stores table was saved successfully "
    "to ltk528_bzan545."
)


# ---------------------------------------------------------
# 10. Write products into ltk528_bzan545
# ---------------------------------------------------------

products.to_sql(
    name="products",
    con=destination_engine,
    if_exists="replace",
    index=False,
    chunksize=1000,
    method="multi",
)

print(
    "The products table was saved successfully "
    "to ltk528_bzan545."
)


# ---------------------------------------------------------
# 11. Write joined table into ltk528_bzan545
# ---------------------------------------------------------

orders_with_stores_and_products.to_sql(
    name="orders_with_stores_and_products",
    con=destination_engine,
    if_exists="replace",
    index=False,
    chunksize=1000,
    method="multi",
)

print(
    "The orders_with_stores_and_products table "
    "was saved successfully to ltk528_bzan545."
)


# ---------------------------------------------------------
# 12. Verify that all three tables now exist
# ---------------------------------------------------------

updated_tables = pd.read_sql(
    "SHOW TABLES;",
    destination_engine,
)

display(updated_tables)


# ---------------------------------------------------------
# 13. Preview the copied tables
# ---------------------------------------------------------

stores_preview = pd.read_sql(
    """
    SELECT *
    FROM stores
    LIMIT 5;
    """,
    destination_engine,
)

products_preview = pd.read_sql(
    """
    SELECT *
    FROM products
    LIMIT 5;
    """,
    destination_engine,
)

joined_preview = pd.read_sql(
    """
    SELECT *
    FROM orders_with_stores_and_products
    LIMIT 10;
    """,
    destination_engine,
)

display(stores_preview)
display(products_preview)
display(joined_preview)


# ---------------------------------------------------------
# 14. Verify database row counts
# ---------------------------------------------------------

database_counts = pd.read_sql(
    """
    SELECT
        'stores' AS table_name,
        COUNT(*) AS row_count
    FROM stores

    UNION ALL

    SELECT
        'products' AS table_name,
        COUNT(*) AS row_count
    FROM products

    UNION ALL

    SELECT
        'orders_with_stores_and_products' AS table_name,
        COUNT(*) AS row_count
    FROM orders_with_stores_and_products;
    """,
    destination_engine,
)

display(database_counts)


# ---------------------------------------------------------
# 15. Compare DataFrame and database row counts
# ---------------------------------------------------------

expected_counts = {
    "stores": len(stores),
    "products": len(products),
    "orders_with_stores_and_products":
        len(orders_with_stores_and_products),
}

for table_name, dataframe_count in expected_counts.items():

    database_count = int(
        database_counts.loc[
            database_counts["table_name"] == table_name,
            "row_count",
        ].iloc[0]
    )

    print(f"\nTable: {table_name}")
    print("DataFrame rows:", dataframe_count)
    print("Database rows:", database_count)

    if dataframe_count == database_count:
        print("Row counts match.")
    else:
        print("Warning: Row counts do not match.")


# ---------------------------------------------------------
# 16. Join-key and grain notes
# ---------------------------------------------------------

# store_id joins orders to stores.
# product_id joins orders to products.

# Stores has one row per store and uses store_id
# as its join key.

# Products has one row per product and uses product_id
# as its join key.

# Orders has one row per order line.


# ---------------------------------------------------------
# 17. Grant group members read-only access
# ---------------------------------------------------------

group_users = [
    "iskelly",
    "rvq266",
    "rrodri21",
    "ccoll108",
    "aspannba",
]

with destination_engine.begin() as connection:

    for group_user in group_users:

        grant_statement = text(
            f"""
            GRANT SELECT
            ON `ltk528_bzan545`.*
            TO '{group_user}'@'%.utk.edu'
            """
        )

        connection.execute(grant_statement)

        print(
            f"SELECT permission granted to {group_user}."
        )


# ---------------------------------------------------------
# 18. Final test
# ---------------------------------------------------------

final_test = pd.read_sql(
    """
    SELECT
        o.order_id,
        o.store_id,
        o.product_id,
        s.store_name,
        p.product_name
    FROM orders_with_stores_and_products AS o
    LEFT JOIN stores AS s
        ON o.store_id = s.store_id
    LEFT JOIN products AS p
        ON o.product_id = p.product_id
    LIMIT 5;
    """,
    destination_engine,
)

display(final_test)
