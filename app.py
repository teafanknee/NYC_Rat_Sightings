import re
import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="NYC Rat Sightings Heatmap",
    page_icon="🐀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    return pd.read_csv("rat_clustered.csv")


@st.cache_data
def load_yearly():
    return pd.read_csv("rat_yearly.csv")


@st.cache_data(show_spinner="Loading NYC neighborhood boundaries…")
def load_geojson():
    url = (
        "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd"
        "?method=export&type=GeoJSON&format=GeoJSON"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"Could not fetch map boundaries: {e}")
        return None


def build_nta_map(geojson):
    """Return {normalized_name: original_ntaname}."""
    nta_map = {}
    if not geojson:
        return nta_map
    for feat in geojson["features"]:
        name = feat["properties"].get("ntaname", "")
        nta_map[name.lower().strip()] = name
    return nta_map


def match_nta(neighborhood, nta_map):
    """Map a Google-Maps neighborhood name to the best-matching NTA name."""
    norm = neighborhood.lower().strip()

    # 1. Exact
    if norm in nta_map:
        return nta_map[norm]

    # 2. All words in neighborhood appear in NTA name (handles "Ditmars Steinway")
    words = norm.split()
    if len(words) > 1:
        for nta_norm, nta_orig in nta_map.items():
            if all(w in nta_norm for w in words):
                return nta_orig

    # 3. Neighborhood is a named segment of a hyphenated NTA
    for nta_norm, nta_orig in nta_map.items():
        parts = [p.strip() for p in re.split(r"[-()]", nta_norm) if p.strip()]
        if norm in parts:
            return nta_orig
        # Neighborhood name contained in any part as prefix
        if any(p.startswith(norm) for p in parts):
            return nta_orig

    # 4. Simple substring fallback
    for nta_norm, nta_orig in nta_map.items():
        if norm in nta_norm:
            return nta_orig

    return None


# ── Constants ──────────────────────────────────────────────────────────────────

COLORSCALE = [
    [0.00, "#2166ac"],   # dark blue   — low
    [0.30, "#92c5de"],   # mid blue
    [0.50, "#ffffbf"],   # pale yellow — middle
    [0.70, "#fdae61"],   # orange
    [0.85, "#f46d43"],   # deep orange
    [1.00, "#a50026"],   # dark red    — high
]

SEASON_ORDER = ["Spring", "Summer", "Fall", "Winter"]
RISK_COLOR = {"Low": "#74add1", "Medium": "#f46d43", "High": "#d73027"}

# ── Load ───────────────────────────────────────────────────────────────────────

df = load_data()
yearly_df = load_yearly()
geojson = load_geojson()
nta_map = build_nta_map(geojson)

df["nta_name"] = df["neighborhood"].apply(lambda n: match_nta(n, nta_map))
matched = df["nta_name"].notna().mean()

# ── Header ─────────────────────────────────────────────────────────────────────

st.title("🐀 NYC Rat Sightings Heatmap")
st.caption(
    "Rat sighting distribution across New York City neighborhoods (2020–2026). "
    "Select a season to explore how sightings shift throughout the year."
)

# ── Filter ─────────────────────────────────────────────────────────────────────

filter_col, _, badge_col = st.columns([2, 4, 1])
with filter_col:
    selected_season = st.selectbox(
        "Filter by Season",
        options=["All Seasons"] + SEASON_ORDER,
        help="'All Seasons' sums sightings across the full year.",
    )
with badge_col:
    st.metric("Map coverage", f"{matched:.0%}", help="Neighborhoods matched to map boundaries")

# ── Aggregate ──────────────────────────────────────────────────────────────────

def aggregate(df, season):
    base = df.dropna(subset=["nta_name"])
    if season != "All Seasons":
        base = base[base["season"] == season]
    agg = (
        base.groupby(["nta_name", "neighborhood", "Borough"], as_index=False)
        .agg(
            sighting_count=("sighting_count", "sum"),
            risk_level=("risk_level", lambda x: x.mode()[0]),
            cluster=("cluster", lambda x: x.mode()[0]),
        )
    )
    # Log-scale column for coloring — compresses the heavy right skew so
    # the majority of neighborhoods get distinct colors instead of all looking blue.
    agg["log_sightings"] = np.log1p(agg["sighting_count"])
    return agg


agg_df = aggregate(df, selected_season)

# ── Choropleth map ─────────────────────────────────────────────────────────────

