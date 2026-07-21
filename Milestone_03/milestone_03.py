import json
import pandas as pd
import sqlalchemy

orders = pd.read_csv("data/raw/orders/2026-07-12/orders.csv")

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


# Load credentials
with open("credentials.json") as file:
    credentials = json.load(file)

# Connect to the team database
engine = create_mysql_utk_engine(
    database="aspannba_bzan545",
    username=credentials["username"],
    password=credentials["password"],
)

# Confirm the database connection
database_check = pd.read_sql(
    "SELECT DATABASE() AS current_database;",
    engine,
)
display(database_check)

# Show all tables
tables = pd.read_sql("SHOW TABLES;", engine)
display(tables)

# Preview reference tables
stores_preview = pd.read_sql(
    "SELECT * FROM stores LIMIT 5;",
    engine,
)

products_preview = pd.read_sql(
    "SELECT * FROM products LIMIT 5;",
    engine,
)

display(stores_preview)
display(products_preview)

# Get row counts
counts = pd.read_sql(
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
    engine,
)

display(counts)



####joining


print(orders.columns.tolist())


print(stores_preview.columns.tolist())


print(products_preview.columns.tolist())

# Load the full stores and products tables
stores = pd.read_sql("SELECT * FROM stores;", engine)
products = pd.read_sql("SELECT * FROM products;", engine)


orders_with_stores = pd.merge(
    orders,
    stores,
    on="store_id",
)


orders_with_stores_and_products = pd.merge(
    orders_with_stores,
    products,
    on="product_id",
)


display(orders_with_stores_and_products.head(10))


#store_id joins orders to stores
#product_id joins orders to products


#Stores has one row per store and uses store_id as the join key.

#Products has one row per product and uses product_id as the join key.

#Orders has one row per order line.