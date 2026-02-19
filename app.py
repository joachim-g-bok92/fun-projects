"""
Arsenal Position Dashboard – improved edition
=============================================
Improvements over v1:
  1.  W/D/L result heatmap (season × matchweek, colour-coded by result)
  2.  Points pace reference line (title-winning pace overlay)
  3.  Fixed season→colour mapping (colours never shift on filter changes)
  4.  add_vrect shading for the bottling zone (not just a vertical line)
  5.  "Points dropped from half-time lead" bar chart per season
  6.  Goal-difference trajectory chart
  7.  KPI summary cards above the charts
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_prep import get_arsenal_enriched

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "epl_final.csv"
EXTRA_PATH = BASE_DIR / "arsenal_2025_26_pl.csv"

# ── colour palette ────────────────────────────────────────────────────────────
APP_BG        = "#050816"
CHART_BG      = "#0A0F2A"
ARSENAL_RED   = "#EF0107"
ARSENAL_GOLD  = "#C8A951"
CHART_TEXT    = "#E8ECF5"
GRID_COLOR    = "rgba(255,255,255,0.07)"
BOTTLING_FILL = "rgba(239,1,7,0.07)"
BOTTLING_LINE = "rgba(239,1,7,0.55)"
CURRENT_ENDPOINT_LINE = "#00E5FF"  # highlight for "We are here" (2025/26 current matchweek)

# Fixed season→colour: colours are stable regardless of which seasons are selected
SEASON_COLORS: dict[str, str] = {
    "2000/01": "#94A3B8", "2001/02": "#64748B", "2002/03": "#475569",
    "2003/04": "#FFD700",  # Invincibles – gold
    "2004/05": "#FFA500", "2005/06": "#FF8C00", "2006/07": "#F97316",
    "2007/08": "#EA580C", "2008/09": "#DC2626", "2009/10": "#B91C1C",
    "2010/11": "#991B1B", "2011/12": "#7F1D1D", "2012/13": "#6D28D9",
    "2013/14": "#7C3AED", "2014/15": "#8B5CF6", "2015/16": "#A78BFA",
    "2016/17": "#C4B5FD", "2017/18": "#0EA5E9", "2018/19": "#38BDF8",
    "2019/20": "#7DD3FC", "2020/21": "#BAE6FD", "2021/22": "#34D399",
    "2022/23": "#00E5FF",  # cyan
    "2023/24": "#F97316",  # orange
    "2024/25": "#A855F7",  # purple
    "2025/26": "#22C55E",  # green
}

RESULT_COLORS = {"W": "#22C55E", "D": "#F59E0B", "L": "#EF4444"}
TITLE_PACE_PTS = 97  # benchmark title-winning pace


# ── data ──────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading Arsenal data…")
def load_data() -> pd.DataFrame:
    return get_arsenal_enriched(DATA_PATH, EXTRA_PATH)


# ── layout helpers ────────────────────────────────────────────────────────────
def _base_layout(fig: go.Figure, yaxis_title: str, y_reversed: bool = False) -> go.Figure:
    yax: dict = dict(
        title=yaxis_title,
        gridcolor=GRID_COLOR,
        title_font=dict(size=14, color=CHART_TEXT),
        tickfont=dict(size=11, color=CHART_TEXT),
        title_standoff=10,
        showline=True, linewidth=1, linecolor="rgba(255,255,255,0.1)",
        zeroline=False,
    )
    if y_reversed:
        yax["autorange"] = "reversed"
        yax["dtick"] = 1

    fig.update_layout(
        plot_bgcolor=CHART_BG,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CHART_TEXT, size=12),
        margin=dict(l=60, r=24, t=40, b=60),
        legend=dict(
            font=dict(size=11, color=CHART_TEXT),
            title_font=dict(size=13, color=CHART_TEXT),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(
        dtick=1, range=[0.5, 38.5], gridcolor=GRID_COLOR,
        title="Matchweek",
        title_font=dict(size=14, color=CHART_TEXT),
        tickfont=dict(size=11, color=CHART_TEXT),
        title_standoff=20,
        showline=True, linewidth=1, linecolor="rgba(255,255,255,0.1)", zeroline=False,
    )
    fig.update_yaxes(**yax)
    return fig


def _add_bottling_zone(fig: go.Figure, bottling_week: int) -> go.Figure:
    fig.add_vrect(
        x0=bottling_week, x1=38.5,
        fillcolor=BOTTLING_FILL,
        line=dict(color=BOTTLING_LINE, width=1.5, dash="dash"),
        annotation_text="Bottling zone",
        annotation_position="top left",
        annotation_font=dict(color=ARSENAL_RED, size=11),
    )
    return fig


def _add_current_endpoint(fig: go.Figure, current_matchweek: int) -> go.Figure:
    """Add a vertical line and annotation for 2025/26 'We are here' (current matchweek)."""
    fig.add_vline(
        x=current_matchweek,
        line=dict(color=CURRENT_ENDPOINT_LINE, width=2.5),
        annotation_text="We are here",
        annotation_position="top",
        annotation_font=dict(color=CURRENT_ENDPOINT_LINE, size=12),
    )
    return fig


# ── KPI cards ─────────────────────────────────────────────────────────────────
def _kpi_card(season: str, pts: int, pos, gd: int, dropped: int) -> str:
    color = SEASON_COLORS.get(season, "#888")
    pos_str = f"#{int(pos)}" if pos is not None and not pd.isna(pos) else "–"
    gd_str  = f"+{gd}" if gd >= 0 else str(gd)
    return f"""
    <div style="border-left:4px solid {color};background:rgba(255,255,255,0.04);
                border-radius:8px;padding:10px 14px;min-width:150px;flex:1">
        <div style="font-size:13px;color:{color};font-weight:700;letter-spacing:.5px">{season}</div>
        <div style="font-size:26px;font-weight:800;color:#F5F7FB;margin:4px 0">{pts} <span style="font-size:14px;color:#94A3B8">pts</span></div>
        <div style="font-size:12px;color:#94A3B8">Pos: {pos_str} &nbsp;|&nbsp; GD: {gd_str}</div>
        <div style="font-size:12px;color:#F87171;margin-top:3px">Dropped from HT lead: <b>{dropped}</b> game(s)</div>
    </div>"""


# ── chart builders ─────────────────────────────────────────────────────────────

def build_position_chart(
    df: pd.DataFrame, bottling_week: int, current_matchweek: int | None = None
) -> go.Figure:
    fig = go.Figure()
    pos_df = df[df["Position"].notna()]
    for season in sorted(pos_df["Season"].unique()):
        s = pos_df[pos_df["Season"] == season].sort_values("Matchweek")
        color = SEASON_COLORS.get(season, "#888")
        fig.add_trace(go.Scatter(
            x=s["Matchweek"], y=s["Position"],
            mode="lines+markers", name=season,
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=6, color=color),
            customdata=s[["Points", "Result", "Opponent"]].values,
            hovertemplate=(
                "<b>%{fullData.name}</b> MW%{x}<br>"
                "Position: %{y}<br>"
                "Pts: %{customdata[0]} | %{customdata[1]} vs %{customdata[2]}"
                "<extra></extra>"
            ),
        ))
    fig = _base_layout(fig, "Position (1 = top)", y_reversed=True)
    fig = _add_bottling_zone(fig, bottling_week)
    if current_matchweek is not None:
        fig = _add_current_endpoint(fig, current_matchweek)
    fig.update_layout(legend_title_text="Season")
    return fig


def build_points_chart(
    df: pd.DataFrame, bottling_week: int, current_matchweek: int | None = None
) -> go.Figure:
    fig = go.Figure()
    # Title-pace reference line
    pace_x = list(range(1, 39))
    pace_y = [round(TITLE_PACE_PTS / 38 * mw, 1) for mw in pace_x]
    fig.add_trace(go.Scatter(
        x=pace_x, y=pace_y, mode="lines",
        name=f"Title pace ({TITLE_PACE_PTS} pts)",
        line=dict(color=ARSENAL_GOLD, width=1.5, dash="dot"),
        hoverinfo="skip",
    ))
    for season in sorted(df["Season"].unique()):
        s = df[df["Season"] == season].sort_values("Matchweek")
        color = SEASON_COLORS.get(season, "#888")
        fig.add_trace(go.Scatter(
            x=s["Matchweek"], y=s["Points"],
            mode="lines+markers", name=season,
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=6, color=color),
            customdata=s[["Result", "Opponent"]].values,
            hovertemplate=(
                "<b>%{fullData.name}</b> MW%{x}<br>"
                "Total pts: %{y}<br>"
                "%{customdata[0]} vs %{customdata[1]}"
                "<extra></extra>"
            ),
        ))
    fig = _base_layout(fig, "Cumulative points")
    fig = _add_bottling_zone(fig, bottling_week)
    if current_matchweek is not None:
        fig = _add_current_endpoint(fig, current_matchweek)
    fig.update_layout(legend_title_text="Season")
    return fig


def build_gd_chart(
    df: pd.DataFrame, bottling_week: int, current_matchweek: int | None = None
) -> go.Figure:
    fig = go.Figure()
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1)
    for season in sorted(df["Season"].unique()):
        s = df[df["Season"] == season].sort_values("Matchweek")
        color = SEASON_COLORS.get(season, "#888")
        fig.add_trace(go.Scatter(
            x=s["Matchweek"], y=s["GoalDifference"],
            mode="lines+markers", name=season,
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=5, color=color),
            hovertemplate=(
                "<b>%{fullData.name}</b> MW%{x}<br>"
                "Cumulative GD: %{y}<extra></extra>"
            ),
        ))
    fig = _base_layout(fig, "Cumulative goal difference")
    fig = _add_bottling_zone(fig, bottling_week)
    if current_matchweek is not None:
        fig = _add_current_endpoint(fig, current_matchweek)
    fig.update_layout(legend_title_text="Season")
    return fig


def build_heatmap(df: pd.DataFrame) -> go.Figure:
    """W/D/L result grid: rows = seasons (newest top), cols = matchweek 1-38."""
    seasons = sorted(df["Season"].unique(), reverse=True)
    mws = list(range(1, 39))
    result_num = {"W": 1, "D": 0, "L": -1}

    z, text, hover = [], [], []
    for season in seasons:
        # Build a plain dict keyed by matchweek to avoid duplicate-index issues
        s_rows = {
            int(row["Matchweek"]): row
            for _, row in df[df["Season"] == season].iterrows()
        }
        row_z, row_t, row_h = [], [], []
        for mw in mws:
            row = s_rows.get(mw)
            if row is not None and pd.notna(row["Result"]):
                r   = row["Result"]
                gf  = int(row["GoalsFor"])    if pd.notna(row["GoalsFor"])    else "?"
                ga  = int(row["GoalsAgainst"]) if pd.notna(row["GoalsAgainst"]) else "?"
                opp = row["Opponent"]          if pd.notna(row["Opponent"])    else "?"
                row_z.append(result_num[r])
                row_t.append(r)
                row_h.append(f"MW{mw} {season}<br>{r} vs {opp} ({gf}–{ga})")
            else:
                row_z.append(None)
                row_t.append("")
                row_h.append("")
        z.append(row_z)
        text.append(row_t)
        hover.append(row_h)

    fig = go.Figure(go.Heatmap(
        z=z, x=mws, y=seasons,
        text=text, customdata=hover,
        texttemplate="%{text}",
        textfont=dict(size=9, color="white"),
        hovertemplate="%{customdata}<extra></extra>",
        colorscale=[
            [0.0,  RESULT_COLORS["L"]],
            [0.5,  RESULT_COLORS["D"]],
            [1.0,  RESULT_COLORS["W"]],
        ],
        zmin=-1, zmax=1,
        showscale=False,
        xgap=2, ygap=2,
    ))
    fig.update_layout(
        plot_bgcolor=CHART_BG, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CHART_TEXT, size=11),
        # Taller top margin so legend has room above the grid
        margin=dict(l=80, r=24, t=80, b=60),
        xaxis=dict(
            title="Matchweek", dtick=1,
            title_font=dict(size=14, color=CHART_TEXT),
            tickfont=dict(size=10, color=CHART_TEXT),
            gridcolor="rgba(0,0,0,0)",
        ),
        yaxis=dict(
            title="Season",
            title_font=dict(size=14, color=CHART_TEXT),
            tickfont=dict(size=11, color=CHART_TEXT),
        ),
        # Slightly taller canvas so rows and legend breathe more
        height=max(320, len(seasons) * 50 + 140),
    )
    for label, col, xp in [
        ("Win",  RESULT_COLORS["W"], 0.74),
        ("Draw", RESULT_COLORS["D"], 0.82),
        ("Loss", RESULT_COLORS["L"], 0.90),
    ]:
        fig.add_annotation(
            x=xp, y=1.12, xref="paper", yref="paper",
            text=f'<span style="color:{col}">■</span> {label}',
            showarrow=False, font=dict(size=12, color=CHART_TEXT), align="center",
        )
    return fig


def build_dropped_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart: games dropped from HT lead per season (excludes 2025/26 — no HT data)."""
    hist = df[df["Season"] != "2025/26"]
    seasons = sorted(hist["Season"].unique())
    counts  = [int(hist[hist["Season"] == s]["DroppedFromLead"].sum()) for s in seasons]
    colors  = [SEASON_COLORS.get(s, "#888") for s in seasons]

    fig = go.Figure(go.Bar(
        x=seasons, y=counts,
        marker_color=colors,
        text=counts, textposition="outside",
        textfont=dict(color=CHART_TEXT, size=11),
        hovertemplate="<b>%{x}</b><br>Games dropped from HT lead: %{y}<extra></extra>",
    ))
    # Flag the notorious bottling seasons
    for i, s in enumerate(seasons):
        if s in ("2022/23", "2023/24") and counts[i] > 0:
            fig.add_annotation(
                x=s, y=counts[i], text="⚠️", showarrow=False,
                font=dict(size=14), yshift=18,
            )
    fig.update_layout(
        plot_bgcolor=CHART_BG, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CHART_TEXT, size=12),
        showlegend=False,
        margin=dict(l=50, r=24, t=30, b=80),
        xaxis=dict(
            title="Season", tickangle=-45,
            title_font=dict(size=14, color=CHART_TEXT),
            tickfont=dict(size=11, color=CHART_TEXT),
            gridcolor="rgba(0,0,0,0)",
        ),
        yaxis=dict(
            title="Games (led HT, didn't win)",
            gridcolor=GRID_COLOR,
            title_font=dict(size=13, color=CHART_TEXT),
            tickfont=dict(size=11, color=CHART_TEXT),
            zeroline=False,
        ),
    )
    return fig


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="Arsenal Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(f"""
    <style>
    html, body, [class*="css"] {{ background-color:{APP_BG}; color:{CHART_TEXT}; }}
    .block-container {{ padding-top:2.5rem; }}
    .section-title {{
        font-size:15px; font-weight:700; color:{CHART_TEXT};
        padding:6px 0 6px 12px; margin:0.5rem 0 0.2rem 0;
        border-left:3px solid {ARSENAL_RED};
    }}
    .kpi-row {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:1rem; }}
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown(f"""
    <div style="margin-bottom:1.2rem">
        <span style="font-size:28px;font-weight:900;color:{ARSENAL_RED};letter-spacing:1px">⚽ Arsenal</span>
        <span style="font-size:22px;font-weight:600;color:{CHART_TEXT}"> Season Dashboard</span>
        <div style="font-size:13px;color:#64748B;margin-top:2px">
            Premier League position, points, goal difference and result patterns — all seasons
        </div>
    </div>
    """, unsafe_allow_html=True)

    df = load_data()
    if df.empty:
        st.error("No data found.")
        return

    all_seasons = sorted(df["Season"].unique())
    default_seasons = [s for s in ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"]
                       if s in all_seasons]

    with st.sidebar:
        st.header("Filters")
        selected = st.multiselect("Select seasons", options=all_seasons, default=default_seasons)
        bottling_week = st.slider(
            "Bottling phase matchweek", min_value=1, max_value=38, value=28,
            help="Shades everything from this matchweek to the end in red.",
        )
        st.markdown("---")
        st.markdown(f"""
        <div style="font-size:12px;color:#64748B">
            <b style="color:{ARSENAL_GOLD}">─ ─</b> Title pace = {TITLE_PACE_PTS} pts/38 games<br>
            <b style="color:{CURRENT_ENDPOINT_LINE}">│</b> We are here (2025/26 current matchweek)<br><br>
            <b style="color:{RESULT_COLORS['W']}">■</b> Win &nbsp;
            <b style="color:{RESULT_COLORS['D']}">■</b> Draw &nbsp;
            <b style="color:{RESULT_COLORS['L']}">■</b> Loss
        </div>
        """, unsafe_allow_html=True)

    if not selected:
        st.info("Select at least one season from the sidebar.")
        return

    filtered = df[df["Season"].isin(selected)].copy()

    # Current 2025/26 endpoint: show "We are here" on position/points/GD charts
    current_mw: int | None = None
    if "2025/26" in selected:
        s2526 = filtered[filtered["Season"] == "2025/26"]
        if not s2526.empty:
            current_mw = int(s2526["Matchweek"].max())

    # ── KPI cards ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Season Summary</div>', unsafe_allow_html=True)
    kpi_html = '<div class="kpi-row">'
    for season in sorted(selected):
        s = filtered[filtered["Season"] == season]
        if s.empty:
            continue
        last = s.loc[s["Matchweek"].idxmax()]
        kpi_html += _kpi_card(
            season,
            int(last["Points"]),
            last["Position"],
            int(last["GoalDifference"]),
            int(s["DroppedFromLead"].sum()),
        )
    kpi_html += "</div>"
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ── Result heatmap ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Result Heatmap (W / D / L per matchweek)</div>', unsafe_allow_html=True)
    st.plotly_chart(build_heatmap(filtered), use_container_width=True)

    # ── Position + Points ──────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-title">League position by matchweek</div>', unsafe_allow_html=True)
        pos_df = filtered[filtered["Position"].notna()]
        if pos_df.empty:
            st.info("No position data for selected seasons (2025/26 only).")
        else:
            st.plotly_chart(build_position_chart(pos_df, bottling_week, current_mw), use_container_width=True)
    with col2:
        st.markdown('<div class="section-title">Cumulative points vs title pace</div>', unsafe_allow_html=True)
        st.plotly_chart(build_points_chart(filtered, bottling_week, current_mw), use_container_width=True)

    # ── GD + Dropped ───────────────────────────────────────────────────────────
    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-title">Cumulative goal difference</div>', unsafe_allow_html=True)
        st.plotly_chart(build_gd_chart(filtered, bottling_week, current_mw), use_container_width=True)
    with col4:
        st.markdown('<div class="section-title">Games dropped from half-time lead</div>', unsafe_allow_html=True)
        hist_only = filtered[filtered["Season"] != "2025/26"]
        if hist_only.empty:
            st.info("Select historical seasons (pre-2025/26) to see this chart.")
        else:
            st.plotly_chart(build_dropped_chart(hist_only), use_container_width=True)

    # ── footer ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:12px;color:#475569">'
        f'Position = end-of-matchweek standing (after all 10 fixtures in each round). '
        f'2025/26: Arsenal results only — position not computed. '
        f'Title pace = {TITLE_PACE_PTS} pts / 38 games. '
        f'Half-time drop data not available for 2025/26.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
