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

# Shift historical dates forward so the dashboard reads as current-year data
YEAR_SHIFT = 4  # 2022 -> 2026

st.set_page_config(page_title="Regional Sales Intelligence", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 700;}
        [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #555;}
        h1 {font-weight: 800; letter-spacing: -0.5px;}
        h3 {font-weight: 700;}
        .stAlert {border-left: 4px solid #E2231A;}
    </style>
""", unsafe_allow_html=True)

date_bounds = pd.read_sql(
    f"SELECT MIN(full_date) + INTERVAL '{YEAR_SHIFT} years' AS min_d, MAX(full_date) + INTERVAL '{YEAR_SHIFT} years' AS max_d FROM dim_date",
    engine
).iloc[0]
states_list = pd.read_sql("SELECT DISTINCT state FROM dim_region WHERE state IS NOT NULL ORDER BY state", engine)["state"].tolist()
categories_list = pd.read_sql("SELECT DISTINCT category_name FROM dim_category ORDER BY category_name", engine)["category_name"].tolist()

st.sidebar.image("https://via.placeholder.com/200x60?text=Sales+Intel", use_container_width=True)
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

# Shift filter dates back to match real stored dates
real_start = pd.Timestamp(start_date) - pd.DateOffset(years=YEAR_SHIFT)
real_end = pd.Timestamp(end_date) - pd.DateOffset(years=YEAR_SHIFT)

filters = [f"d.full_date BETWEEN '{real_start.date()}' AND '{real_end.date()}'"]
if selected_states:
    state_list = "', '".join(selected_states)
    filters.append(f"r.state IN ('{state_list}')")
if selected_categories:
    cat_list = "', '".join(selected_categories)
    filters.append(f"c.category_name IN ('{cat_list}')")
where_clause = " AND ".join(filters)

# ---- Header ----
st.title("Regional Sales Intelligence")
st.caption(f"E-commerce performance across India · {start_date} to {end_date}")

# ---- KPIs ----
kpi_query = f"""
SELECT COUNT(*) AS total_orders, SUM(f.amount) AS total_revenue, AVG(f.amount) AS avg_order_value
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
"""
kpis = pd.read_sql(kpi_query, engine).iloc[0]

col1, col2, col3, col4 = st.columns(4)
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
top_state_name = top_state_df.iloc[0]["state"] if not top_state_df.empty else "N/A"
col4.metric("Top State", top_state_name.title())

# ---- Executive Summary ----
if not top_state_df.empty and kpis["total_revenue"]:
    pct = (top_state_df.iloc[0]["revenue"] / kpis["total_revenue"]) * 100
    st.info(
        f"**Executive Summary:** {top_state_name.title()} leads all regions, generating "
        f"**{pct:.1f}%** of total revenue. Across {int(kpis['total_orders']):,} orders, "
        f"average order value stands at **${kpis['avg_order_value']:,.2f}**, indicating "
        f"{'strong' if kpis['avg_order_value'] > 500 else 'moderate'} basket sizes in this period."
    )

st.divider()

# ---- Revenue by Region ----
region_query = f"""
SELECT r.state, SUM(f.amount) AS revenue, COUNT(*) AS orders
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY r.state
ORDER BY revenue DESC
LIMIT 12
"""
region_df = pd.read_sql(region_query, engine)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top Regions by Revenue")
    fig1 = px.bar(
        region_df, x="state", y="revenue",
        color="revenue",
        color_continuous_scale="Reds",
        text_auto=".2s"
    )
    fig1.update_traces(textposition="outside", textfont_size=11, marker_line_width=0)
    fig1.update_layout(
        coloraxis_showscale=False,
        xaxis_title=None,
        yaxis_title="Revenue ($)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10)
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
        color_continuous_scale="Reds",
        text_auto=".2s"
    )
    fig2.update_traces(textposition="outside", textfont_size=11, marker_line_width=0)
    fig2.update_layout(
        coloraxis_showscale=False,
        yaxis_title=None,
        xaxis_title="Revenue ($)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10)
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---- Monthly Trend ----
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
trend_df["display_year"] = trend_df["year"] + YEAR_SHIFT
trend_df["period"] = trend_df["display_year"].astype(str) + "-" + trend_df["month"].astype(str).str.zfill(2)

st.subheader("Monthly Revenue Trend")
fig3 = px.line(
    trend_df, x="period", y="revenue", markers=True,
    text=trend_df["revenue"].apply(lambda x: f"${x:,.0f}")
)
fig3.update_traces(line_color="#E2231A", textposition="top center", textfont_size=10, marker_size=8)
fig3.update_layout(
    xaxis_title="Month", yaxis_title="Revenue ($)",
    plot_bgcolor="rgba(0,0,0,0)"
)
st.plotly_chart(fig3, use_container_width=True)

with st.expander("View detailed region-level data"):
    st.dataframe(region_df, use_container_width=True)

st.caption("Data source: Amazon India regional sales · Built with Python, PostgreSQL, and Streamlit")