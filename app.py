
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="GeoAI Site Selection Challenge", page_icon="🌍", layout="wide")

# ---------- Simulated GeoCity ----------
@st.cache_data
def make_data(n=20, seed=7):
    rng = np.random.default_rng(seed)
    x, y = np.meshgrid(np.arange(n), np.arange(n))
    x = x.ravel(); y = y.ravel()

    # Synthetic geography: river diagonally through the city
    river_line = 0.65*x + 3
    river_dist = np.abs(y-river_line) + 0.8
    river_dist = river_dist / river_dist.max()

    # Elevation: generally higher in NE, lower near river
    elev = 20 + 0.9*x + 0.7*y - 10*np.exp(-((y-(0.65*x+3))**2)/12)
    elev += rng.normal(0, 1.5, len(x))
    elev = (elev-elev.min())/(elev.max()-elev.min())

    slope = np.sqrt((np.gradient(elev.reshape(n,n), axis=0))**2 +
                    (np.gradient(elev.reshape(n,n), axis=1))**2).ravel()
    slope = (slope-slope.min())/(slope.max()-slope.min()+1e-9)

    rainfall = 0.45 + 0.35*np.exp(-((x-8)**2+(y-13)**2)/70) + rng.normal(0,0.05,len(x))
    rainfall = np.clip(rainfall,0,1)

    # Drainage: weaker in low areas / dense urban areas
    drainage = np.clip(0.25 + 0.7*elev - 0.25*rng.random(len(x)),0,1)

    pop = 0.15 + 0.8*np.exp(-((x-13)**2+(y-8)**2)/45) + 0.25*np.exp(-((x-5)**2+(y-15)**2)/30)
    pop += rng.normal(0,0.04,len(x)); pop=np.clip(pop,0,1)

    roads = np.minimum(np.abs(y-5), np.abs(x-10))
    road_access = 1/(1+roads)
    road_access=(road_access-road_access.min())/(road_access.max()-road_access.min())

    hospital_dist = np.sqrt((x-15)**2+(y-4)**2)
    hospital_access = 1-(hospital_dist/hospital_dist.max())

    land = rng.random(len(x))
    land = np.clip(0.4+0.4*elev+0.2*land,0,1)

    # Flood risk: higher = more risk
    flood = (0.30*(1-elev)+0.24*(1-river_dist)+0.20*rainfall+
             0.16*(1-drainage)+0.10*(1-slope))
    flood += rng.normal(0,0.025,len(x))
    flood=np.clip(flood,0,1)

    df=pd.DataFrame({
        "x":x,"y":y,"elevation":elev,"slope":slope,"river_distance":river_dist,
        "rainfall":rainfall,"drainage":drainage,"population":pop,
        "road_access":road_access,"hospital_access":hospital_access,
        "land_availability":land,"flood_risk":flood
    })
    return df

df = make_data()

FACTOR_LABELS = {
    "elevation":"Elevation",
    "river_distance":"Distance to river",
    "rainfall":"Rainfall",
    "slope":"Slope",
    "drainage":"Drainage capacity"
}

st.title("🌍 GeoAI Site Selection Challenge")
st.caption("A simulated classroom lab: use AI-style analysis + spatial decision making to choose an evacuation-center site.")

with st.sidebar:
    st.header("Mission control")
    mission = st.radio("Choose mission", ["1 · Flood Factor Challenge", "2 · Evacuation Center Challenge"])
    st.divider()
    st.write("**GeoCity** is simulated. Scores demonstrate the method; they are not real-world emergency guidance.")

# ---------- Map helper ----------
def map_scatter(d, color, title, hover_cols=None):
    fig=px.scatter(d, x="x", y="y", color=color, hover_data=hover_cols,
                   color_continuous_scale="Turbo", title=title,
                   labels={"x":"East-West grid","y":"North-South grid"})
    fig.update_traces(marker_size=11)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig

if mission.startswith("1"):
    st.header("🌧 Mission 1 — What makes an area flood-prone?")
    st.write("Rank the factors first. Then ask the AI-style model to reveal the data-generating weights.")

    left,right=st.columns([1,1])
    with left:
        st.subheader("A. Explore the spatial data")
        layer=st.selectbox("Map layer", ["flood_risk","elevation","river_distance","rainfall","slope","drainage"])
        st.plotly_chart(map_scatter(df, layer, layer.replace("_"," ").title()),
                        use_container_width=True)
    with right:
        st.subheader("B. Your hypothesis")
        rank_order=st.multiselect("Rank factors from most to least important (choose all, in order)",
                                  list(FACTOR_LABELS.keys()))
        st.info("Tip: think geographically. Low elevation and proximity to rivers may matter, but do not assume the answer.")

        if st.button("🤖 Ask AI to analyze", type="primary"):
            # Transparent synthetic "AI-style" feature-importance result.
            X=df[list(FACTOR_LABELS.keys())].copy()
            y=df["flood_risk"]
            corr=X.corrwith(y).abs()
            corr=corr/corr.sum()
            out=pd.DataFrame({"Factor":[FACTOR_LABELS[k] for k in corr.index],
                              "Estimated importance":corr.values})
            out=out.sort_values("Estimated importance",ascending=False)
            st.session_state["factor_result"]=out

        if "factor_result" in st.session_state:
            out=st.session_state["factor_result"]
            st.dataframe(out.style.format({"Estimated importance":"{:.0%}"}), hide_index=True, use_container_width=True)
            fig=px.bar(out, x="Estimated importance", y="Factor", orientation="h",
                       title="AI-style feature importance")
            st.plotly_chart(fig,use_container_width=True)
            st.success("Interpretation: importance is estimated from the simulated dataset. It is evidence for discussion, not a universal causal law.")

            if rank_order:
                ai_order=out["Factor"].tolist()
                user_names=[FACTOR_LABELS[k] for k in rank_order]
                overlap=len(set(user_names[:3]) & set(ai_order[:3]))
                st.metric("Top-3 ranking overlap", f"{overlap}/3")
                st.write("**Discuss:** Why did your intuition agree or disagree with the data?")

