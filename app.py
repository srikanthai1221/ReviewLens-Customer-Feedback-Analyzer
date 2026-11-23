import pandas as pd
import plotly.express as px
import streamlit as st

from config import MAX_CONCURRENCY, OPENAI_API_KEY, OPENAI_MODEL
from pipeline import analyse_reviews, build_report, compute_stats, to_excel_csv, validate_reviews
from schemas import CATEGORIES, SENTIMENTS

COLORS = {"positive": "#2E7D32", "neutral": "#9E9E9E", "negative": "#C62828"}

st.set_page_config(page_title="ReviewLens", page_icon="🔎", layout="wide")
st.title("🔎 ReviewLens: Customer Feedback Analyzer")
st.caption("Raw reviews → tagged, prioritised insights and a 5-minute weekly report.")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY not found. Add it to your .env file and restart the app.")
    st.stop()

st.sidebar.markdown(f"**Model:** `{OPENAI_MODEL}`  \n**Max concurrency:** {MAX_CONCURRENCY}")

# 01 Upload
uploaded = st.file_uploader("Upload this week's reviews (CSV)", type="csv")
if uploaded is None:
    st.info("Required columns: review_id, date, platform, rating, review_text")
    st.stop()

# 02 Validate
try:
    df, dropped = validate_reviews(pd.read_csv(uploaded))
except ValueError as e:
    st.error(str(e))
    st.stop()
st.success(f"{len(df)} valid reviews loaded ({dropped} empty/duplicate rows dropped).")

# Period filter
min_d, max_d = df["date"].min().date(), df["date"].max().date()
picked = st.sidebar.date_input("Report period", value=(min_d, max_d),
                               min_value=min_d, max_value=max_d)
if len(picked) != 2:
    st.stop()
start, end = picked
week_df = df[df["date"].dt.date.between(start, end)].reset_index(drop=True)
period = f"{start:%d %b} to {end:%d %b %Y}"
st.sidebar.write(f"{len(week_df)} reviews in period")

run_key = f"{uploaded.name}-{uploaded.size}-{start}-{end}"

# 03-05 Classify + aggregate + report
if st.button(f"Analyse {len(week_df)} reviews", type="primary", disabled=week_df.empty):
    bar = st.progress(0.0, text="Starting…")

    def on_progress(done, total, attempt):
        bar.progress(done / total, text=f"Analysed {done}/{total} (pass {attempt})")

    enriched = analyse_reviews(week_df, on_progress)
    with st.spinner("Writing weekly report…"):
        report = build_report(enriched, period)
    st.session_state["result"] = {"key": run_key, "enriched": enriched, "report": report}

result = st.session_state.get("result")
if not result or result["key"] != run_key:
    st.stop()  # nothing analysed yet for this file + period

enriched, report = result["enriched"], result["report"]
stats = compute_stats(enriched)

# KPI row
pct = stats["sentiment"].set_index("sentiment")["pct"]
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total reviews", stats["total"])
k2.metric("Positive", f"{pct['positive']}%")
k3.metric("Neutral", f"{pct['neutral']}%")
k4.metric("Negative", f"{pct['negative']}%")
k5.metric("🚨 High urgency", stats["high_urgency"])
if stats["needs_review"]:
    st.warning(f"{stats['needs_review']} reviews could not be tagged after retries; marked 'needs_review'.")

tab_dash, tab_report, tab_table = st.tabs(["📊 Dashboard", "📝 Weekly report", "📋 Reviews"])

# 06 Show
with tab_dash:
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.pie(stats["sentiment"], names="sentiment", values="count", hole=0.45,
                           color="sentiment", color_discrete_map=COLORS, title="Sentiment split"))
    c2.plotly_chart(px.bar(stats["category"], x="category", y="count", color="sentiment",
                           color_discrete_map=COLORS, title="Reviews by category"))

with tab_report:
    st.code(report, language=None)
    st.download_button("⬇️ Download report (.txt)", report, file_name=f"weekly_report_{start}_{end}.txt")

with tab_table:
    only_high = st.toggle("🚨 Show only HIGH urgency")
    f1, f2, f3 = st.columns(3)
    sent_f = f1.multiselect("Sentiment", SENTIMENTS + ["needs_review"])
    cat_f = f2.multiselect("Category", CATEGORIES + ["needs_review"])
    plat_f = f3.multiselect("Platform", sorted(enriched["platform"].unique()))

    view = enriched
    if only_high:
        view = view[view["urgency"] == "high"]
    if sent_f:
        view = view[view["sentiment"].isin(sent_f)]
    if cat_f:
        view = view[view["category"].isin(cat_f)]
    if plat_f:
        view = view[view["platform"].isin(plat_f)]

    st.caption(f"Showing {len(view)} of {len(enriched)} reviews")
    st.dataframe(view, hide_index=True)

    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download ALL enriched reviews (CSV)", to_excel_csv(enriched),
                       file_name=f"reviewlens_enriched_{start}_{end}.csv", mime="text/csv")
    d2.download_button("⬇️ Download FILTERED view (CSV)", to_excel_csv(view),
                       file_name=f"reviewlens_filtered_{start}_{end}.csv", mime="text/csv")