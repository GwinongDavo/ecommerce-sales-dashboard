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

YEAR_SHIFT = 4

st.set_page_config(page_title="Amazon India Sales Intelligence", layout="wide", initial_sidebar_state="expanded")

NAVY = "#1F2B47"
CARD = "#28365A"
ACCENT = "#E63946"

st.markdown(f"""
    <style>
        .stApp {{ background-color: {NAVY}; }}
        header[data-testid="stHeader"] {{ background-color: {NAVY}; }}
        [data-testid="stToolbar"] {{ background-color: {NAVY}; }}
        .block-container {{ padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }}
        h1, h2, h3, p, span, label, .stMarkdown {{ color: #FFFFFF !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.6rem; font-weight: 800; color: #FFFFFF; }}
        [data-testid="stMetricLabel"] {{ font-size: 0.78rem; color: #C5CCDA; }}
        div[data-testid="stMetric"] {{
            background-color: {CARD}; border-radius: 10px; padding: 12px; border: 1px solid #37456B;
        }}
        .keyhighlight-box {{
            background-color: {CARD}; border-radius: 10px; padding: 16px; border-left: 4px solid {ACCENT};
            font-size: 0.95rem; line-height: 1.5;
        }}
        section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
        @media (max-width: 640px) {{
            [data-testid="stMetricValue"] {{ font-size: 1.3rem; }}
            h1 {{ font-size: 1.5rem !important; }}
            h3 {{ font-size: 1.1rem !important; }}
        }}
    </style>
""", unsafe_allow_html=True)

REGION_MAP_SQL = """
CASE
    WHEN r.state IN ('MAHARASHTRA','GUJARAT','RAJASTHAN','GOA','MADHYA PRADESH') THEN 'West'
    WHEN r.state IN ('KARNATAKA','TAMIL NADU','TELANGANA','ANDHRA PRADESH','KERALA') THEN 'South'
    WHEN r.state IN ('DELHI','UTTAR PRADESH','PUNJAB','HARYANA','UTTARAKHAND','JAMMU & KASHMIR','CHANDIGARH','HIMACHAL PRADESH') THEN 'North'
    WHEN r.state IN ('WEST BENGAL','BIHAR','ODISHA','JHARKHAND','ASSAM','MEGHALAYA') THEN 'East'
    ELSE 'Central'
END
"""

# ---- Real data bounds, split into two REAL halves (fixes the empty "previous period" issue) ----
date_bounds = pd.read_sql("SELECT MIN(full_date) AS min_d, MAX(full_date) AS max_d FROM dim_date", engine).iloc[0]
real_min, real_max = pd.Timestamp(date_bounds["min_d"]), pd.Timestamp(date_bounds["max_d"])
midpoint = real_min + (real_max - real_min) / 2

second_half_start, second_half_end = midpoint + pd.Timedelta(days=1), real_max
first_half_start, first_half_end = real_min, midpoint

def shift(d):
    return (d + pd.DateOffset(years=YEAR_SHIFT)).date()

st.sidebar.header("Filters")
period_choice = st.sidebar.radio(
    "Time Period",
    [f"Recent ({shift(second_half_start)} – {shift(second_half_end)})",
     f"Earlier ({shift(first_half_start)} – {shift(first_half_end)})",
     "All Available Data"]
)

if period_choice.startswith("Recent"):
    real_start, real_end = second_half_start, second_half_end
elif period_choice.startswith("Earlier"):
    real_start, real_end = first_half_start, first_half_end
else:
    real_start, real_end = real_min, real_max

selected_categories = st.sidebar.multiselect(
    "Category",
    pd.read_sql("SELECT DISTINCT category_name FROM dim_category ORDER BY category_name", engine)["category_name"].tolist(),
    default=[]
)

filters = [f"d.full_date BETWEEN '{real_start.date()}' AND '{real_end.date()}'"]
if selected_categories:
    cat_list = "', '".join(selected_categories)
    filters.append(f"c.category_name IN ('{cat_list}')")
where_clause = " AND ".join(filters)

# ---- Header ----
st.markdown("## Amazon India Sales Intelligence")
st.caption(f"Apparel & Fashion Marketplace Analysis · {period_choice}")

# ---- KPIs ----
kpi_query = f"""
SELECT COUNT(*) AS total_orders, SUM(f.amount) AS total_revenue,
       AVG(f.amount) AS avg_order_value, COUNT(DISTINCT r.state) AS states_reached
FROM fact_sales f
JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id
JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause}
"""
kpis = pd.read_sql(kpi_query, engine).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"${(kpis['total_revenue'] or 0):,.0f}")
c2.metric("Total Orders", f"{int(kpis['total_orders'] or 0):,}")
c3.metric("Avg Order Value", f"${kpis['avg_order_value'] or 0:,.2f}")
c4.metric("States Reached", f"{int(kpis['states_reached'] or 0)}")

