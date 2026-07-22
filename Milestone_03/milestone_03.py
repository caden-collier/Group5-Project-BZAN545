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


from sqlalchemy import create_engine, text


engine = create_engine(
    "mysql+pymysql://ltk528:Pink092003!!@mariadb-compx0.oit.utk.edu/ltk528_bzan545"
)


with engine.connect() as connection:
    current_database = connection.execute(
        text("SELECT DATABASE();")
    ).scalar()

print("Currently connected to:", current_database)

if current_database != "ltk528_bzan545":
    raise RuntimeError(
        f"Connected to {current_database}, not ltk_528. "
        "Check the database name in the connection string."
    )


orders_with_stores_and_products.to_sql(
    name="orders_with_stores_and_products",
    con=engine,
    if_exists="replace",
    index=False,
    chunksize=1000,
    method="multi",
)

print(
    "The orders_with_stores_and_products table "
    "was saved successfully to ltk_528."
)


new_table_preview = pd.read_sql(
    """
    SELECT *
    FROM orders_with_stores_and_products
    LIMIT 10;
    """,
    engine,
)

display(new_table_preview)



updated_tables = pd.read_sql(
    "SHOW TABLES;",
    engine,
)

display(updated_tables)




new_table_count = pd.read_sql(
    """
    SELECT COUNT(*) AS row_count
    FROM orders_with_stores_and_products;
    """,
    engine,
)

display(new_table_count)




dataframe_row_count = len(orders_with_stores_and_products)
database_row_count = int(new_table_count.loc[0, "row_count"])

print("DataFrame rows:", dataframe_row_count)
print("Database table rows:", database_row_count)

if dataframe_row_count == database_row_count:
    print("Row counts match. The table was copied successfully.")
else:
    print("Warning: The DataFrame and database row counts do not match.")




#store_id joins orders to stores
#product_id joins orders to products


#Stores has one row per store and uses store_id as the join key.

#Products has one row per product and uses product_id as the join key.

#Orders has one row per order line.


from sqlalchemy import text

with engine.begin() as connection:
    connection.execute(
        text("""
            GRANT ALL PRIVILEGES
            ON `ltk528_bzan545`.*
            TO 'iskelly'@'%.utk.edu'
        """)
    )


with engine.begin() as connection:
    connection.execute(
        text("""
            GRANT ALL PRIVILEGES
            ON `ltk528_bzan545`.*
            TO 'rvq266'@'%.utk.edu'
        """)
    )



with engine.begin() as connection:
    connection.execute(
        text("""
            GRANT ALL PRIVILEGES
            ON `ltk528_bzan545`.*
            TO 'rrodri21'@'%.utk.edu'
        """)
    )


with engine.begin() as connection:
    connection.execute(
        text("""
            GRANT ALL PRIVILEGES
            ON `ltk528_bzan545`.*
            TO 'ccoll108'@'%.utk.edu'
        """)
    )