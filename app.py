
import os, time, uuid, json
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(page_title="GeoAI Site Selection Challenge", page_icon="🌍", layout="wide")

# =========================
# Live classroom backend
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ROOM = st.query_params.get("room", "GEOCITY")
SESSION_ID = st.session_state.setdefault("session_id", str(uuid.uuid4()))

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type":"application/json", "Prefer":"return=representation"}

def sb_get(table, params=""):
    if not (SUPABASE_URL and SUPABASE_KEY): return []
    try:
        r=requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers(), timeout=8)
        r.raise_for_status(); return r.json()
    except Exception:
        return []

def sb_post(table, payload):
    if not (SUPABASE_URL and SUPABASE_KEY): return []
    try:
        r=requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=payload, timeout=8)
        r.raise_for_status(); return r.json()
    except Exception:
        return []

def sb_patch(table, params, payload):
    if not (SUPABASE_URL and SUPABASE_KEY): return []
    try:
        r=requests.patch(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers(), json=payload, timeout=8)
        r.raise_for_status(); return r.json()
    except Exception:
        return []

def live_mode():
    return bool(SUPABASE_URL and SUPABASE_KEY)

# =========================
# User / room registration
# =========================
st.title("🌍 GeoAI Site Selection Challenge")
if "name" not in st.session_state:
    st.session_state.name = ""

if not st.session_state.name:
    st.subheader("Join the classroom")
    name = st.text_input("Your name", placeholder="e.g., Parichat")
    room = st.text_input("Room code", value=ROOM)
    if st.button("🚀 Join", type="primary") and name.strip():
        st.session_state.name=name.strip()
        st.query_params["room"]=room.strip().upper()
        st.rerun()
    st.stop()

ROOM = st.query_params.get("room", ROOM).upper()

# Register / heartbeat
now=int(time.time())
if live_mode():
    existing=sb_get("participants", f"room=eq.{ROOM}&session_id=eq.{SESSION_ID}")
    payload={"room":ROOM,"session_id":SESSION_ID,"name":st.session_state.name,
             "last_seen":now,"mission":int(st.session_state.get("mission",1)),
             "completed_m1":bool(st.session_state.get("completed_m1",False))}
    if existing:
        sb_patch("participants", f"room=eq.{ROOM}&session_id=eq.{SESSION_ID}", payload)
    else:
        sb_post("participants", payload)
    active=sb_get("participants", f"room=eq.{ROOM}&last_seen=gt.{now-15}&select=name,mission,completed_m1")
else:
    active=[]

with st.sidebar:
    st.success(f"👤 {st.session_state.name}")
    st.caption(f"Room: **{ROOM}**")
    if live_mode():
        st.metric("🟢 Students online", len(active))
        names=[x["name"] for x in active]
        st.caption("Online now: " + ", ".join(names[:12]))
    else:
        st.warning("Demo mode: add SUPABASE_URL and SUPABASE_KEY for live classroom mode.")
        st.metric("Students online", 1)

    completed=st.session_state.get("completed_m1",False)
    mission_options=["1 · Flood Factor Challenge"] + (["2 · Evacuation Center Challenge"] if completed else [])
    mission=st.radio("Mission",mission_options)
    st.session_state.mission=1 if mission.startswith("1") else 2
    if not completed:
        st.caption("🔒 Mission 2 unlocks after Mission 1 is completed.")

# =========================
# Real-data loader
# =========================
st.divider()
st.subheader("🗺️ Real-data study area")