else:
    st.header("🚨 Mission 2 — Choose an evacuation-center site")
    st.write("Build a transparent multi-criteria decision model. You control the final weights; the AI-style assistant only proposes a starting point.")

    st.subheader("1. Tell the AI what matters")
    prompt=st.text_area("Example requirement",
        "Choose a site that is safe from flooding, accessible by road, close to population, elevated, and reasonably close to a hospital.",
        height=90)

    if st.button("🤖 Generate suggested weights", type="primary"):
        # Rule-based classroom assistant: deterministic and inspectable.
        st.session_state["suggested"]={
            "flood_risk":0.30, "population":0.25, "road_access":0.20,
            "elevation":0.15, "hospital_access":0.10
        }

    if "suggested" not in st.session_state:
        st.session_state["suggested"]={"flood_risk":0.30,"population":0.25,"road_access":0.20,"elevation":0.15,"hospital_access":0.10}

    s=st.session_state["suggested"]
    st.write("**AI-style starting point**")
    cols=st.columns(5)
    for c,(k,v) in zip(cols,s.items()):
        c.metric(k.replace("_"," ").title(), f"{v:.0%}")

    st.subheader("2. Human override — set your own weights")
    w={}
    cols=st.columns(5)
    for c,k in zip(cols,s):
        w[k]=c.slider(k.replace("_"," ").title(),0,100,int(s[k]*100),1)
    total=sum(w.values())
    if total==0:
        st.error("Give at least one criterion a non-zero weight.")
        st.stop()
    wn={k:v/total for k,v in w.items()}
    st.caption(f"Weights are automatically normalized to 100%. Current total: {total}%")

    # suitability: high is good
    suitability=(wn["flood_risk"]*(1-df.flood_risk)+
                  wn["population"]*df.population+
                  wn["road_access"]*df.road_access+
                  wn["elevation"]*df.elevation+
                  wn["hospital_access"]*df.hospital_access)
    result=df.copy()
    result["suitability"]=suitability

    st.subheader("3. Run site selection")
    if st.button("🗺️ Calculate candidate sites", type="primary"):
        st.session_state["site_result"]=result

    if "site_result" in st.session_state:
        r=st.session_state["site_result"]
        st.plotly_chart(map_scatter(r,"suitability","Evacuation-center suitability",
                                     ["flood_risk","population","road_access","elevation"]),
                        use_container_width=True)

        top=r.sort_values("suitability",ascending=False).head(5).copy()
        top["rank"]=range(1,6)
        top=top[["rank","x","y","suitability","flood_risk","population","road_access","elevation"]]
        st.subheader("Top candidate sites")
        st.dataframe(top.style.format({
            "suitability":"{:.3f}","flood_risk":"{:.3f}","population":"{:.3f}",
            "road_access":"{:.3f}","elevation":"{:.3f}"
        }),hide_index=True,use_container_width=True)

        st.subheader("4. Scenario challenge")
        scenario=st.selectbox("Change the scenario",[
            "Normal conditions","Extreme rainfall","Road closure","Population surge"])
        rr=r.copy()
        if scenario=="Extreme rainfall":
            rr["flood_risk"]=np.clip(rr.flood_risk+0.18*(1-rr.elevation),0,1)
        elif scenario=="Road closure":
            rr["road_access"]=np.clip(rr.road_access-0.30,0,1)
        elif scenario=="Population surge":
            rr["population"]=np.clip(rr.population*1.25,0,1)
        rr["suitability"]=(wn["flood_risk"]*(1-rr.flood_risk)+
                           wn["population"]*rr.population+
                           wn["road_access"]*rr.road_access+
                           wn["elevation"]*rr.elevation+
                           wn["hospital_access"]*rr.hospital_access)
        top2=rr.sort_values("suitability",ascending=False).head(5)
        st.plotly_chart(map_scatter(rr,"suitability",f"Suitability — {scenario}"),
                        use_container_width=True)
        st.write("**Compare the top candidates before and after the scenario. Why did the ranking change?**")

st.divider()
st.markdown("### 🎓 Learning takeaway")
st.markdown("**ASK → DATA → AI → MAP → EXPLAIN → DECIDE**  \nAI provides evidence and alternatives; humans define objectives, constraints, assumptions, and the final decision.")
