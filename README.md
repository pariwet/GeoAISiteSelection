# GeoAI Site Selection Challenge

A classroom-ready Streamlit prototype for first-year international engineering students.

## Missions
1. Flood Factor Challenge: students inspect simulated spatial layers, rank flood factors, then compare their intuition with an AI-style feature-importance analysis.
2. Evacuation Center Challenge: students describe planning goals, receive a transparent starting weight set, override the weights, calculate a suitability map, and test scenarios.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Teaching note
The dataset and "AI" analysis are deliberately simulated and transparent. This is a teaching model, not a real emergency-planning system. For a more advanced version, replace the rule-based assistant with a real LLM and replace the synthetic grid with GeoJSON/raster layers from a real study area.
