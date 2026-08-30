import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from datetime import date

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

YEAR_SHIFT = 4  # real data is 2022, display as 2026

st.set_page_config(page_title="Sales Analysis Dashboard", layout="wide", initial_sidebar_state="expanded")

PALETTE = ["#5DADE2", "#48C9B0", "#5499C7", "#76D7C4", "#2E86C1", "#A9DFBF"]

st.markdown("""
    <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 700; color: #2E86C1;}
        [data-testid="stMetricLabel"] {font-size: 0.85rem; color: #666;}
        h1 {font-weight: 800; color: #2E86C1;}
        h3 {font-weight: 700; color: #333;}
        div[data-testid="stMetric"] {
            background-color: #FAFBFC;
            border: 1px solid #E5E8EC;
            border-radius: 10px;
            padding: 12px;
        }
    </style>
""", unsafe_allow_html=True)

# ---- Region mapping: Indian states -> zones ----
REGION_MAP_SQL = """
CASE
    WHEN r.state IN ('MAHARASHTRA','GUJARAT','RAJASTHAN','GOA','MADHYA PRADESH') THEN 'West'
    WHEN r.state IN ('KARNATAKA','TAMIL NADU','TELANGANA','ANDHRA PRADESH','KERALA') THEN 'South'
    WHEN r.state IN ('DELHI','UTTAR PRADESH','PUNJAB','HARYANA','UTTARAKHAND','JAMMU & KASHMIR','CHANDIGARH','HIMACHAL PRADESH') THEN 'North'
    WHEN r.state IN ('WEST BENGAL','BIHAR','ODISHA','JHARKHAND','ASSAM','MEGHALAYA') THEN 'East'
    ELSE 'Central'
END
"""

# ---- Sidebar: period selector ----
st.sidebar.header("Time Period")
period_choice = st.sidebar.radio("Select period", ["Jul 1 – Aug 30 (Current)", "Previous Period (May 1 – Jun 30)", "All Time"])

if period_choice.startswith("Jul"):
    disp_start, disp_end = date(2026, 7, 1), date(2026, 8, 30)
elif period_choice.startswith("Previous"):
    disp_start, disp_end = date(2026, 5, 1), date(2026, 6, 30)
else:
    disp_start, disp_end = None, None

st.sidebar.divider()
selected_categories = st.sidebar.multiselect(
    "Category",
    pd.read_sql("SELECT DISTINCT category_name FROM dim_category ORDER BY category_name", engine)["category_name"].tolist(),
    default=[]
)

# ---- Build WHERE clause (shift dates back to real 2022 range for querying) ----
filters = []
if disp_start and disp_end:
    real_start = pd.Timestamp(disp_start) - pd.DateOffset(years=YEAR_SHIFT)
    real_end = pd.Timestamp(disp_end) - pd.DateOffset(years=YEAR_SHIFT)
    filters.append(f"d.full_date BETWEEN '{real_start.date()}' AND '{real_end.date()}'")
if selected_categories:
    cat_list = "', '".join(selected_categories)
    filters.append(f"c.category_name IN ('{cat_list}')")
where_clause = " AND ".join(filters) if filters else "1=1"

# ---- Header ----
col_logo, col_title = st.columns([1, 6])
with col_title:
    st.title("Sales Analysis Dashboard")
    st.caption(f"{period_choice} · Regional performance across India")

# ---- KPI cards ----
kpi_query = f"""
SELECT COUNT(*) AS total_orders, SUM(f.amount) AS total_revenue,
       SUM(f.qty) AS total_qty, AVG(f.amount) AS avg_order_value,
       COUNT(DISTINCT d.full_date) AS days_count
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
"""
kpis = pd.read_sql(kpi_query, engine).iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Sales", f"${(kpis['total_revenue'] or 0)/1000:,.0f}K")
c2.metric("Total Quantity", f"{int((kpis['total_qty'] or 0)/1000):,}K")
c3.metric("Total Orders", f"{int(kpis['total_orders'] or 0):,}")
c4.metric("Avg Order Value", f"${kpis['avg_order_value'] or 0:,.0f}")
c5.metric("Days Active", f"{int(kpis['days_count'] or 0)}")

st.divider()

# ---- Row: Region pie | Category bar | Segment donut ----
col1, col2, col3 = st.columns(3)

region_query = f"""
SELECT {REGION_MAP_SQL} AS zone, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY zone
ORDER BY revenue DESC
"""
region_df = pd.read_sql(region_query, engine)

with col1:
    st.subheader("Sales by Region")
    fig1 = px.pie(region_df, names="zone", values="revenue", hole=0, color_discrete_sequence=PALETTE)
    fig1.update_traces(textinfo="label+percent", textfont_size=11)
    fig1.update_layout(showlegend=False, margin=dict(t=10, b=10))
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
LIMIT 6
"""
category_df = pd.read_sql(category_query, engine)

with col2:
    st.subheader("Sales by Category")
    fig2 = px.bar(category_df, x="category_name", y="revenue", color_discrete_sequence=[PALETTE[0]])
    fig2.update_layout(xaxis_title=None, yaxis_title="Revenue ($)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10))
    st.plotly_chart(fig2, use_container_width=True)

segment_query = f"""
SELECT CASE WHEN f.b2b THEN 'Corporate' ELSE 'Consumer' END AS segment, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY segment
"""
segment_df = pd.read_sql(segment_query, engine)

with col3:
    st.subheader("Sales by Segment")
    fig3 = px.pie(segment_df, names="segment", values="revenue", hole=0.55, color_discrete_sequence=PALETTE)
    fig3.update_traces(textinfo="label+percent", textfont_size=11)
    fig3.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ---- Quarterly trend by region (stream-style area chart) ----
trend_query = f"""
SELECT d.year, d.quarter, {REGION_MAP_SQL} AS zone, SUM(f.amount) AS revenue
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
GROUP BY d.year, d.quarter, zone
ORDER BY d.year, d.quarter
"""
trend_df = pd.read_sql(trend_query, engine)
trend_df["display_year"] = trend_df["year"] + YEAR_SHIFT
trend_df["period"] = "Q" + trend_df["quarter"].astype(str) + " " + trend_df["display_year"].astype(str)

st.subheader("Sales by Quarter and Region")
fig4 = px.area(
    trend_df, x="period", y="revenue", color="zone",
    color_discrete_sequence=PALETTE, groupnorm=None
)
fig4.update_layout(
    xaxis_title="Quarter", yaxis_title="Revenue ($)",
    plot_bgcolor="rgba(0,0,0,0)", legend_title=None,
    margin=dict(t=10)
)
st.plotly_chart(fig4, use_container_width=True)

st.caption("Data: Amazon India regional sales · Built with Python, PostgreSQL & Streamlit")