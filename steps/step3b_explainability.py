import streamlit as st
import numpy as np
import os
import plotly.graph_objects as go
from utils import process_city, load_raster, compute_heat_index, high_heat_area
import rasterio
import tempfile
import matplotlib.pyplot as plt
import pydeck as pdk
import pyproj
from shapely.geometry import box
from shapely.ops import transform as shp_transform


def get_latlon_bounds(src):
    """Convert raster bounds to EPSG:4326 (lat/lon)."""
    proj_src = pyproj.CRS(src.crs)
    proj_dst = pyproj.CRS("EPSG:4326")
    project = pyproj.Transformer.from_crs(proj_src, proj_dst, always_xy=True).transform
    bbox = box(src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
    bbox_latlon = shp_transform(project, bbox)
    minx, miny, maxx, maxy = bbox_latlon.bounds
    return [[miny, minx], [maxy, maxx]]  # [[south, west], [north, east]]


def run_step(BASE_DIR):
    st.header("Step 4B: Explainability & Digital Twin Simulation")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        Here the app explains **why certain hotspots occur** and simulates how they evolve over time.  

        - 🏙 **Explainability (XAI)** → shows why hotspots exist (dense buildings, low greenery, or slope effects).  
        - ⏳ **Digital Twin Simulation** → projects changes in heat area over 20 years under greening interventions.  
        - 🗺 **Interactive map comparison** → baseline, 5, 10, 15, 20 years + difference map.  
        """)

    canopy_increase = st.session_state["canopy_increase"]
    roof_increase   = st.session_state["roof_increase"]
    park_increase   = st.session_state["park_increase"]

    temporal_results = {}
    top_n = 3

    # --- Loop over cities ---
    for city in st.session_state["selected_cities"]:
        _, heatmaps = process_city(BASE_DIR, city, canopy_increase, roof_increase, park_increase)
        heat_baseline = heatmaps["Baseline"]

        # --- Explainability: top hotspots ---
        flat_idx = np.dstack(np.unravel_index(np.argsort(heat_baseline.ravel())[::-1], heat_baseline.shape))[0]
        top_pixels = flat_idx[:top_n]

        city_dir = os.path.join(BASE_DIR, city)
        ndvi_norm = load_raster(os.path.join(city_dir, "ndvi_norm.tif"))
        slope_norm = load_raster(os.path.join(city_dir, "slope.tif"))
        built_raster = load_raster(os.path.join(city_dir, "buildings.tif"))

        st.markdown(f"### 🔍 City: {city} – Top {top_n} Hotspots")
        for i, (r, c) in enumerate(top_pixels, start=1):
            msg = (
                f"- Hotspot {i}: Built={built_raster[r,c]:.2f}, NDVI={ndvi_norm[r,c]:.2f}, "
                f"Slope={slope_norm[r,c]:.2f}. Reason → "
                f"{'Dense urban' if built_raster[r,c]>0.7 else 'Mixed'} with "
                f"{'low vegetation' if ndvi_norm[r,c]<0.3 else 'moderate greenery'}."
            )
            st.write(msg)

        # --- Digital Twin Simulation ---
        st.subheader(f"⏳ Digital Twin – {city}")
        years = list(range(0, 21))
        temporal_results[city] = {"years": years, "heat_area": []}

        heat_baseline = load_raster(os.path.join(city_dir, "heat_index.tif"))

        for year in years:
            tree_factor, roof_factor, park_factor = min(1.0, year/15), min(1.0, year/5), min(1.0, year/10)
            ndvi_sim = ndvi_norm.copy()

            threshold = np.nanpercentile(heat_baseline, 80)
            ndvi_sim[heat_baseline >= threshold] = np.minimum(1, ndvi_sim[heat_baseline >= threshold] + canopy_increase * tree_factor)
            ndvi_sim[(slope_norm < 0.05) & (built_raster==1)] = np.minimum(1, ndvi_sim[(slope_norm < 0.05) & (built_raster==1)] + roof_increase * roof_factor)
            ndvi_sim[(built_raster==0) & (ndvi_norm<0.2)] = np.minimum(1, ndvi_sim[(built_raster==0) & (ndvi_norm<0.2)] + park_increase * park_factor)

            heat_sim = compute_heat_index(ndvi_sim, built_raster, slope_norm)
            temporal_results[city]["heat_area"].append(high_heat_area(heat_sim))

            # Save snapshots
            if year in [5, 10, 15, 20]:
                temporal_results[city][f"heatmap_year{year}"] = heat_sim
        temporal_results[city]["heatmap_baseline"] = heat_baseline

        # --- Interactive map with pydeck ---
        if st.checkbox(f"🌍 Show Interactive Baseline + Future Snapshots – {city}"):
            baseline_path = os.path.join(city_dir, "heat_index.tif")
            with rasterio.open(baseline_path) as src:
                bounds_latlon = get_latlon_bounds(src)

            center_lat = (bounds_latlon[0][0] + bounds_latlon[1][0]) / 2
            center_lon = (bounds_latlon[0][1] + bounds_latlon[1][1]) / 2

            cmap = st.selectbox(
                f"🎨 Choose Color Ramp for {city}",
                ["inferno", "viridis", "plasma", "magma", "cividis"],
                index=0, key=f"cmap_{city}"
            )
            opacity = st.slider(f"🔎 Raster Opacity for {city}", 0.1, 1.0, 0.7, step=0.05, key=f"opacity_{city}")

            # Snapshots to display
            scenario_maps = {
                "Baseline": temporal_results[city]["heatmap_baseline"],
                "Year 5": temporal_results[city]["heatmap_year5"],
                "Year 10": temporal_results[city]["heatmap_year10"],
                "Year 15": temporal_results[city]["heatmap_year15"],
                "Year 20": temporal_results[city]["heatmap_year20"],
                "Cooling Effect (20y - Baseline)": temporal_results[city]["heatmap_year20"] - temporal_results[city]["heatmap_baseline"],
            }

            selected_layers = st.multiselect(
                f"👀 Toggle layers for {city}",
                options=list(scenario_maps.keys()),
                default=list(scenario_maps.keys())
            )

            layers = []
            for sc, arr in scenario_maps.items():
                if sc not in selected_layers:
                    continue

                if np.nanmax(arr) > np.nanmin(arr):
                    normed = (arr - np.nanmin(arr)) / (np.nanmax(arr) - np.nanmin(arr))
                else:
                    normed = np.zeros_like(arr)

                tmp_png = os.path.join(tempfile.gettempdir(), f"{city}_{sc}.png")
                plt.imsave(tmp_png, normed, cmap=cmap)

                image_bounds = [
                    bounds_latlon[0][1],  # west
                    bounds_latlon[0][0],  # south
                    bounds_latlon[1][1],  # east
                    bounds_latlon[1][0],  # north
                ]

                layer = pdk.Layer(
                    "BitmapLayer",
                    data=None,
                    image=tmp_png,
                    bounds=image_bounds,
                    opacity=opacity,
                    pickable=False,
                    id=f"{city}_{sc}",
                )
                layers.append(layer)

            view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=12)
            deck = pdk.Deck(
                layers=layers,
                initial_view_state=view_state,
                map_style=None,  # OSM background
            )
            st.pydeck_chart(deck)

        # --- Time series chart ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=years, y=temporal_results[city]["heat_area"],
                                 mode="lines+markers", name=city, line=dict(color="blue")))
        fig.update_layout(title="High-Heat Area Evolution under Greening Interventions",
                          xaxis_title="Years", yaxis_title="High-Heat Area (km²)",
                          template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

        st.info("💡 Insight: Trees take longest to mature, but provide the most durable cooling effect. "
                "Roofs act fast, parks balance both speed and area impact.")

    # --- Navigation ---
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 3.1
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["step"] = 3.3
            st.rerun()
