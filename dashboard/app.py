"""ResQStats dashboard - Streamlit app.

Run locally:
    streamlit run dashboard/app.py

Deploy free: push repo to GitHub -> share.streamlit.io -> point at this file.
(data/resqstats.duckdb must be committed for cloud deploys - see .gitignore)
"""
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB = Path(__file__).resolve().parent.parent / "data" / "resqstats.duckdb"

st.set_page_config(page_title="ResQStats — Karachi Ambulance Analytics",
                   page_icon="🚑", layout="wide")


@st.cache_data
def load() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.sql("""
        select town, incident_type, severity, call_hour, station,
               minutes_to_scene, total_minutes, is_raining
        from fct_incidents
    """).df()
    con.close()
    return df


df = load()

# ---------------- sidebar filters ----------------
st.sidebar.title("Filters")
sevs = st.sidebar.multiselect("Severity", ["critical", "serious", "moderate", "minor"],
                              default=["critical", "serious", "moderate", "minor"])
types = st.sidebar.multiselect("Incident type", sorted(df.incident_type.unique()),
                               default=sorted(df.incident_type.unique()))
weather = st.sidebar.radio("Weather", ["All", "Dry days", "Rainy days"])

f = df[df.severity.isin(sevs) & df.incident_type.isin(types)]
if weather == "Dry days":
    f = f[~f.is_raining]
elif weather == "Rainy days":
    f = f[f.is_raining]

st.sidebar.caption(f"{len(f)} of {len(df)} incidents")

# ---------------- header + KPIs ----------------
st.title("🚑 ResQStats — Karachi Ambulance Dispatch Analytics")

if f.empty:
    st.warning("No incidents match the current filters.")
    st.stop()

crit = f[f.severity == "critical"]
golden = f"{100 * (crit.total_minutes <= 60).mean():.0f}%" if len(crit) else "—"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Emergency incidents", len(f))
c2.metric("Median response", f"{f.minutes_to_scene.median():.1f} min")
c3.metric("P90 response", f"{f.minutes_to_scene.quantile(0.9):.1f} min")
c4.metric("Golden hour (critical ≤60m)", golden)
c5.metric("Towns covered", f.town.nunique())

# ---------------- coverage gaps ----------------
st.subheader("Coverage gaps — response time by town")
town_stats = (f.groupby("town").minutes_to_scene
              .agg(median="median", p90=lambda s: s.quantile(0.9), incidents="count")
              .round(1).reset_index().sort_values("median"))
colors = ["#e53935" if t == "Baldia" else ("#fb8c00" if m > 20 else "#43a047")
          for t, m in zip(town_stats.town, town_stats["median"])]
fig = go.Figure([
    go.Bar(y=town_stats.town, x=town_stats["median"], orientation="h",
           marker_color=colors, name="Median",
           hovertemplate="%{y}: %{x} min<extra>median</extra>"),
    go.Scatter(y=town_stats.town, x=town_stats.p90, mode="markers", name="P90",
               marker=dict(color="#8b98a5", size=9, symbol="line-ns-open"),
               hovertemplate="%{y}: %{x} min<extra>P90</extra>"),
])
fig.add_vline(x=15, line_dash="dash", line_color="grey",
              annotation_text="15 min target")
fig.update_layout(height=520, margin=dict(t=10, b=10),
                  legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, use_container_width=True)

# ---------------- hourly + types ----------------
left, right = st.columns(2)

with left:
    st.subheader("Demand & response by hour")
    hourly = (f.groupby("call_hour")
              .agg(incidents=("minutes_to_scene", "count"),
                   avg_response=("minutes_to_scene", "mean")).reset_index())
    fig = go.Figure([
        go.Bar(x=hourly.call_hour, y=hourly.incidents, name="Incidents",
               marker_color="#3949ab"),
        go.Scatter(x=hourly.call_hour, y=hourly.avg_response.round(1),
                   name="Avg response (min)", yaxis="y2",
                   line=dict(color="#e53935", width=2)),
    ])
    fig.update_layout(height=400, margin=dict(t=10, b=10),
                      xaxis=dict(title="hour of day", dtick=2),
                      yaxis2=dict(overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Incident types")
    tc = f.incident_type.value_counts().reset_index()
    tc.columns = ["type", "count"]
    fig = px.bar(tc, x="count", y="type", orientation="h",
                 color_discrete_sequence=["#00897b"])
    fig.update_layout(height=400, margin=dict(t=10, b=10),
                      yaxis=dict(autorange="reversed"), xaxis_title=None,
                      yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

# ---------------- severity + heatmap ----------------
left, right = st.columns(2)

with left:
    st.subheader("Severity mix")
    sc = f.severity.value_counts().reindex(
        ["critical", "serious", "moderate", "minor"]).dropna().reset_index()
    sc.columns = ["severity", "count"]
    fig = px.pie(sc, names="severity", values="count", hole=0.55,
                 color="severity",
                 color_discrete_map={"critical": "#e53935", "serious": "#fb8c00",
                                     "moderate": "#fdd835", "minor": "#43a047"})
    fig.update_layout(height=380, margin=dict(t=10, b=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Station load heatmap")
    heat = f.pivot_table(index="station", columns="call_hour",
                         values="minutes_to_scene", aggfunc="count").fillna(0)
    fig = px.imshow(heat, color_continuous_scale="YlOrRd", aspect="auto")
    fig.update_layout(height=380, margin=dict(t=10, b=10),
                      coloraxis_showscale=False, xaxis_title="hour of day")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Simulated Karachi dispatch data — real dispatch records are confidential. "
           "Pipeline: Kafka → Spark → MinIO → dbt/DuckDB → Airflow.")