with st.expander("Data setup / instructor panel", expanded=False):
    st.markdown("""
**Default study area: Bangkok, Thailand.** The app is designed for real spatial data rather than a synthetic grid.

Upload a real **GeoTIFF DEM** and optionally GeoTIFF rainfall/flood-hazard rasters. Vector layers can be loaded from GeoJSON. 
For a live class, prepare the same files on the instructor machine or host them at stable URLs.

Recommended layers:
- `DEM.tif` — elevation
- `Rainfall.tif` — event rainfall or climatology
- `FloodHazard.tif` — observed/modelled flood hazard (optional)
- `waterways.geojson`
- `roads.geojson`
- `hospitals.geojson`
- `buildings.geojson`

The OSM Overpass API can also be used to fetch Bangkok waterways/roads/hospitals, but public services may rate-limit classroom traffic.
""")
    dem_file=st.file_uploader("Upload real DEM GeoTIFF", type=["tif","tiff"], key="dem")
    rain_file=st.file_uploader("Upload real rainfall GeoTIFF (optional)", type=["tif","tiff"], key="rain")
    flood_file=st.file_uploader("Upload real flood-hazard GeoTIFF (optional)", type=["tif","tiff"], key="flood")
    geo_files=st.file_uploader("Upload real GeoJSON layers", type=["geojson","json"], accept_multiple_files=True, key="geo")

if dem_file is None:
    st.info("For the real-data version, upload the instructor's Bangkok DEM GeoTIFF. The app will not silently fall back to simulated geography.")
    st.stop()

try:
    import rasterio
    from rasterio.transform import rowcol
    import geopandas as gpd
except Exception as e:
    st.error("Install rasterio and geopandas from requirements.txt.")
    st.stop()

def read_raster(uploaded):
    import tempfile
    suffix=".tif"
    tmp=Path(tempfile.gettempdir())/(str(uuid.uuid4())+suffix)
    tmp.write_bytes(uploaded.getvalue())
    src=rasterio.open(tmp)
    arr=src.read(1).astype("float32")
    nodata=src.nodata
    if nodata is not None: arr[arr==nodata]=np.nan
    return src,arr

dem_src, dem = read_raster(dem_file)
rain_src, rain = read_raster(rain_file) if rain_file else (None,None)
flood_src, flood = read_raster(flood_file) if flood_file else (None,None)

# Make a manageable display sample from real DEM.
def sample_raster(arr, src, max_points=8000):
    h,w=arr.shape
    step=max(1,int(np.sqrt(h*w/max_points)))
    rows=np.arange(0,h,step); cols=np.arange(0,w,step)
    rr,cc=np.meshgrid(rows,cols,indexing="ij")
    vals=arr[rr,cc]
    ok=np.isfinite(vals)
    xs,ys=rasterio.transform.xy(src.transform, rr[ok], cc[ok])
    return pd.DataFrame({"lon":xs,"lat":ys,"value":vals[ok]})

dem_df=sample_raster(dem,dem_src)
if dem_df.empty:
    st.error("The DEM has no readable numeric cells."); st.stop()

# Real GeoJSON layers
geo_layers={}
for gf in geo_files or []:
    try:
        gdf=gpd.read_file(gf)
        geo_layers[gf.name]=gdf
    except Exception as e:
        st.warning(f"Could not read {gf.name}: {e}")

layer_name=st.selectbox("Display real-data layer", ["DEM"] + list(geo_layers.keys()))
if layer_name=="DEM":
    fig=px.scatter(dem_df,x="lon",y="lat",color="value",color_continuous_scale="Turbo",
                   title="Real DEM — Bangkok study area")
    fig.update_traces(marker_size=4)
else:
    gdf=geo_layers[layer_name].to_crs(4326)
    fig=px.scatter_geo(gdf, lon=gdf.geometry.centroid.x, lat=gdf.geometry.centroid.y,
                       title=f"Real GeoJSON — {layer_name}")
st.plotly_chart(fig,use_container_width=True)

