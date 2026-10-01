import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="AI Site Selection",
    page_icon="🌍",
    layout="wide"
)

st.title("AI in Geography: Site Selection Challenge")
st.write(
    "Choose the best location for a new public facility "
    "using geographic data."
)

# Sample geographic data
data = pd.DataFrame({
    "Site": ["A", "B", "C", "D", "E", "F"],
    "Latitude": [13.756, 13.742, 13.765, 13.731, 13.778, 13.750],
    "Longitude": [100.501, 100.530, 100.490, 100.515, 100.520, 100.475],
    "Population": [8000, 15000, 22000, 11000, 18000, 9000],
    "Road_Access": [9, 7, 5, 8, 6, 9],
    "Flood_Safety": [9, 6, 3, 8, 7, 8],
    "Nearby_Facilities": [5, 3, 2, 7, 4, 6]
})

st.sidebar.header("Set your priorities")

population_weight = st.sidebar.slider(
    "Population importance", 0, 100, 30
)

road_weight = st.sidebar.slider(
    "Road accessibility importance", 0, 100, 25
)

flood_weight = st.sidebar.slider(
    "Flood safety importance", 0, 100, 30
)

facility_weight = st.sidebar.slider(
    "Nearby facilities importance", 0, 100, 15
)

total_weight = (
    population_weight
    + road_weight
    + flood_weight
    + facility_weight
)

if total_weight == 0:
    st.warning("Please assign at least one weight.")
else:
    # Normalize population to a 0-10 scale
    data["Population_Score"] = (
        data["Population"] / data["Population"].max() * 10
    )

    data["Score"] = (
        data["Population_Score"] * population_weight
        + data["Road_Access"] * road_weight
        + data["Flood_Safety"] * flood_weight
        + data["Nearby_Facilities"] * facility_weight
    ) / total_weight

    data = data.sort_values("Score", ascending=False)

    best_site = data.iloc[0]

    st.subheader(f"Recommended site: {best_site['Site']}")
    st.success(
        f"Site {best_site['Site']} has the highest score: "
        f"{best_site['Score']:.2f} / 10"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Site ranking")
        st.dataframe(
            data[
                [
                    "Site",
                    "Population",
                    "Road_Access",
                    "Flood_Safety",
                    "Nearby_Facilities",
                    "Score"
                ]
            ].round(2),
            use_container_width=True
        )

    with col2:
        st.subheader("Map view")
        map_data = data.rename(
            columns={
                "Latitude": "lat",
                "Longitude": "lon"
            }
        )

        st.map(map_data[["lat", "lon"]])

    st.info(
        "Discussion question: Would you choose the recommended site? "
        "Why or why not?"
    )
