import rasterio
import numpy as np
import os
import streamlit as st   # to read session state

pixel_size = 10  # meters

def load_raster(path):
    with rasterio.open(path) as src:
        return src.read(1).astype(float)

def compute_heat_index(ndvi_new, built_raster, slope_norm):
    return built_raster - ndvi_new + slope_norm * 0.2

def high_heat_area(heat, threshold=0.7):
    return np.sum(heat > threshold) * (pixel_size**2) / 1e6  # km²

def process_city(BASE_DIR, city, canopy_increase, roof_increase, park_increase):
    """
    Load preprocessed rasters for a city (uploaded/custom or auto-processed),
    run scenarios, and return metrics + scenario heatmaps.
    """

    # --- Figure out where city data is stored ---
    if "custom_city_dir" in st.session_state and city in st.session_state.get("selected_cities", []):
        city_dir = st.session_state["custom_city_dir"]
    elif "auto_city_dir" in st.session_state and city in st.session_state.get("selected_cities", []):
        city_dir = st.session_state["auto_city_dir"]
    else:
        # fallback to predefined BASE_DIR/city
        city_dir = os.path.join(BASE_DIR, city)

    # --- Load inputs ---
    ndvi_norm     = load_raster(os.path.join(city_dir, "ndvi_norm.tif"))
    slope_norm    = load_raster(os.path.join(city_dir, "slope.tif"))
    built_raster  = load_raster(os.path.join(city_dir, "buildings.tif"))
    heat_baseline = load_raster(os.path.join(city_dir, "heat_index.tif"))

    # --- Scenario A – Canopy in top 20% hotspots ---
    threshold = np.nanpercentile(heat_baseline, 80)
    ndvi_A = ndvi_norm.copy()
    ndvi_A[heat_baseline >= threshold] = np.minimum(1, ndvi_A[heat_baseline >= threshold] + canopy_increase)
    heat_A = compute_heat_index(ndvi_A, built_raster, slope_norm)

    # --- Scenario B – Green Roofs on flat buildings ---
    flat_roofs = (slope_norm < 0.05) & (built_raster == 1)
    ndvi_B = ndvi_norm.copy()
    ndvi_B[flat_roofs] = np.minimum(1, ndvi_B[flat_roofs] + roof_increase)
    heat_B = compute_heat_index(ndvi_B, built_raster, slope_norm)

    # --- Scenario C – Pocket Parks on vacant parcels ---
    vacant = (built_raster == 0) & (ndvi_norm < 0.2)
    ndvi_C = ndvi_norm.copy()
    ndvi_C[vacant] = np.minimum(1, ndvi_C[vacant] + park_increase)
    heat_C = compute_heat_index(ndvi_C, built_raster, slope_norm)

    # --- Collect metrics ---
    metrics = {
        "Baseline": high_heat_area(heat_baseline),
        "Scenario A (Canopy)": high_heat_area(heat_A),
        "Scenario B (Roofs)": high_heat_area(heat_B),
        "Scenario C (Parks)": high_heat_area(heat_C)
    }

    # --- Return both metrics + heatmaps ---
    return metrics, {
        "Baseline": heat_baseline,
        "Scenario A (Canopy)": heat_A,
        "Scenario B (Roofs)": heat_B,
        "Scenario C (Parks)": heat_C
    }
