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

YEAR_SHIFT = 4  # real data ~2022, display as ~2026

st.set_page_config(page_title="Amazon India Sales Intelligence", layout="wide", initial_sidebar_state="expanded")

NAVY = "#1F2B47"
CARD = "#28365A"
ACCENT = "#E63946"
GRAY_BAR = "#8B95A8"

st.markdown(f"""
    <style>
        .stApp {{ background-color: {NAVY}; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 1rem; }}
        h1, h2, h3, p, span, label, .stMarkdown {{ color: #FFFFFF !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.8rem; font-weight: 800; color: #FFFFFF; }}
        [data-testid="stMetricLabel"] {{ font-size: 0.8rem; color: #C5CCDA; }}
        div[data-testid="stMetric"] {{
            background-color: {CARD}; border-radius: 10px; padding: 14px; border: 1px solid #37456B;
        }}
        .keyhighlight-box {{
            background-color: {CARD}; border-radius: 10px; padding: 18px; border-left: 4px solid {ACCENT};
        }}
        section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
    </style>
""", unsafe_allow_html=True)

# ---- Actual data bounds (this fixes the blank-data bug) ----
date_bounds = pd.read_sql("SELECT MIN(full_date) AS min_d, MAX(full_date) AS max_d FROM dim_date", engine).iloc[0]
real_min, real_max = date_bounds["min_d"], date_bounds["max_d"]
disp_min = pd.Timestamp(real_min) + pd.DateOffset(years=YEAR_SHIFT)
disp_max = pd.Timestamp(real_max) + pd.DateOffset(years=YEAR_SHIFT)

period_length = (real_max - real_min)
prev_real_end = real_min - pd.Timedelta(days=1)
prev_real_start = prev_real_end - period_length
prev_disp_start = prev_real_start + pd.DateOffset(years=YEAR_SHIFT)
prev_disp_end = prev_real_end + pd.DateOffset(years=YEAR_SHIFT)

st.sidebar.header("Filters")
period_choice = st.sidebar.radio(
    "Time Period",
    [f"Current ({disp_min.date()} – {disp_max.date()})",
     f"Previous ({prev_disp_start.date()} – {prev_disp_end.date()})",
     "All Available Data"]
)

if period_choice.startswith("Current"):
    real_start, real_end = real_min, real_max
elif period_choice.startswith("Previous"):
    real_start, real_end = prev_real_start, prev_real_end
else:
    real_start, real_end = real_min, real_max  # only one real period exists in this dataset

selected_categories = st.sidebar.multiselect(
    "Category",
    pd.read_sql("SELECT DISTINCT category_name FROM dim_category ORDER BY category_name", engine)["category_name"].tolist(),
    default=[]
)

filters = [f"d.full_date BETWEEN '{real_start}' AND '{real_end}'"]
if selected_categories:
    cat_list = "', '".join(selected_categories)
    filters.append(f"c.category_name IN ('{cat_list}')")
where_clause = " AND ".join(filters)

REGION_MAP_SQL = """
CASE
    WHEN r.state IN ('MAHARASHTRA','GUJARAT','RAJASTHAN','GOA','MADHYA PRADESH') THEN 'West'
    WHEN r.state IN ('KARNATAKA','TAMIL NADU','TELANGANA','ANDHRA PRADESH','KERALA') THEN 'South'
    WHEN r.state IN ('DELHI','UTTAR PRADESH','PUNJAB','HARYANA','UTTARAKHAND','JAMMU & KASHMIR','CHANDIGARH','HIMACHAL PRADESH') THEN 'North'
    WHEN r.state IN ('WEST BENGAL','BIHAR','ODISHA','JHARKHAND','ASSAM','MEGHALAYA') THEN 'East'
    ELSE 'Central'
END
"""

# ---- Header ----
st.markdown("## Amazon India Sales Intelligence")
st.caption(f"Apparel & Fashion Marketplace Analysis · {period_choice}")