st.divider()

# ---- Key Highlights ----
cat_perf = pd.read_sql(f"""
SELECT c.category_name, SUM(f.amount) AS revenue
FROM fact_sales f JOIN dim_category c ON f.category_id = c.category_id
JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id
WHERE {where_clause} GROUP BY c.category_name ORDER BY revenue DESC
""", engine)

top_state = pd.read_sql(f"""
SELECT r.state, SUM(f.amount) AS revenue
FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause} GROUP BY r.state ORDER BY revenue DESC LIMIT 1
""", engine)

if not cat_perf.empty and kpis["total_revenue"]:
    top_cat, worst_cat = cat_perf.iloc[0], cat_perf.iloc[-1]
    top_pct = (top_cat["revenue"] / kpis["total_revenue"]) * 100
    worst_pct = (worst_cat["revenue"] / kpis["total_revenue"]) * 100
    top_state_name = top_state.iloc[0]["state"].title() if not top_state.empty else "N/A"
    st.markdown(f"""
    <div class="keyhighlight-box">
    <b>KEY HIGHLIGHTS</b><br><br>
    <b style="color:{ACCENT}">{top_cat['category_name']}</b> is the top-performing category, driving 
    <b>{top_pct:.1f}%</b> of total revenue. <b style="color:{ACCENT}">{top_state_name}</b> leads all regions.
    <b>{worst_cat['category_name']}</b> is the weakest category at just <b>{worst_pct:.2f}%</b> of revenue.
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ---- Category & Region bars — continuous color scale, darker = higher, with labels ----
col1, col2 = st.columns(2)
with col1:
    st.markdown("### Spending by Category")
    d = cat_perf.sort_values("revenue")
    fig1 = px.bar(d, x="revenue", y="category_name", orientation="h",
                   color="revenue", color_continuous_scale=["#F4A6A6", ACCENT, "#8B0000"],
                   text_auto=".2s")
    fig1.update_traces(textposition="outside")
    fig1.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="white", yaxis_title=None, xaxis_title=None, margin=dict(t=10))
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.markdown("### Spending by Region")
    region_df = pd.read_sql(f"""
    SELECT {REGION_MAP_SQL} AS zone, SUM(f.amount) AS revenue
    FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
    JOIN dim_date d ON f.date_id = d.date_id JOIN dim_category c ON f.category_id = c.category_id
    WHERE {where_clause} GROUP BY zone ORDER BY revenue ASC
    """, engine)
    fig2 = px.bar(region_df, x="revenue", y="zone", orientation="h",
                   color="revenue", color_continuous_scale=["#F4A6A6", ACCENT, "#8B0000"],
                   text_auto=".2s")
    fig2.update_traces(textposition="outside")
    fig2.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        font_color="white", yaxis_title=None, xaxis_title=None, margin=dict(t=10))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---- Fulfillment rate — clarified + fixed color logic (darker red = HIGHEST) ----
st.markdown("### Order Fulfillment Rate by Category")
st.caption("Percentage of orders successfully shipped (vs. cancelled or returned) — a measure of reliable delivery performance per category. Darker = higher fulfillment.")

status_df = pd.read_sql(f"""
SELECT c.category_name,
       ROUND(100.0 * SUM(CASE WHEN f.status ILIKE '%%Shipped%%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS fulfillment_rate
FROM fact_sales f JOIN dim_category c ON f.category_id = c.category_id
JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id
WHERE {where_clause}
GROUP BY c.category_name ORDER BY fulfillment_rate DESC
""", engine)
avg_rate = status_df["fulfillment_rate"].mean() if not status_df.empty else 0

fig3 = px.bar(status_df, x="category_name", y="fulfillment_rate",
               color="fulfillment_rate", color_continuous_scale=["#F4A6A6", ACCENT, "#8B0000"],
               text_auto=".2s")
fig3.add_hline(y=avg_rate, line_dash="dash", line_color="#F4D35E", annotation_text=f"Avg {avg_rate:.1f}%")
fig3.update_layout(coloraxis_showscale=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_color="white", xaxis_title=None, yaxis_title="Fulfillment %", margin=dict(t=10))
st.plotly_chart(fig3, use_container_width=True)

st.caption("Source: Amazon India apparel marketplace data · Built with Python, PostgreSQL & Streamlit")