# =========================
# Mission 1
# =========================
if mission.startswith("1"):
    st.header("🌧 Mission 1 — AI Flood Factor Challenge")
    st.write("Use real spatial layers to decide which factors should receive the greatest weight.")

    available=["Elevation (DEM)"]
    if rain_file: available.append("Rainfall raster")
    if flood_file: available.append("Flood-hazard raster")
    available += list(geo_layers.keys())

    st.write("### 1. Your hypothesis")
    ranking=st.multiselect("Rank the factors you think are most important", available)

    if st.button("🤖 Analyze real-data relationships", type="primary"):
        if flood is not None:
            # Compare raster cells after resampling flood raster to DEM grid.
            from rasterio.warp import reproject, Resampling
            aligned=np.full(dem.shape,np.nan,dtype="float32")
            reproject(flood, aligned, src_transform=flood_src.transform, src_crs=flood_src.crs,
                      dst_transform=dem_src.transform, dst_crs=dem_src.crs, resampling=Resampling.bilinear)
            d=pd.DataFrame({"Elevation":dem.ravel(),"FloodHazard":aligned.ravel()}).dropna()
            corr=abs(d.corr(numeric_only=True)["FloodHazard"].drop("FloodHazard"))
            if len(corr):
                out=corr/corr.sum()
                st.session_state["importance"]=out.sort_values(ascending=False)
        else:
            st.warning("Upload a real FloodHazard.tif to estimate factor importance against observed/modelled flood hazard. The app will not invent a flood target.")
            st.session_state["importance"]=None

    if "importance" in st.session_state and st.session_state["importance"] is not None:
        imp=st.session_state["importance"]
        st.dataframe(pd.DataFrame({"Factor":imp.index,"Absolute correlation share":imp.values})
                     .style.format({"Absolute correlation share":"{:.0%}"}),hide_index=True)
        st.info("This is an exploratory association, not causal proof. For a richer model, add rainfall, distance-to-water, land cover, drainage and other real layers.")
        if ranking:
            user_names=ranking
            st.write("**Your ranking:**", " → ".join(user_names))
        if st.button("✅ Complete Mission 1"):
            st.session_state.completed_m1=True
            if live_mode():
                sb_patch("participants",f"room=eq.{ROOM}&session_id=eq.{SESSION_ID}",
                         {"completed_m1":True,"mission":2,"last_seen":int(time.time())})
            st.success("Mission 1 complete — Mission 2 is now unlocked.")
            st.rerun()