# ---- KPI row ----
kpi_query = f"""
SELECT COUNT(*) AS total_orders, SUM(f.amount) AS total_revenue,
       SUM(f.qty) AS total_qty, AVG(f.amount) AS avg_order_value,
       COUNT(DISTINCT r.state) AS states_reached
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

# ---- Key Highlights narrative ----
top_cat_query = f"""
SELECT c.category_name, SUM(f.amount) AS revenue
FROM fact_sales f JOIN dim_category c ON f.category_id = c.category_id
JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id
WHERE {where_clause} GROUP BY c.category_name ORDER BY revenue DESC
"""
cat_perf = pd.read_sql(top_cat_query, engine)

top_state_query = f"""
SELECT r.state, SUM(f.amount) AS revenue
FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
JOIN dim_date d ON f.date_id = d.date_id JOIN dim_category c ON f.category_id = c.category_id
WHERE {where_clause} GROUP BY r.state ORDER BY revenue DESC LIMIT 1
"""
top_state = pd.read_sql(top_state_query, engine)

if not cat_perf.empty and kpis["total_revenue"]:
    top_cat = cat_perf.iloc[0]
    worst_cat = cat_perf.iloc[-1]
    top_cat_pct = (top_cat["revenue"] / kpis["total_revenue"]) * 100
    worst_cat_pct = (worst_cat["revenue"] / kpis["total_revenue"]) * 100
    top_state_name = top_state.iloc[0]["state"].title() if not top_state.empty else "N/A"

    st.markdown(f"""
    <div class="keyhighlight-box">
    <b>KEY HIGHLIGHTS</b><br><br>
    The best-performing category is <b style="color:{ACCENT}">{top_cat['category_name']}</b>, 
    accounting for <b>{top_cat_pct:.1f}%</b> of total revenue. 
    <b style="color:{ACCENT}">{top_state_name}</b> leads all regions in sales volume. 
    The lowest-performing category is <b>{worst_cat['category_name']}</b>, 
    contributing only <b>{worst_cat_pct:.2f}%</b> of total purchases.
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ---- Category spend bars (gray, lowest highlighted red) ----
col1, col2 = st.columns([1, 1])
with col1:
    st.markdown("### Spending by Category")
    cat_perf_sorted = cat_perf.sort_values("revenue", ascending=True)
    colors = [ACCENT if i == 0 else GRAY_BAR for i in range(len(cat_perf_sorted))]
    fig1 = px.bar(cat_perf_sorted, x="revenue", y="category_name", orientation="h", text_auto=".2s")
    fig1.update_traces(marker_color=colors, textposition="outside")
    fig1.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="white", yaxis_title=None, xaxis_title=None,
        margin=dict(t=10)
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.markdown("### Spending by Region")
    region_query = f"""
    SELECT {REGION_MAP_SQL} AS zone, SUM(f.amount) AS revenue
    FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
    JOIN dim_date d ON f.date_id = d.date_id JOIN dim_category c ON f.category_id = c.category_id
    WHERE {where_clause} GROUP BY zone ORDER BY revenue ASC
    """
    region_df = pd.read_sql(region_query, engine)
    colors2 = [ACCENT if i == 0 else GRAY_BAR for i in range(len(region_df))]
    fig2 = px.bar(region_df, x="revenue", y="zone", orientation="h", text_auto=".2s")
    fig2.update_traces(marker_color=colors2, textposition="outside")
    fig2.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="white", yaxis_title=None, xaxis_title=None,
        margin=dict(t=10)
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---- Order status performance (analog to "campaign success rate") ----
st.markdown("### Order Fulfillment Rate by Category")
status_query = f"""
SELECT c.category_name,
       ROUND(100.0 * SUM(CASE WHEN f.status ILIKE '%%Shipped%%' THEN 1 ELSE 0 END) / COUNT(*), 2) AS fulfillment_rate
FROM fact_sales f JOIN dim_category c ON f.category_id = c.category_id
JOIN dim_region r ON f.region_id = r.region_id JOIN dim_date d ON f.date_id = d.date_id
WHERE {where_clause}
GROUP BY c.category_name
ORDER BY fulfillment_rate DESC
"""
status_df = pd.read_sql(status_query, engine)
avg_rate = status_df["fulfillment_rate"].mean() if not status_df.empty else 0
colors3 = [ACCENT if v == status_df["fulfillment_rate"].min() else GRAY_BAR for v in status_df["fulfillment_rate"]]

fig3 = px.bar(status_df, x="category_name", y="fulfillment_rate", text_auto=".2s")
fig3.update_traces(marker_color=colors3)
fig3.add_hline(y=avg_rate, line_dash="dash", line_color="#F4D35E", annotation_text=f"Avg {avg_rate:.1f}%")
fig3.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font_color="white", xaxis_title=None, yaxis_title="Fulfillment %",
    margin=dict(t=10)
)
st.plotly_chart(fig3, use_container_width=True)

st.caption("Source: Amazon India apparel marketplace data · Built with Python, PostgreSQL & Streamlit")