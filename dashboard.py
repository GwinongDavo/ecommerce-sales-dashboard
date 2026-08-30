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

st.set_page_config(page_title="E-commerce Sales Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.8rem;}
    </style>
""", unsafe_allow_html=True)

date_bounds = pd.read_sql("SELECT MIN(full_date) AS min_d, MAX(full_date) AS max_d FROM dim_date", engine).iloc[0]
states_list = pd.read_sql("SELECT DISTINCT state FROM dim_region WHERE state IS NOT NULL ORDER BY state", engine)["state"].tolist()
categories_list = pd.read_sql("SELECT DISTINCT category_name FROM dim_category ORDER BY category_name", engine)["category_name"].tolist()

st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date range",
    value=(date_bounds["min_d"], date_bounds["max_d"]),
    min_value=date_bounds["min_d"],
    max_value=date_bounds["max_d"]
)
selected_states = st.sidebar.multiselect("State", states_list, default=[])
selected_categories = st.sidebar.multiselect("Category", categories_list, default=[])

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = date_bounds["min_d"], date_bounds["max_d"]

filters = [f"d.full_date BETWEEN '{start_date}' AND '{end_date}'"]
if selected_states:
    state_list = "', '".join(selected_states)
    filters.append(f"r.state IN ('{state_list}')")
if selected_categories:
    cat_list = "', '".join(selected_categories)
    filters.append(f"c.category_name IN ('{cat_list}')")
where_clause = " AND ".join(filters)

st.title("E-commerce Sales Dashboard")
st.caption(f"Showing data from **{start_date}** to **{end_date}**" +
           (f" · States: {', '.join(selected_states)}" if selected_states else "") +
           (f" · Categories: {', '.join(selected_categories)}" if selected_categories else ""))

kpi_query = f"""
SELECT COUNT(*) AS total_orders, SUM(f.amount) AS total_revenue, AVG(f.amount) AS avg_order_value
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
"""
kpis = pd.read_sql(kpi_query, engine).iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Total Orders", f"{int(kpis['total_orders'] or 0):,}")
col2.metric("Total Revenue", f"${kpis['total_revenue'] or 0:,.0f}")
col3.metric("Avg Order Value", f"${kpis['avg_order_value'] or 0:,.2f}")

top_state_query = f"""
SELECT r.state, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY r.state
ORDER BY revenue DESC
LIMIT 1
"""
top_state_df = pd.read_sql(top_state_query, engine)
if not top_state_df.empty and kpis["total_revenue"]:
    top_state = top_state_df.iloc[0]
    pct = (top_state["revenue"] / kpis["total_revenue"]) * 100
    st.info(f"📍 **{top_state['state']}** is the top-performing state, contributing **{pct:.1f}%** of total revenue in this period.")

st.divider()

region_query = f"""
SELECT r.state, SUM(f.amount) AS revenue, COUNT(*) AS orders
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY r.state
ORDER BY revenue DESC
LIMIT 15
"""
region_df = pd.read_sql(region_query, engine)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top States by Revenue")
    fig1 = px.bar(
        region_df, x="state", y="revenue",
        color="revenue",
        color_continuous_scale="Blues",
        text_auto=".2s"
    )
    fig1.update_traces(textposition="outside", textfont_size=11)
    fig1.update_layout(
        coloraxis_showscale=False,
        xaxis_title=None,
        yaxis_title="Revenue ($)",
        margin=dict(t=20)
    )
    st.plotly_chart(fig1, use_container_width=True)

category_query = f"""
SELECT c.category_name, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY c.category_name
ORDER BY revenue DESC
"""
category_df = pd.read_sql(category_query, engine)

with col2:
    st.subheader("Revenue by Category")
    fig2 = px.bar(
        category_df.sort_values("revenue"), x="revenue", y="category_name",
        orientation="h",
        color="revenue",
        color_continuous_scale="Blues",
        text_auto=".2s"
    )
    fig2.update_traces(textposition="outside", textfont_size=11)
    fig2.update_layout(
        coloraxis_showscale=False,
        yaxis_title=None,
        xaxis_title="Revenue ($)",
        margin=dict(t=20)
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

trend_query = f"""
SELECT d.year, d.month, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY d.year, d.month
ORDER BY d.year, d.month
"""
trend_df = pd.read_sql(trend_query, engine)
trend_df["period"] = trend_df["year"].astype(str) + "-" + trend_df["month"].astype(str).str.zfill(2)

st.subheader("Monthly Revenue Trend")
st.caption("Each point represents total revenue for that calendar month, based on order date.")
fig3 = px.line(trend_df, x="period", y="revenue", markers=True, text=trend_df["revenue"].apply(lambda x: f"${x:,.0f}"))
fig3.update_traces(textposition="top center", textfont_size=10)
fig3.update_layout(xaxis_title="Month", yaxis_title="Revenue ($)")
st.plotly_chart(fig3, use_container_width=True)

with st.expander("View detailed state-level data"):
    st.dataframe(region_df, use_container_width=True)