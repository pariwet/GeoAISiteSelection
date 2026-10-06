from __future__ import annotations

import os
import re
import time
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover
    st_autorefresh = None

st.set_page_config(page_title="AI Site Selection Challenge", page_icon="🌍", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
:root { --ink:#ecf4ff; --muted:#8fa8c2; --bg:#07111f; --panel:#0d1d31; --line:#203b59; --cyan:#56e0e7; --lime:#c9f56a; --coral:#ff7c6b; }
html, body, [class*="css"] { font-family:'Space Grotesk',sans-serif; }
.stApp { background:radial-gradient(circle at 90% 0%, #123252 0%, var(--bg) 40%); color:var(--ink); }
.block-container { padding-top:1.7rem; max-width:1500px; padding-bottom:6rem; }
[data-testid="stSidebar"] { background:#091827; border-right:1px solid var(--line); }
[data-testid="stMetric"] { background:rgba(13,29,49,.86); border:1px solid var(--line); border-radius:14px; padding:14px; }
[data-testid="stMetricLabel"] { color:var(--muted); }
[data-testid="stMetricValue"] { color:var(--ink); }
.kicker { color:var(--cyan); font-family:'DM Mono',monospace; font-size:.76rem; letter-spacing:.12em; text-transform:uppercase; }
.hero { font-size:2.55rem; font-weight:700; line-height:1.03; margin:.25rem 0 .65rem; }
.subtle { color:var(--muted); }
.challenge-card { background:linear-gradient(135deg,rgba(16,42,67,.94),rgba(9,24,40,.94)); border:1px solid var(--line); border-radius:18px; padding:22px; box-shadow:0 18px 50px rgba(0,0,0,.18); }
.badge { display:inline-block; padding:5px 10px; border-radius:999px; background:#183653; color:var(--cyan); font-size:.78rem; font-weight:600; }
.score-pill { font-family:'DM Mono',monospace; color:var(--lime); font-size:1.15rem; }
.small-note { color:var(--muted); font-size:.82rem; }
.factor-title { color:var(--cyan); font-weight:600; margin-bottom:0; }
</style>
""", unsafe_allow_html=True,
)

# Five flood factors for the site-selection challenge.
FACTORS = ["Slope", "Elevation", "Rainfall", "Distance to river", "Drainage capacity"]
DEFAULT_WEIGHTS = {factor: 0 for factor in FACTORS}
BENCHMARK_WEIGHTS = {"Slope": 18, "Elevation": 24, "Rainfall": 28, "Distance to river": 18, "Drainage capacity": 12}


def init_state() -> None:
    defaults: dict[str, Any] = {
        "weights": DEFAULT_WEIGHTS.copy(),
        "mission1_score": 0,
        "mission2_score": 0,
        "selected_sites": [],
        "chat": [],
        "team_name": "",
        "teams": [],
        "team_scores": {},
        "map_generated": False,
        "timer_started": time.monotonic(),
        "nav": "Challenge",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    # If the app is hot-reloaded after a factor-set change, start the new round cleanly.
    if set(st.session_state.get("weights", {}).keys()) != set(FACTORS):
        st.session_state.weights = DEFAULT_WEIGHTS.copy()
        st.session_state.map_generated = False
        st.session_state.selected_sites = []
        st.session_state.mission1_score = 0
        st.session_state.mission2_score = 0


def make_data(n: int = 12) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(42)
    y, x = np.mgrid[0:n, 0:n]
    elevation = 35 + .9*x + 1.5*y + 11*np.exp(-((x-8)**2+(y-3)**2)/18) + rng.normal(0, 1.5, (n,n))
    slope_raw = np.hypot(np.gradient(elevation, axis=0), np.gradient(elevation, axis=1))
    rainfall = 125 + .8*y + 24*np.exp(-((x-3)**2+(y-9)**2)/25) + rng.normal(0, 3, (n,n))
    river_distance = np.abs(y - (2.3 + .34*x + 1.0*np.sin(x/2))) + .2
    def norm(a: np.ndarray) -> np.ndarray:
        return (a - a.min()) / (a.max() - a.min())
    elevation_n, slope_n = norm(elevation), norm(slope_raw)
    drainage_capacity = np.clip(.65*elevation_n + .35*(1-slope_n), 0, 1)
    return {
        "x": x, "y": y, "slope": slope_n, "elevation": 1-elevation_n,
        "rainfall": norm(rainfall), "distance_to_river": norm(river_distance),
        "drainage_capacity": 1-drainage_capacity,
        "elevation_m": elevation,
    }


DATA = make_data()
LAYER_KEYS = {"Slope":"slope", "Elevation":"elevation", "Rainfall":"rainfall", "Distance to river":"distance_to_river", "Drainage capacity":"drainage_capacity"}


def risk_map(weights: dict[str, float]) -> np.ndarray:
    values = np.array([weights[f] for f in FACTORS], dtype=float) / 100
    layers = np.stack([DATA[LAYER_KEYS[f]] for f in FACTORS])
    return np.clip(np.tensordot(values, layers, axes=1), 0, 1)


def mission1_score(weights: dict[str, int]) -> tuple[int, dict[str, int]]:
    component = {f: max(0, 100 - abs(weights[f] - BENCHMARK_WEIGHTS[f]) * 3) for f in FACTORS}
    return min(100, int(round(sum(component.values()) / len(component)))) , component


def mission2_score(selected: list[tuple[int, int]], risk: np.ndarray) -> tuple[int, dict[str, float]]:
    if not selected:
        return 0, {"safety":0, "coverage":0}
    safety = float(np.mean([1-risk[r,c] for r,c in selected]))
    coverage = len({(r >= 6, c >= 6) for r,c in selected}) / 4
    score = max(0, int(round((.65*safety + .35*coverage) * 100 - max(0, len(selected)-4)*3)))
    return score, {"safety":safety, "coverage":coverage}


def cell_label(r: int, c: int) -> str:
    return f"Cell {chr(65+r)}{c+1}"


def parse_cell_names(raw: str) -> tuple[list[tuple[int, int]], list[str]]:
    """Parse learner input such as 'A1, B2, C5' into grid coordinates."""
    cells: list[tuple[int, int]] = []
    invalid: list[str] = []
    for token in raw.split(","):
        token = token.strip().upper().replace("CELL ", "")
        if not token:
            continue
        match = re.fullmatch(r"([A-L])(1[0-2]|[1-9])", token)
        if not match:
            invalid.append(token)
            continue
        cell = (ord(match.group(1)) - 65, int(match.group(2)) - 1)
        if cell not in cells:
            cells.append(cell)
    if len(cells) > 5:
        invalid.extend([cell_label(r, c) for r, c in cells[5:]])
        cells = cells[:5]
    return cells, invalid


def heatmap(title: str, z: np.ndarray, colorscale: str = "Turbo", selected: list[tuple[int,int]] | None = None, selectable: bool = False) -> go.Figure:
    fig = go.Figure(go.Heatmap(z=z, colorscale=colorscale, zmin=0, zmax=1, x=[str(i+1) for i in range(z.shape[1])], y=[chr(65+i) for i in range(z.shape[0])], hovertemplate="Cell %{y}%{x}<br>Normalized value: %{z:.2f}<extra></extra>"))
    if selectable:
        # Transparent point layer makes individual heatmap cells selectable in Streamlit.
        # The visible heatmap remains the teaching visualization underneath.
        xs, ys = [], []
        for row in range(z.shape[0]):
            for col in range(z.shape[1]):
                xs.append(str(col + 1)); ys.append(chr(65 + row))
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", marker=dict(size=27, color="rgba(255,255,255,0.02)"), showlegend=False, hoverinfo="skip", selectedpoints=[]))
    for r,c in selected or []:
        fig.add_trace(go.Scatter(x=[str(c+1)], y=[chr(65+r)], mode="markers", marker=dict(size=22, color="#ff4fa3", symbol="circle-open", line=dict(width=3, color="#ffd1e7")), showlegend=False, hoverinfo="skip"))
    fig.update_layout(title=title, height=330, margin=dict(l=8,r=8,t=42,b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ecf4ff"), xaxis_title="Column", yaxis_title="Row")
    return fig


def call_ai(messages: list[dict[str,str]]) -> str:
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return "I am in demo mode right now. Add OPENAI_API_KEY to enable the live AI advisor. Based on the current evidence, explain which factors you prioritized and how that changes the risk map."
    client = OpenAI()
    model = os.getenv("SITE_SELECTION_LLM_MODEL", "gpt-5-mini")
    kwargs: dict[str, Any] = {"model":model, "messages":messages, "max_completion_tokens":500}
    if model.startswith("gpt-5"):
        kwargs["extra_body"] = {"reasoning":{"effort":"low"}}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or "I could not generate an answer."


def advisor_prompt() -> str:
    return """You are Earthy, the friendly AI advisor inside an undergraduate GIS flood-risk game. Answer in concise, plain English. Use only the supplied normalized factor layers, player weights, selected cells, and scores. Never invent measurements or claim this is a real flood forecast. Explain trade-offs: low elevation, rainfall, slope, and short distance to river can increase flood risk; high drainage capacity reduces risk. Ask a reflective follow-up question when helpful. Do not reveal the benchmark weights unless the learner asks about scoring."""


init_state()
if st.session_state.nav not in {"Challenge", "Facilitator guide"}:
    st.session_state.nav = "Challenge"
if st_autorefresh:
    st_autorefresh(interval=1000, key="game_clock")
remaining = max(0, 20*60 - int(time.monotonic() - st.session_state.timer_started))
risk = risk_map(st.session_state.weights)

# Sidebar HUD and navigation
st.sidebar.markdown("<div class='kicker'>FLOODOPS // LIVE CLASSROOM</div>", unsafe_allow_html=True)
st.sidebar.markdown("# AI Site Selection Challenge")
st.session_state.nav = st.sidebar.radio("Navigate", ["Challenge", "Facilitator guide"], index=["Challenge","Facilitator guide"].index(st.session_state.nav), label_visibility="collapsed")
st.sidebar.divider()
mm, ss = divmod(remaining, 60)
st.sidebar.text_input("Team name", key="team_name", placeholder="Enter your team")
if st.sidebar.button("Join", use_container_width=True):
    name = st.session_state.get("team_name", "").strip()
    if name and name not in st.session_state.teams:
        st.session_state.teams.append(name)
        st.session_state.team_scores[name] = {"Mission 1": 0, "Mission 2": 0}
        st.sidebar.success(f"{name} joined")
st.sidebar.metric("Time remaining", f"{mm:02d}:{ss:02d}")
a,b = st.sidebar.columns(2)
a.metric("Mission 1", f"{st.session_state.mission1_score}/100")
b.metric("Mission 2", f"{st.session_state.mission2_score}/100")
st.sidebar.markdown("**TOP 3 TEAMS**")
if st.session_state.teams:
    rows = []
    for team in st.session_state.teams:
        scores = st.session_state.team_scores.get(team, {"Mission 1": 0, "Mission 2": 0})
        rows.append({"Team": team, "M1": scores["Mission 1"], "M2": scores["Mission 2"], "Total": scores["Mission 1"] + scores["Mission 2"]})
    top3 = pd.DataFrame(rows).sort_values(["Total", "Team"], ascending=[False, True]).head(3).reset_index(drop=True)
    top3.insert(0, "#", range(1, len(top3) + 1))
    st.sidebar.dataframe(top3, hide_index=True, use_container_width=True)
else:
    st.sidebar.caption("No teams yet")

if st.session_state.nav == "Challenge":
    st.markdown("<div class='kicker'>ROUND 01 // URBAN RESILIENCE</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero'>Choose the safest place.</div>", unsafe_allow_html=True)
    st.markdown("<p class='subtle'>Build the evidence. Generate the map. Then place evacuation sites.</p>", unsafe_allow_html=True)
    top = st.columns([1.25,1,1])
    with top[0]:
        st.markdown("<div class='challenge-card'><span class='badge'>LIVE CHALLENGE</span><h3>Flood resilience sprint</h3><p class='subtle'>Two connected missions. Every choice must be explainable.</p><div class='score-pill'>200 pts available</div></div>", unsafe_allow_html=True)
    with top[1]: st.metric("Teams on board", len(st.session_state.teams), "Join in left panel")
    with top[2]: st.metric("Your total", st.session_state.mission1_score + st.session_state.mission2_score, "of 200")

    st.divider()
    st.markdown("<div class='kicker'>MISSION 1 // FACTOR WEIGHTING</div>", unsafe_allow_html=True)
    st.markdown("## Decide what matters most.")
    st.markdown("<p class='subtle'>Set the five factors on the left. Their evidence maps appear on the right. All weights start at 0% on first launch.</p>", unsafe_allow_html=True)
    left, right = st.columns([0.8, 2.2], gap="large")
    with left:
        for idx, factor in enumerate(FACTORS):
            st.session_state.weights[factor] = st.slider(factor, 0, 100, int(st.session_state.weights[factor]), 1, key=f"weight_{idx}")
        total = sum(st.session_state.weights.values())
        st.metric("Weight total", f"{total}%", "Ready" if total == 100 else "Must equal 100%")
        if st.button("Generate flood-risk map →", type="primary", disabled=total != 100):
            st.session_state.map_generated = True
            st.session_state.mission1_score = mission1_score(st.session_state.weights)[0]
            current_team = st.session_state.get("team_name", "").strip()
            if current_team in st.session_state.team_scores:
                st.session_state.team_scores[current_team]["Mission 1"] = st.session_state.mission1_score
            st.toast("Flood-risk map generated. Mission 2 is ready below.")
    with right:
        st.markdown("### Factor maps · 2D evidence layers")
        map_cols = st.columns(2)
        for idx, factor in enumerate(FACTORS):
            with map_cols[idx % 2]:
                st.markdown(f"<p class='factor-title'>{factor}</p>", unsafe_allow_html=True)
                st.plotly_chart(heatmap(factor, DATA[LAYER_KEYS[factor]], "Blues" if factor == "Distance to river" else "Viridis"), use_container_width=True, key=f"factor_map_{idx}")
    total = sum(st.session_state.weights.values())
    if total != 100:
        st.warning("Adjust the sliders until the weight total equals 100%. Then generate the flood-risk map.")
    else:
        st.success("Weights total 100%. Click Generate flood-risk map when ready.")

    st.divider()
    st.markdown("<div class='kicker'>MISSION 2 // EVACUATION SITES</div>", unsafe_allow_html=True)
    if not st.session_state.map_generated:
        st.info("Mission 2 will activate inside the generated flood-risk map after Mission 1 is submitted.")
    else:
        st.markdown("### Flood-risk map · generated from your weights")
        st.markdown("<p class='subtle'>Use the map as a reference. Enter 2–5 cell names separated by commas, apply them, then submit.</p>", unsafe_allow_html=True)
        # Keep the map as a visual reference; cell selection is explicit text input.
        st.plotly_chart(heatmap("Flood-risk map reference", risk, "RdYlGn_r", st.session_state.selected_sites), use_container_width=True, key="risk_map_mission2")
        st.caption("Enter cell names exactly as shown on the grid. Separate multiple cells with commas, for example: A1, B2, C5.")
        input_col, apply_col = st.columns([2.4, 1])
        with input_col:
            cell_input = st.text_input("Evacuation cell(s)", key="mission2_cell_input", placeholder="A1, B2, C5")
        with apply_col:
            st.write("")
            if st.button("Apply cells", use_container_width=True, key="apply_cells"):
                parsed_cells, invalid_cells = parse_cell_names(cell_input)
                st.session_state.selected_sites = parsed_cells
                if invalid_cells:
                    st.warning("Invalid cell name(s): " + ", ".join(invalid_cells))
                else:
                    st.toast("Cell selection applied")
        score2, metrics = mission2_score(st.session_state.selected_sites, risk)
        m1,m2,m3 = st.columns(3)
        m1.metric("Mission 2 score", f"{score2}/100")
        m2.metric("Safety", f"{metrics['safety']:.0%}")
        m3.metric("Coverage", f"{metrics['coverage']:.0%}")
        ca, cb = st.columns([1, 1])
        with ca:
            if st.button("Clear selected cells"):
                st.session_state.selected_sites = []; st.rerun()
        with cb:
            if st.button("Submit", type="primary", use_container_width=True, disabled=not (2 <= len(st.session_state.selected_sites) <= 5), key="submit_cells_top"):
                st.session_state.mission2_score = score2
                current_team = st.session_state.get("team_name", "").strip()
                if current_team in st.session_state.team_scores:
                    st.session_state.team_scores[current_team]["Mission 2"] = st.session_state.mission2_score
                st.toast("Evacuation sites submitted!")

    if st.session_state.teams:
        st.markdown("### Live Team Board")
        board_rows = []
        for team in st.session_state.teams:
            scores = st.session_state.team_scores.get(team, {"Mission 1": 0, "Mission 2": 0})
            board_rows.append({"Team": team, "Mission 1": scores["Mission 1"], "Mission 2": scores["Mission 2"], "Total": scores["Mission 1"] + scores["Mission 2"]})
        board = pd.DataFrame(board_rows).sort_values(["Total", "Team"], ascending=[False, True]).reset_index(drop=True)
        board.insert(0, "Rank", range(1, len(board)+1))
        st.dataframe(board, hide_index=True, use_container_width=True)

else:
    st.markdown("<div class='kicker'>FACILITATOR MODE</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero'>Run the challenge in class.</div>", unsafe_allow_html=True)
    st.markdown("The round begins at **20:00**. Students start with all five weights at **0%**, generate the map only after reaching 100%, and then click 2–5 evacuation sites directly on the generated map.")
    st.markdown("### Data dictionary")
    st.dataframe(pd.DataFrame({"Layer":FACTORS,"Teaching meaning":["Relative runoff acceleration from terrain gradient","Low elevation is treated as more exposed","Relative rainfall intensity","Normalized distance to the modeled river corridor","Relative ability of terrain to drain water; high capacity lowers risk"]}), hide_index=True, use_container_width=True)
    st.markdown("### Production upgrade path")
    st.markdown("Use Postgres/Supabase for shared teams and real-time leaderboard events; replace simulated arrays with GeoTIFF/rasterio layers; keep the AI call server-side and log consented chat for assessment review.")
