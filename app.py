import os
import time
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from openai import OpenAI

# ==========================================
# 1. PAGE CONFIGURATION & STYLING (Kahoot Style)
# ==========================================
st.set_page_config(
    page_title="AI Site Selection Challenge",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #4A90E2;
        text-align: center;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.2rem;
        text-align: center;
        color: #7B889B;
        margin-bottom: 20px;
    }
    .score-card {
        background-color: #1E293B;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border: 2px solid #334155;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #38BDF8;
    }
    </style>
""",
    unsafe_allow_html=True,
)

import streamlit as st

# Initialize a key if it doesn't exist yet
if "my_key" not in st.session_state:
    st.session_state.my_key = "initial_value"

# Access or modify it
st.session_state.my_key = "new_value"
st.write(st.session_state["my_key"])

# Initialize Session State
if "team_name" not in st.session_state:
    st.session_state.team_name = "Team Explorer"
if "m1_score" not in st.session_state:
    st.session_state.m1_score = 0.0
if "m2_score" not in st.session_state:
    st.session_state.m2_score = 0.0
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()
`st.state_dict` does not exist in Streamlit. 

# ==========================================
# 2. SYNTHETIC SPATIAL DATA GENERATION (50x50 Grid)
# ==========================================
@st.cache_data
def generate_spatial_data():
    grid_size = 50
    x = np.linspace(0, 49, grid_size)
    y = np.linspace(0, 49, grid_size)
    X, Y = np.meshgrid(x, y)

    # Elevation (m): High on left/top, low in center valley
    Elevation = 150 - (
        np.sqrt((X - 25) ** 2 + (Y - 25) ** 2) * 2.5 + np.sin(X / 5) * 10
    )
    Elevation = np.clip(Elevation, 10, 200)

    # Slope (%): Gradient of elevation
    dy, dx = np.gradient(Elevation)
    Slope = np.sqrt(dx**2 + dy**2) * 2

    # Rainfall (mm): High rainfall gradient towards top-right
    Rainfall = 150 + X * 2 + Y * 3 + np.random.normal(0, 5, (grid_size, grid_size))

    # River Path: Bisecting diagonally
    River_Dist = np.abs(Y - (0.8 * X + 5))

    # Road Network: Two intersecting main corridors
    Road_Dist = np.minimum(np.abs(X - 20), np.abs(Y - 30))

    # Building Density (0 to 1)
    Building = np.exp(-((X - 30) ** 2 + (Y - 20) ** 2) / 200) + np.exp(
        -((X - 10) ** 2 + (Y - 40) ** 2) / 150
    )
    Building = np.clip(Building, 0, 1)

    # Hospital Location at Grid (35, 35)
    Hospital_X, Hospital_Y = 35, 35
    Hospital_Dist = np.sqrt((X - Hospital_X) ** 2 + (Y - Hospital_Y) ** 2)

    return {
        "X": X,
        "Y": Y,
        "Elevation": Elevation,
        "Slope": Slope,
        "Rainfall": Rainfall,
        "River_Dist": River_Dist,
        "Road_Dist": Road_Dist,
        "Building": Building,
        "Hospital_Dist": Hospital_Dist,
        "Hospital_Pos": (Hospital_X, Hospital_Y),
    }


data = generate_spatial_data()

# Optimal Expert Weights for Benchmark
OPTIMAL_WEIGHTS = {
    "Elevation": 25,
    "Slope": 15,
    "Rainfall": 20,
    "River_Dist": 20,
    "Road_Dist": 5,
    "Building": 10,
    "Hospital_Dist": 5,
}

# ==========================================
# 3. SIDEBAR: GAME DASHBOARD & LEADERBOARD
# ==========================================
with st.sidebar:
    st.image(
        "https://img.icons8.com/isometric-folders/100/globe-earth.png", width=80
    )
    st.title("🎮 Game Control")
    st.session_state.team_name = st.text_input(
        "Team Name", st.session_state.team_name
    )

    # Countdown Timer (15 Minutes Challenge)
    elapsed = int(time.time() - st.session_state.start_time)
    remaining = max(0, 900 - elapsed)
    mins, secs = divmod(remaining, 60)
    st.metric("⏳ Time Remaining", f"{mins:02d}:{secs:02d}")

    st.markdown("---")
    st.subheader("🏆 Live Leaderboard")
    leaderboard_data = pd.DataFrame(
        [
            {
                "Team": st.session_state.team_name,
                "M1": round(st.session_state.m1_score, 1),
                "M2": round(st.session_state.m2_score, 1),
                "Total": round(
                    st.session_state.m1_score + st.session_state.m2_score, 1
                ),
            },
            {"Team": "HydroBot AI", "M1": 92.0, "M2": 88.5, "Total": 180.5},
            {"Team": "GeoMaster", "M1": 85.0, "M2": 82.0, "Total": 167.0},
            {"Team": "UrbanPlanner_01", "M1": 78.0, "M2": 74.5, "Total": 152.5},
        ]
    ).sort_values(by="Total", ascending=False)

    st.dataframe(leaderboard_data, hide_index=True, use_container_width=True)

# ==========================================
# 4. MAIN CONTENT HEADER
# ==========================================
st.markdown(
    '<div class="main-title">🌊 AI Site Selection Challenge</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Spatial AI in Action: Flood Risk Mapping & Evacuation Planning</div>',
    unsafe_allow_html=True,
)

col_score1, col_score2, col_score3 = st.columns(3)
with col_score1:
    st.markdown(
        f'<div class="score-card">Mission 1 Score<div class="metric-value">{st.session_state.m1_score:.1f} / 100</div></div>',
        unsafe_allow_html=True,
    )
with col_score2:
    st.markdown(
        f'<div class="score-card">Mission 2 Score<div class="metric-value">{st.session_state.m2_score:.1f} / 100</div></div>',
        unsafe_allow_html=True,
    )
with col_score3:
    total_sc = st.session_state.m1_score + st.session_state.m2_score
    st.markdown(
        f'<div class="score-card">Total Score<div class="metric-value">{total_sc:.1f} / 200</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

tab1, tab2, tab3 = st.tabs(
    [
        "🎯 Mission 1: Flood Risk Weights",
        "📍 Mission 2: Evacuation Sites",
        "🤖 Chat with AI Advisor",
    ]
)

# ==========================================
# 5. TAB 1: MISSION 1 - WEIGHT CONFIGURATION & 3D MAP
# ==========================================
with tab1:
    st.header("Mission 1: Multi-Criteria Flood Risk Weighting")
    st.write(
        "Assign weights (%) to each flood factor. Total weights must equal **100%**."
    )

    c1, c2 = st.columns([1, 2])

    with c1:
        st.subheader("⚙️ Factor Weights")
        w_elev = st.slider("Elevation (Low Elev = High Risk)", 0, 50, 25)
        w_slope = st.slider("Slope (Flat = High Risk)", 0, 50, 15)
        w_rain = st.slider("Rainfall Intensity", 0, 50, 20)
        w_river = st.slider("Proximity to River", 0, 50, 20)
        w_road = st.slider("Proximity to Road", 0, 30, 5)
        w_build = st.slider("Building Density", 0, 30, 10)
        w_hosp = st.slider("Distance to Hospital", 0, 30, 5)

        total_w = (
            w_elev + w_slope + w_rain + w_river + w_road + w_build + w_hosp
        )

        if total_w != 100:
            st.warning(f"⚠️ Total Weight: **{total_w}%** (Must be 100%)")
        else:
            st.success("✅ Total Weight: **100%**")

        if st.button("🚀 Calculate Flood Risk Map", use_container_width=True):
            # Calculate Risk Matrix Normalized 0..1
            norm_elev = 1 - (
                data["Elevation"] - data["Elevation"].min()
            ) / (data["Elevation"].max() - data["Elevation"].min())
            norm_slope = 1 - (data["Slope"] - data["Slope"].min()) / (
                data["Slope"].max() - data["Slope"].min()
            )
            norm_rain = (data["Rainfall"] - data["Rainfall"].min()) / (
                data["Rainfall"].max() - data["Rainfall"].min()
            )
            norm_river = 1 - (
                data["River_Dist"] - data["River_Dist"].min()
            ) / (data["River_Dist"].max() - data["River_Dist"].min())
            norm_road = (data["Road_Dist"] - data["Road_Dist"].min()) / (
                data["Road_Dist"].max() - data["Road_Dist"].min()
            )
            norm_build = data["Building"]
            norm_hosp = (data["Hospital_Dist"] - data["Hospital_Dist"].min()) / (
                data["Hospital_Dist"].max() - data["Hospital_Dist"].min()
            )

            risk_map = (
                w_elev * norm_elev
                + w_slope * norm_slope
                + w_rain * norm_rain
                + w_river * norm_river
                + w_road * norm_road
                + w_build * norm_build
                + w_hosp * norm_hosp
            ) / 100.0

            st.session_state["risk_map"] = risk_map

            # Calculate M1 Score
            user_w = {
                "Elevation": w_elev,
                "Slope": w_slope,
                "Rainfall": w_rain,
                "River_Dist": w_river,
                "Road_Dist": w_road,
                "Building": w_build,
                "Hospital_Dist": w_hosp,
            }
            diff = sum(
                abs(user_w[k] - OPTIMAL_WEIGHTS[k]) for k in OPTIMAL_WEIGHTS
            )
            st.session_state.m1_score = max(0.0, 100.0 - diff * 1.5)
            st.rerun()

    with c2:
        st.subheader("🌋 3D Terrain & Calculated Risk Map")

        # 3D Surface Plot of Terrain Elevation
        fig_3d = go.Figure(
            data=[
                go.Surface(
                    z=data["Elevation"],
                    x=data["X"],
                    y=data["Y"],
                    colorscale="Viridis",
                )
            ]
        )
        fig_3d.update_layout(
            title="3D Elevation Surface (Topography)",
            autosize=True,
            height=350,
            margin=dict(l=0, r=0, b=0, t=30),
        )
        st.plotly_chart(fig_3d, use_container_width=True)

        if "risk_map" in st.session_state:
            fig_risk = px.imshow(
                st.session_state["risk_map"],
                labels=dict(x="X Coordinate", y="Y Coordinate", color="Risk Level"),
                x=np.arange(50),
                y=np.arange(50),
                color_continuous_scale="Reds",
                title="Generated Flood Risk Map (0 = Safe, 1 = Extreme Risk)",
            )
            fig_risk.add_scatter(
                x=[data["Hospital_Pos"][0]],
                y=[data["Hospital_Pos"][1]],
                mode="markers",
                marker=dict(size=12, color="blue", symbol="cross"),
                name="Hospital",
            )
            st.plotly_chart(fig_risk, use_container_width=True)

# ==========================================
# 6. TAB 2: MISSION 2 - SITE SELECTION
# ==========================================
with tab2:
    st.header("Mission 2: Select 3 Evacuation Shelter Sites")
    st.write(
        "Select coordinates $(X, Y)$ for 3 evacuation shelters. Ideal sites must have **Low Flood Risk**, **High Road Accessibility**, and **Proximity to Hospital**."
    )

    col_m21, col_m22 = st.columns([1, 2])

    with col_m21:
        st.subheader("📌 Site Coordinates")
        s1_x = st.number_input("Site 1 X", 0, 49, 10)
        s1_y = st.number_input("Site 1 Y", 0, 49, 10)
        st.markdown("---")
        s2_x = st.number_input("Site 2 X", 0, 49, 25)
        s2_y = st.number_input("Site 2 Y", 0, 49, 40)
        st.markdown("---")
        s3_x = st.number_input("Site 3 X", 0, 49, 40)
        s3_y = st.number_input("Site 3 Y", 0, 49, 15)

        if st.button("Evaluate Evacuation Sites", use_container_width=True):
            if "risk_map" not in st.session_state:
                st.error("Please calculate the Flood Risk Map in Mission 1 first!")
            else:
                rm = st.session_state["risk_map"]
                sites = [(s1_x, s1_y), (s2_x, s2_y), (s3_x, s3_y)]
                site_scores = []

                for sx, sy in sites:
                    risk_val = rm[sy, sx]
                    road_acc = 1.0 - (
                        data["Road_Dist"][sy, sx] / data["Road_Dist"].max()
                    )
                    hosp_prox = 1.0 - (
                        data["Hospital_Dist"][sy, sx] / data["Hospital_Dist"].max()
                    )

                    # Score per site
                    score = (
                        (1.0 - risk_val) * 40.0
                        + road_acc * 30.0
                        + hosp_prox * 30.0
                    )
                    site_scores.append(score)

                st.session_state.m2_score = float(np.mean(site_scores))
                st.rerun()

    with col_m22:
        st.subheader("🗺️ Selected Shelter Overlay Map")
        if "risk_map" in st.session_state:
            fig_sites = px.imshow(
                st.session_state["risk_map"],
                color_continuous_scale="Reds",
                title="Shelter Sites vs. Flood Risk Heatmap",
            )
            # Add Hospital
            fig_sites.add_scatter(
                x=[data["Hospital_Pos"][0]],
                y=[data["Hospital_Pos"][1]],
                mode="markers",
                marker=dict(size=14, color="blue", symbol="hospital"),
                name="Hospital",
            )
            # Add Selected Sites
            fig_sites.add_scatter(
                x=[s1_x, s2_x, s3_x],
                y=[s1_y, s2_y, s3_y],
                mode="markers+text",
                text=["Site 1", "Site 2", "Site 3"],
                textposition="top center",
                marker=dict(size=14, color="green", symbol="star"),
                name="Evacuation Shelters",
            )
            st.plotly_chart(fig_sites, use_container_width=True)
        else:
            st.info("Complete Mission 1 first to display the overlay map.")

# ==========================================
# 7. TAB 3: REAL-TIME LLM AI ADVISOR
# ==========================================
with tab3:
    st.header("🤖 Interactive GeoAI Advisor")
    st.write(
        "Ask questions about flood modeling, weight rationales, or spatial decision analysis."
    )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY"))

    SYSTEM_PROMPT = """You are 'GeoAI Assistant', an expert spatial data scientist specializing in flood risk modeling and emergency disaster management.
    You are evaluating a student's flood risk weighting model and evacuation site selection in an interactive challenge.
    
    Explain spatial relationships clearly using hydro-geomorphological principles (e.g., elevation, slope, runoff accumulation, proximity to rivers).
    Respond in a concise, educational, and encouraging tone suitable for university students."""

    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_prompt := st.chat_input(
        "Ask AI (e.g., 'Why did you give flood risk 30%?')"
    ):
        st.session_state.chat_history.append(
            {"role": "user", "content": user_prompt}
        )
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *st.session_state.chat_history,
                    ],
                )
                ai_reply = response.choices[0].message.content
            except Exception as e:
                ai_reply = f"*(AI Mode Simulation - OpenAI Key required for full API integration)*\n\n**GeoAI Explanation:** Flood risk factors like **Elevation** and **Slope** carry heavy weights (25% and 15%) because water naturally flows to lower elevations and flat areas where surface runoff accumulates. **Proximity to River** (20%) directly reflects exposure to riverine flooding during heavy rainstorms."

            st.markdown(ai_reply)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": ai_reply}
            )
            
