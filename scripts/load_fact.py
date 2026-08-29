import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Load and clean data (same as before)
df = pd.read_csv("data/Amazon Sale Report.csv", low_memory=False)
df = df.dropna(subset=["Order ID", "Amount"])
df["Date"] = pd.to_datetime(df["Date"], format="%m-%d-%y", errors="coerce")
df = df.dropna(subset=["Date"])

# Load dimension tables back from DB to map IDs
dim_region = pd.read_sql("SELECT region_id, city, state, country FROM dim_region", engine)
dim_category = pd.read_sql("SELECT category_id, category_name FROM dim_category", engine)
dim_date = pd.read_sql("SELECT date_id, full_date FROM dim_date", engine)

# Merge to get region_id
df = df.merge(dim_region, left_on=["ship-city", "ship-state", "ship-country"],
               right_on=["city", "state", "country"], how="left")

# Merge to get category_id
df = df.merge(dim_category, left_on="Category", right_on="category_name", how="left")

# Merge to get date_id
dim_date["full_date"] = pd.to_datetime(dim_date["full_date"])
df = df.merge(dim_date, left_on="Date", right_on="full_date", how="left")

# Build fact table
fact_df = pd.DataFrame({
    "order_id": df["Order ID"],
    "date_id": df["date_id"],
    "region_id": df["region_id"],
    "category_id": df["category_id"],
    "status": df["Status"],
    "sales_channel": df["Sales Channel "],
    "qty": df["Qty"],
    "amount": df["Amount"],
    "b2b": df["B2B"]
})

fact_df = fact_df.dropna(subset=["date_id", "region_id"])

fact_df.to_sql("fact_sales", engine, if_exists="append", index=False)

print(f"Fact table loaded: {len(fact_df)} rows inserted.")