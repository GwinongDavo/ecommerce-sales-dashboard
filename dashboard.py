import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

def get_config(key):
    value = os.getenv(key)
    if value:
        return value
    return st.secrets.get(key)

DB_HOST = get_config("DB_HOST")
DB_PORT = get_config("DB_PORT")
DB_NAME = get_config("DB_NAME")
DB_USER = get_config("DB_USER")
DB_PASSWORD = get_config("DB_PASSWORD")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

st.set_page_config(page_title="E-commerce Sales Dashboard", layout="wide")
st.title("E-commerce Sales Dashboard")

kpi_query = """
SELECT COUNT(*) AS total_orders, SUM(amount) AS total_revenue, AVG(amount) AS avg_order_value
FROM fact_sales
"""
kpis = pd.read_sql(kpi_query, engine).iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Total Orders", f"{int(kpis['total_orders']):,}")
col2.metric("Total Revenue", f"$ {kpis['total_revenue']:,.0f}")
col3.metric("Avg Order Value", f"$ {kpis['avg_order_value']:,.2f}")

st.divider()

region_query = """
SELECT r.state, SUM(f.amount) AS revenue, COUNT(*) AS orders
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
GROUP BY r.state
ORDER BY revenue DESC
LIMIT 15
"""
region_df = pd.read_sql(region_query, engine)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top States by Revenue")
    fig1 = px.bar(region_df, x="state", y="revenue", color="revenue")
    st.plotly_chart(fig1, use_container_width=True)

category_query = """
SELECT c.category_name, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_category c ON f.category_id = c.category_id
GROUP BY c.category_name
ORDER BY revenue DESC
"""
category_df = pd.read_sql(category_query, engine)

with col2:
    st.subheader("Revenue by Category")
    fig2 = px.pie(category_df, names="category_name", values="revenue")
    st.plotly_chart(fig2, use_container_width=True)

trend_query = """
SELECT d.year, d.month, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY d.year, d.month
ORDER BY d.year, d.month
"""
trend_df = pd.read_sql(trend_query, engine)
trend_df["period"] = trend_df["year"].astype(str) + "-" + trend_df["month"].astype(str).str.zfill(2)

st.subheader("Monthly Revenue Trend")
fig3 = px.line(trend_df, x="period", y="revenue", markers=True)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("Top States - Detail")
st.dataframe(region_df, use_container_width=True)