# Recommended real-data package for Bangkok

## Minimum for Mission 1
1. DEM GeoTIFF — real elevation.
2. FloodHazard GeoTIFF — observed/modelled flood hazard or flood extent converted to a raster target.

## Stronger Mission 1
Add:
- Rainfall GeoTIFF
- distance-to-waterways GeoJSON
- land-cover GeoTIFF
- drainage capacity layer

## Minimum for Mission 2
- DEM
- flood hazard
- roads
- hospitals

## Stronger Mission 2
Add:
- population raster / census polygons
- building footprints
- schools / public facilities
- land parcels
- road travel-time surface

## Data sources
- SRTM: NASA / OpenTopography. OpenTopography documents SRTM GL1 30 m and GeoTIFF output.
- OpenStreetMap: roads, waterways, hospitals, buildings.
- Thailand/Bangkok government open-data portals: administrative boundaries, flood records, rainfall and population where available.

The app intentionally uses uploaded real layers rather than silently substituting synthetic values.
