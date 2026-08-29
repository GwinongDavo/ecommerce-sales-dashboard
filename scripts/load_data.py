import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Load and clean data
df = pd.read_csv("data/Amazon Sale Report.csv", low_memory=False)

# Drop rows with no order ID or amount (junk rows)
df = df.dropna(subset=["Order ID", "Amount"])

# Parse date
df["Date"] = pd.to_datetime(df["Date"], format="%m-%d-%y", errors="coerce")
df = df.dropna(subset=["Date"])

# --- dim_region ---
region_df = df[["ship-city", "ship-state", "ship-country"]].drop_duplicates()
region_df.columns = ["city", "state", "country"]
region_df = region_df.dropna(subset=["city", "state"])
region_df.to_sql("dim_region", engine, if_exists="append", index=False)

# --- dim_category ---
category_df = df[["Category"]].drop_duplicates().dropna()
category_df.columns = ["category_name"]
category_df.to_sql("dim_category", engine, if_exists="append", index=False)

# --- dim_date ---
date_df = df[["Date"]].drop_duplicates().dropna()
date_df["day"] = date_df["Date"].dt.day
date_df["month"] = date_df["Date"].dt.month
date_df["quarter"] = date_df["Date"].dt.quarter
date_df["year"] = date_df["Date"].dt.year
date_df.columns = ["full_date", "day", "month", "quarter", "year"]
date_df.to_sql("dim_date", engine, if_exists="append", index=False)

print("Dimension tables loaded successfully.")
print(f"Regions: {len(region_df)}, Categories: {len(category_df)}, Dates: {len(date_df)}")