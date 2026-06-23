import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="SyntaxTax", layout="wide")
st.title("SyntaxTax — Technical Debt Dashboard")

org_id = st.sidebar.text_input("GitHub Organization name", value="")
st.sidebar.button("Refresh data")


def fetch_reports(org_id: str) -> list[dict]:
    resp = requests.get(f"{API_BASE_URL}/api/reports/{org_id}", timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


if not org_id:
    st.info("Enter a GitHub Organization name in the sidebar (e.g. your GitHub username).")
    st.stop()

try:
    reports = fetch_reports(org_id)
except requests.RequestException as e:
    st.error(f"Failed to connect to API at {API_BASE_URL}: {e}")
    st.stop()

if not reports:
    st.warning("No reports found for this organization.")
    st.stop()

total_cost = sum(r["report_data"]["total_cost_eur"] for r in reports)
total_repos = len(reports)
total_files = sum(r["report_data"]["total_files_analyzed"] for r in reports)
total_funcs = sum(r["report_data"]["total_functions_analyzed"] for r in reports)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Cost (EUR)", f"€{total_cost:,.2f}")
col2.metric("Repositories Analyzed", total_repos)
col3.metric("Files Analyzed", total_files)
col4.metric("Functions Analyzed", total_funcs)

repo_costs = pd.DataFrame([
    {"Repository": r["repository_name"], "Cost (EUR)": r["report_data"]["total_cost_eur"]}
    for r in reports
])
fig = px.bar(
    repo_costs,
    x="Repository",
    y="Cost (EUR)",
    title="Cost per Repository",
    text_auto=".2s",
)
fig.update_traces(textposition="outside")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Critical Functions")
rows: list[dict] = []
for r in reports:
    for f in r["report_data"]["top_files"]:
        for fn in f["critical_functions"]:
            rows.append({
                "Repository": r["repository_name"],
                "File": f["file"],
                "Function": fn["name"],
                "Complexity": fn["complexity"],
                "Extra": fn["extra_complexity"],
                "Lines": fn["lines"],
                "Cost (EUR)": fn["cost_eur"],
            })

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        column_config={
            "Cost (EUR)": st.column_config.NumberColumn(format="€%.2f"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No critical functions found across any repository.")
