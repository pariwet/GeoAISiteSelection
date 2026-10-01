# GeoAI Site Selection Challenge v2

## What changed

### 1. Live classroom / Kahoot-style presence
Students enter a name and room code. With Supabase configured, the app:
- shows the student's name;
- counts students active in the same room;
- shows names currently online;
- stores Mission 1 completion so Mission 2 is locked until completion.

Presence is based on a heartbeat (`last_seen`) and a 15-second activity window.

### 2. Mission lock
Mission 2 is not displayed in the navigation until Mission 1 is completed. The server-side participant record also stores `completed_m1`.

### 3. Real spatial data
The synthetic grid has been removed. The app requires a real GeoTIFF DEM and accepts real GeoJSON / GeoTIFF layers.
Recommended Bangkok layers:
- DEM.tif
- Rainfall.tif
- FloodHazard.tif
- roads.geojson
- waterways.geojson
- hospitals.geojson
- buildings.geojson or population.geojson

The app deliberately refuses to invent a flood target when no real flood-hazard raster is supplied.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Live mode

Create a Supabase project, run `supabase_schema.sql` in the SQL editor, then set:

```bash
export SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
export SUPABASE_KEY="YOUR_ANON_KEY"
streamlit run app.py
```

For Streamlit Cloud, put these values in Secrets instead of source code.

## Data

The recommended study area is Bangkok. NASA SRTM is a suitable DEM source; OpenTopography documents SRTM GL1 at 30 m and WGS84 coordinates. See the source links supplied with the course materials.

For vector data, OpenStreetMap/Overpass can supply roads, waterways, hospitals and other features. Respect the service's usage policy and avoid sending hundreds of simultaneous requests; download and host a classroom copy when possible.

## Important teaching limitation

This is a teaching prototype. A suitability score is not a real emergency-planning recommendation. Students should learn that:
AI/model output depends on data quality, criteria, weights, scale, normalization and assumptions.