# =========================
# Mission 2
# =========================
else:
    st.header("🚨 Mission 2 — Real-data Evacuation Center Challenge")
    st.write("Select a real candidate location using transparent multi-criteria spatial decision analysis.")

    if not st.session_state.get("completed_m1",False):
        st.error("Mission 2 is locked until Mission 1 is completed.")
        st.stop()

    st.subheader("1. Define priorities")
    st.write("Set the weights for the real-data criteria available in your uploaded layers.")
    criteria=["Flood safety","Elevation","Road accessibility","Population coverage","Hospital accessibility"]
    defaults=[35,20,20,15,10]
    vals=[]
    cols=st.columns(5)
    for c,label,val in zip(cols,criteria,defaults):
        vals.append(c.slider(label,0,100,val,1))
    total=sum(vals)
    weights=np.array(vals)/total if total else np.zeros(5)
    st.caption(f"Normalized weights: {np.round(weights*100).astype(int).tolist()}%")

    st.subheader("2. Candidate generation")
    st.write("The prototype uses the DEM footprint as candidate space. For a full real-world version, upload building/land-parcel polygons and road data.")

    # Candidate cells from DEM, with flood safety based on uploaded flood raster if present.
    cand=dem_df.copy()
    elev_norm=(cand.value-cand.value.min())/(cand.value.max()-cand.value.min()+1e-9)
    cand["elevation_score"]=elev_norm
    if flood is not None:
        from rasterio.warp import reproject, Resampling
        aligned=np.full(dem.shape,np.nan,dtype="float32")
        reproject(flood, aligned, src_transform=flood_src.transform, src_crs=flood_src.crs,
                  dst_transform=dem_src.transform, dst_crs=dem_src.crs, resampling=Resampling.bilinear)
        # map DEM sampled pixels to corresponding flood values
        # approximate using nearest pixel lookup
        rows,cols=rasterio.transform.rowcol(dem_src.transform,cand.lon.values,cand.lat.values)
        rows=np.clip(rows,0,aligned.shape[0]-1); cols=np.clip(cols,0,aligned.shape[1]-1)
        hz=aligned[rows,cols]
        hz=np.nan_to_num(hz,nan=np.nanmedian(hz) if np.isfinite(hz).any() else 0.5)
        hz=(hz-np.nanmin(hz))/(np.nanmax(hz)-np.nanmin(hz)+1e-9)
        cand["flood_safety"]=1-hz
    else:
        cand["flood_safety"]=cand["elevation_score"]
        st.warning("No flood-hazard raster supplied. Flood safety is temporarily represented by elevation only; upload a real hazard raster for the intended exercise.")

    # Real roads/hospitals if uploaded; otherwise these criteria cannot be scored honestly.
    cand["road_score"]=np.nan
    cand["pop_score"]=np.nan
    cand["hospital_score"]=np.nan
    names=" ".join(geo_layers.keys()).lower()
    for name,gdf in geo_layers.items():
        low=name.lower()
        if "road" in low or "street" in low:
            # score by inverse distance to nearest road using centroids (coarse teaching metric)
            pts=gdf.to_crs(dem_src.crs)
            coords=np.array([[p.x,p.y] for p in pts.geometry.centroid])
            # DEM CRS could be geographic; this is only a fallback. Use normalized nearest-neighbour distance.
            if len(coords):
                dx=cand.lon.values[:,None]-coords[:,0]
                dy=cand.lat.values[:,None]-coords[:,1]
                dd=np.sqrt(dx*dx+dy*dy).min(axis=1)
                cand["road_score"]=1-(dd-dd.min())/(dd.max()-dd.min()+1e-9)
        if "hospital" in low:
            pts=gdf.to_crs(dem_src.crs)
            coords=np.array([[p.x,p.y] for p in pts.geometry.centroid])
            if len(coords):
                dx=cand.lon.values[:,None]-coords[:,0]
                dy=cand.lat.values[:,None]-coords[:,1]
                dd=np.sqrt(dx*dx+dy*dy).min(axis=1)
                cand["hospital_score"]=1-(dd-dd.min())/(dd.max()-dd.min()+1e-9)
        if "population" in low or "building" in low or "residential" in low:
            cand["pop_score"]=0.5 # placeholder only if actual population polygons are not supplied

    missing=[]
    if cand["road_score"].isna().all(): missing.append("roads")
    if cand["pop_score"].isna().all(): missing.append("population/buildings")
    if cand["hospital_score"].isna().all(): missing.append("hospitals")
    if missing:
        st.warning("Missing real layers: "+", ".join(missing)+". Their criteria are excluded from the score rather than fabricated.")

    score_parts=[]
    score_parts.append(weights[0]*cand.flood_safety)
    score_parts.append(weights[1]*cand.elevation_score)
    if not cand["road_score"].isna().all(): score_parts.append(weights[2]*cand.road_score.fillna(0))
    if not cand["pop_score"].isna().all(): score_parts.append(weights[3]*cand.pop_score.fillna(0))
    if not cand["hospital_score"].isna().all(): score_parts.append(weights[4]*cand.hospital_score.fillna(0))
    cand["suitability"]=sum(score_parts)

    if st.button("🗺️ Find candidate sites", type="primary"):
        top=cand.sort_values("suitability",ascending=False).head(10)
        st.session_state["top_sites"]=top

    if "top_sites" in st.session_state:
        top=st.session_state["top_sites"]
        fig=px.scatter(top,x="lon",y="lat",size="suitability",color="suitability",
                       color_continuous_scale="Turbo",title="Top real-data candidate locations")
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(top[["lon","lat","suitability","flood_safety","elevation_score"]]
                     .style.format("{:.3f}"),hide_index=True,use_container_width=True)
        st.info("These are candidate locations under your chosen criteria, not a certified emergency-planning recommendation.")

# Auto-refresh for classroom presence
if live_mode():
    time.sleep(0.1)
    st_autorefresh = getattr(st, "autorefresh", None)
    if st_autorefresh:
        st_autorefresh(interval=5000, key="heartbeat")
