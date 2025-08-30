import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import rasterio
import numpy as np
import pydeck as pdk
import pyproj
from shapely.geometry import box
from shapely.ops import transform as shp_transform
from utils import process_city


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
    st.header("Step 4A: Heatmaps & Metrics")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        In this step you see **heatmaps and key metrics** for your selected city.  

        - 🌡 **Baseline** → current high-heat areas (km²).  
        - 🌳 **Canopy / Trees scenario** → effect of planting more street trees.  
        - 🏢 **Roof scenario** → effect of greening rooftops.  
        - 🏞 **Parks scenario** → effect of creating new pocket parks.  
        """)

    canopy_increase = st.session_state["canopy_increase"]
    roof_increase   = st.session_state["roof_increase"]
    park_increase   = st.session_state["park_increase"]

    all_metrics = {}
    st.session_state["heatmap_figs"] = []

    for city in st.session_state["selected_cities"]:
        metrics, heatmaps = process_city(
            BASE_DIR, city,
            canopy_increase, roof_increase, park_increase
        )
        all_metrics[city] = metrics

        st.subheader(f"🌡 Interactive Heatmaps – {city}")

        # Load baseline raster to get bounds in lat/lon
        baseline_path = os.path.join(BASE_DIR, city, "heat_index.tif")
        with rasterio.open(baseline_path) as src:
            bounds_latlon = get_latlon_bounds(src)

        # Map center
        center_lat = (bounds_latlon[0][0] + bounds_latlon[1][0]) / 2
        center_lon = (bounds_latlon[0][1] + bounds_latlon[1][1]) / 2

        # Save centroid for reuse in later steps
        if "city_centroids" not in st.session_state:
            st.session_state["city_centroids"] = {}
        st.session_state["city_centroids"][city] = (center_lat, center_lon)

        # User controls
        cmap = st.selectbox(
            f"🎨 Choose Color Ramp for {city}",
            ["inferno", "viridis", "plasma", "magma", "cividis"],
            index=0, key=f"cmap_{city}"
        )
        opacity = st.slider(
            f"🔎 Raster Opacity for {city}",
            0.1, 1.0, 0.7, step=0.05, key=f"opacity_{city}"
        )

        # --- Toggleable layers ---
        selected_layers = st.multiselect(
            f"👀 Toggle layers for {city}",
            options=list(heatmaps.keys()),
            default=list(heatmaps.keys())
        )

        # Prepare pydeck layers
        layers = []
        for sc, arr in heatmaps.items():
            if sc not in selected_layers:
                continue

            # Normalize
            if np.nanmax(arr) > np.nanmin(arr):
                normed = (arr - np.nanmin(arr)) / (np.nanmax(arr) - np.nanmin(arr))
            else:
                normed = np.zeros_like(arr)

            # Save PNG for layer
            tmp_png = os.path.join(tempfile.gettempdir(), f"{city}_{sc}.png")
            plt.imsave(tmp_png, normed, cmap=cmap)

            # Bounds [west, south, east, north]
            image_bounds = [
                bounds_latlon[0][1],
                bounds_latlon[0][0],
                bounds_latlon[1][1],
                bounds_latlon[1][0],
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

            st.session_state["heatmap_figs"].append((f"{city} – {sc}", tmp_png))

        # Show deck map
        view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=12)
        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            map_style=None,  # OSM background (no Mapbox token needed)
        )
        st.pydeck_chart(deck)

    # --- Metrics table ---
    df_abs = pd.DataFrame(all_metrics).T.round(2)
    st.subheader("📊 High-Heat Area (km²)")
    st.dataframe(df_abs)
    st.session_state["df_abs"] = df_abs

    # --- Quick Insights ---
    st.subheader("📌 Quick Insights")
    for city in df_abs.index:
        baseline = df_abs.loc[city, "Baseline"]
        best_scenario = df_abs.loc[city].drop("Baseline").idxmin()
        best_value = df_abs.loc[city, best_scenario]
        best_reduction = (baseline - best_value) / baseline * 100 if baseline > 0 else 0

        st.markdown(f"**{city}**")
        st.write(
            f"➡️ Best: **{best_scenario}** reduces from {baseline:.2f} → {best_value:.2f} km² "
            f"(**{best_reduction:.1f}% reduction**)"
        )
        for scenario in df_abs.columns.drop(["Baseline", best_scenario]):
            value = df_abs.loc[city, scenario]
            reduction = (baseline - value) / baseline * 100 if baseline > 0 else 0
            st.write(f"- {scenario}: {value:.2f} km² ({reduction:.1f}% reduction)")

    # Navigation
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 2
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["step"] = 3.2
            st.rerun()