if geojson and not agg_df.empty:
    agg_df["Borough_display"] = agg_df["Borough"].str.title()
    agg_df["cluster_label"] = agg_df["cluster"].map({0: "Low (0)", 1: "Medium (1)", 2: "High (2)"})

    # Colorbar ticks: pick round numbers that fall inside the current data range,
    # then label them with their original (non-log) values so the legend stays readable.
    _tick_targets = [5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000, 8000]
    _s_min = agg_df["sighting_count"].min()
    _s_max = agg_df["sighting_count"].max()
    _ticks = [(np.log1p(v), str(v)) for v in _tick_targets if _s_min <= v <= _s_max]
    _tick_vals, _tick_text = zip(*_ticks) if _ticks else ([], [])

    fig = px.choropleth_map(
        agg_df,
        geojson=geojson,
        locations="nta_name",
        featureidkey="properties.ntaname",
        color="log_sightings",
        color_continuous_scale=COLORSCALE,
        range_color=(agg_df["log_sightings"].min(), agg_df["log_sightings"].max()),
        map_style="carto-positron",
        zoom=9.6,
        center={"lat": 40.660, "lon": -73.940},
        opacity=0.78,
        hover_name="neighborhood",
        hover_data={
            "Borough_display": True,
            "sighting_count": True,
            "risk_level": True,
            "cluster_label": True,
            "nta_name": False,
            "Borough": False,
            "cluster": False,
            "log_sightings": False,
        },
        labels={
            "sighting_count": "Rat Sightings",
            "risk_level": "Risk Level",
            "cluster_label": "Cluster",
            "Borough_display": "Borough",
        },
    )
    fig.update_layout(
        height=660,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title=dict(text="Sightings", font=dict(size=12)),
            tickvals=list(_tick_vals),
            ticktext=list(_tick_text),
            thickness=14,
            len=0.55,
            tickfont=dict(size=11),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Map could not be rendered. Check your internet connection or the data.")

# ── Stats row ─────────────────────────────────────────────────────────────────

st.divider()

c1, c2 = st.columns(2)
c1.metric("Total Sightings", f"{agg_df['sighting_count'].sum():,}")
c2.metric("Neighborhoods on Map", f"{len(agg_df):,}")

# ── Borough bar chart ─────────────────────────────────────────────────────────

st.markdown("#### Sightings by Borough")

borough_df = (
    agg_df.groupby("Borough")["sighting_count"]
    .sum()
    .reset_index()
    .sort_values("sighting_count", ascending=False)
)
borough_df["Borough"] = borough_df["Borough"].str.title()

bar_fig = px.bar(
    borough_df,
    x="Borough",
    y="sighting_count",
    color="sighting_count",
    color_continuous_scale=COLORSCALE,
    text="sighting_count",
    labels={"sighting_count": "Total Sightings", "Borough": ""},
)
bar_fig.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    textfont=dict(color="#1a1a1a", size=12),
)
bar_fig.update_layout(
    height=300,
    showlegend=False,
    coloraxis_showscale=False,
    margin={"t": 20, "b": 10, "l": 40, "r": 20},
    plot_bgcolor="white",
    paper_bgcolor="rgba(0,0,0,0)",
    yaxis=dict(gridcolor="#ececec", title="", tickfont=dict(color="#1a1a1a")),
    xaxis=dict(title="", tickfont=dict(color="#1a1a1a")),
    font=dict(color="#1a1a1a"),
)
st.plotly_chart(bar_fig, use_container_width=True)

# ── Year-over-year trend ──────────────────────────────────────────────────────

st.markdown("#### Rat Sightings by Year")

BOROUGH_COLORS = {
    "BROOKLYN":      "#e63946",
    "MANHATTAN":     "#f4a261",
    "BRONX":         "#2a9d8f",
    "QUEENS":        "#457b9d",
    "STATEN ISLAND": "#9b72cf",
}

trend_df = yearly_df.copy()
trend_df["Borough_display"] = trend_df["Borough"].str.title()

trend_fig = go.Figure()
for borough, color in BOROUGH_COLORS.items():
    bdata = trend_df[trend_df["Borough"] == borough].sort_values("year")
    full = bdata[bdata["year"] <= 2025]          # 2020-2025: all complete years
    connector = bdata[bdata["year"].isin([2025, 2026])]  # just the bridge segment

    trend_fig.add_trace(go.Scatter(
        x=full["year"], y=full["sighting_count"],
        mode="lines+markers",
        name=borough.title(),
        line=dict(color=color, width=2.5),
        marker=dict(size=7),
        hovertemplate="<b>%{fullData.name}</b><br>Year: %{x}<br>Sightings: %{y:,}<extra></extra>",
    ))
    # Dotted segment from 2025 → 2026 only; no marker at 2025 to avoid double dot
    trend_fig.add_trace(go.Scatter(
        x=connector["year"], y=connector["sighting_count"],
        mode="lines+markers",
        name=borough.title(),
        line=dict(color=color, width=2.5, dash="dot"),
        marker=dict(size=7, symbol=["line-ns", "circle"]),  # hide 2025, show 2026
        showlegend=False,
        hovertemplate="<b>%{fullData.name}</b><br>Year: %{x}<br>Sightings: %{y:,} (Jan–Jun only)<extra></extra>",
    ))

trend_fig.add_annotation(
    x=2026, y=trend_df[trend_df["year"] == 2026]["sighting_count"].max(),
    text="2026: Jan–Jun only",
    showarrow=False,
    xanchor="right",
    font=dict(size=11, color="#555"),
    yshift=14,
)
trend_fig.update_layout(
    height=360,
    margin={"t": 20, "b": 40, "l": 50, "r": 20},
    plot_bgcolor="white",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#1a1a1a"),
    xaxis=dict(
        tickmode="linear", dtick=1, title="",
        gridcolor="#ececec", tickfont=dict(color="#1a1a1a"),
    ),
    yaxis=dict(title="Sightings", gridcolor="#ececec", tickfont=dict(color="#1a1a1a")),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(color="#1a1a1a")),
    hovermode="x unified",
)
st.plotly_chart(trend_fig, use_container_width=True)

# ── Top neighborhoods table ────────────────────────────────────────────────────

with st.expander("Top 20 Neighborhoods by Sightings"):
    top20 = (
        agg_df[["neighborhood", "Borough", "sighting_count", "risk_level"]]
        .sort_values("sighting_count", ascending=False)
        .head(20)
        .reset_index(drop=True)
    )
    top20.index += 1
    top20.columns = ["Neighborhood", "Borough", "Sightings", "Risk Level"]
    top20["Borough"] = top20["Borough"].str.title()
    st.dataframe(top20, use_container_width=True)
