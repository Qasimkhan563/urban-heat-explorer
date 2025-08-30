import streamlit as st
import os
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
import numpy as np
from scipy import ndimage
from skimage.transform import resize
import ee
import geemap
import osmnx as ox
import pyproj
from shapely.ops import transform as shp_transform
from shapely.geometry import shape, mapping
import asyncio
import nest_asyncio
from ee_auth import init_ee
init_ee()

# Patch async issues for Streamlit
nest_asyncio.apply()

# ==============================
# Helper: Safe Earth Engine → NumPy
# ==============================
def safe_ee_to_numpy(img, region, scale):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return geemap.ee_to_numpy(img, region=region, scale=scale)

# ==============================
# Step UI
# ==============================
def run_step():
    st.header("Step 3: Cost & Carbon Parameters")
    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        This step adds an **economic and climate perspective** to the scenarios.  

        - 💶 **Cost levels** → Estimate investment needed for each intervention.  
        - 🌱 **Carbon factor** → Approximate CO₂ sequestration by greening (kg per m² per year).  

        Why is this important?  
        - Cities need to balance **budget vs. impact**.  
        - It allows comparison of interventions not just on heat reduction, but also **financial cost** and **carbon benefits**.  
        """)

    # --- Cost presets ---
    cost_levels = {
        "Low – cheap, limited impact": (20, 40),
        "Medium – balanced option": (50, 100),
        "High – costly, stronger impact": (80, 150)
    }
    roof_levels = {
        "Low – minimal coverage": (80, 120),
        "Medium – standard coverage": (100, 180),
        "High – extensive coverage": (150, 220)
    }
    park_levels = {
        "Low – small parks only": (30, 70),
        "Medium – moderate parks": (50, 100),
        "High – large parks": (80, 140)
    }

    cost_canopy = cost_levels[st.selectbox("🌳 Canopy cost", list(cost_levels.keys()), index=1)]
    cost_roofs  = roof_levels[st.selectbox("🏢 Roof cost", list(roof_levels.keys()), index=1)]
    cost_parks  = park_levels[st.selectbox("🏞 Park cost", list(park_levels.keys()), index=1)]
    carbon_factor = st.number_input("🌱 Carbon sequestration (kg CO₂/m²/yr)", 0.1, 5.0, 1.0, step=0.1)

    # --- Buttons ---
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 1
            st.rerun()
    with col2:
        if st.button("Run Analysis 🚀"):
            st.session_state["cost_canopy"] = cost_canopy
            st.session_state["cost_roofs"] = cost_roofs
            st.session_state["cost_parks"] = cost_parks
            st.session_state["carbon_factor"] = carbon_factor

            # --- Branch: uploaded vs auto city ---
            if "custom_aoi" in st.session_state:
                preprocess_custom_data()
            elif "auto_city" in st.session_state:
                preprocess_auto_city(st.session_state["auto_city"])

            st.session_state["step"] = 3.1
            st.rerun()

# ==============================
# Preprocess (Upload path)
# ==============================
def preprocess_custom_data(BASE_DIR=None):
    if BASE_DIR is None:
        BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

    city_name = st.session_state.get("custom_city_name", "Custom_AOI").replace(" ", "_")
    city_dir = os.path.join(BASE_DIR, city_name)
    os.makedirs(city_dir, exist_ok=True)

    gdf_aoi = gpd.read_file(st.session_state["custom_aoi"]).to_crs("EPSG:3857")
    xmin, ymin, xmax, ymax = gdf_aoi.total_bounds
    target_res = 10
    width = int((xmax - xmin) / target_res)
    height = int((ymax - ymin) / target_res)
    transform = from_origin(xmin, ymax, target_res, target_res)

    with rasterio.open(st.session_state["custom_dem"]) as src:
        dem = src.read(1).astype("float32")
        dem_resampled = resize(dem, (height, width), order=1, preserve_range=True, anti_aliasing=False)

    dzdx = ndimage.sobel(dem_resampled, axis=1) / (8.0 * target_res)
    dzdy = ndimage.sobel(dem_resampled, axis=0) / (8.0 * target_res)
    slope = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
    slope_norm = (slope - slope.min()) / (slope.max() - slope.min())

    with rasterio.open(st.session_state["custom_ndvi"]) as src:
        ndvi = src.read(1).astype("float32")
        ndvi_resampled = resize(ndvi, (height, width), order=1, preserve_range=True, anti_aliasing=False)
    ndvi_norm = (ndvi_resampled - ndvi_resampled.min()) / (ndvi_resampled.max() - ndvi_resampled.min())

    gdf_build = gpd.read_file(st.session_state["custom_buildings"]).to_crs("EPSG:3857")
    buildings_raster = rasterize(
        ((geom, 1) for geom in gdf_build.geometry if geom.is_valid),
        out_shape=(height, width), transform=transform, fill=0, dtype="uint8"
    )

    built_norm = buildings_raster.astype(float) / (buildings_raster.max() if buildings_raster.max()>0 else 1)
    heat_index = built_norm - ndvi_norm + slope_norm * 0.2

    profile = {"driver":"GTiff","height":height,"width":width,"count":1,"dtype":"float32","crs":"EPSG:3857","transform":transform}
    for name, arr, dtype in [("ndvi_norm", ndvi_norm, "float32"),
                             ("slope", slope_norm, "float32"),
                             ("buildings", buildings_raster, "uint8"),
                             ("heat_index", heat_index, "float32")]:
        with rasterio.open(os.path.join(city_dir, f"{name}.tif"), "w", **profile) as dst:
            dst.write(arr.astype(dtype), 1)

    st.session_state["custom_city_dir"] = city_dir
    st.session_state["selected_cities"] = [city_name]
    st.success(f"✅ Custom preprocessing complete! Data saved in {city_dir}")

def get_city_aoi(city_query):
    city_gdf = ox.geocode_to_gdf(city_query).to_crs(4326)

    # Make sure we only grab the first geometry
    geom = city_gdf.geometry.iloc[0]

    # Convert to GeoJSON-like dict for EE
    geom_dict = mapping(geom)

    # Now construct AOI for Earth Engine
    aoi = ee.Geometry(geom_dict)

    # For reprojection to meters
    project = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    aoi_m = shp_transform(project, geom)  # ← use the shapely geom, not aoi.getInfo()

    return aoi, aoi_m

# ==============================
# Preprocess (Auto EE+OSM path)
# ==============================
def preprocess_auto_city(city_query, BASE_DIR=None):
    if BASE_DIR is None:
        BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    aoi, aoi_m = get_city_aoi(city_query)
    xmin, ymin, xmax, ymax = aoi_m.bounds
    width, height = int((xmax - xmin) / 10), int((ymax - ymin) / 10)

    # safeguard
    max_dim = 8000
    if width > max_dim or height > max_dim:
        scale_factor = max(width, height) / max_dim
        width = int(width / scale_factor)
        height = int(height / scale_factor)

    transform = from_origin(xmin, ymax, 10, 10)


    # NDVI
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(aoi).filterDate("2023-06-01", "2023-08-31")
          .map(lambda img: img.divide(10000))
          .map(lambda img: img.normalizedDifference(['B8','B4']).rename("NDVI")))
    ndvi = s2.median().clip(aoi).select("NDVI")
    ndvi_array = safe_ee_to_numpy(ndvi, aoi, 10)
    if ndvi_array.ndim == 3:
        ndvi_array = np.nanmean(ndvi_array, axis=-1)
    ndvi_norm = (ndvi_array - np.nanmin(ndvi_array)) / (np.nanmax(ndvi_array) - np.nanmin(ndvi_array))

    # DEM
    dem = ee.ImageCollection("COPERNICUS/DEM/GLO30").mosaic().select("DEM").clip(aoi)
    dem_array  = safe_ee_to_numpy(dem, aoi, 30)
    if dem_array.ndim == 3:
        dem_array = np.nanmean(dem_array, axis=-1)
    dem_resampled = resize(dem_array, ndvi_norm.shape, order=1, preserve_range=True, anti_aliasing=False)

    dzdx = ndimage.sobel(dem_resampled, axis=1) / 80
    dzdy = ndimage.sobel(dem_resampled, axis=0) / 80
    slope = np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))
    slope_norm = (slope - slope.min()) / (slope.max() - slope.min())

    # Buildings
    buildings = ox.features_from_place(city_query, tags={"building": True}).to_crs("EPSG:3857")
    buildings_raster = rasterize(
        ((geom, 1) for geom in buildings.geometry if geom.is_valid),
        out_shape=ndvi_norm.shape, transform=transform, fill=0, dtype="uint8"
    )

    built_norm = buildings_raster.astype(float) / (buildings_raster.max() if buildings_raster.max() > 0 else 1)
    heat_index = built_norm - ndvi_norm + slope_norm * 0.2
    heat_index = (heat_index - heat_index.min()) / (heat_index.max() - heat_index.min())

    # Save inside data/cities/city_name
    city_name = city_query.replace(" ", "_")
    city_dir = os.path.join(BASE_DIR, city_name)
    os.makedirs(city_dir, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "height": ndvi_norm.shape[0],
        "width": ndvi_norm.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:3857",
        "transform": transform,
    }

    for name, arr, dtype in [
        ("ndvi_norm", ndvi_norm, "float32"),
        ("slope", slope_norm, "float32"),
        ("buildings", buildings_raster, "uint8"),
        ("heat_index", heat_index, "float32"),
    ]:
        with rasterio.open(os.path.join(city_dir, f"{name}.tif"), "w", **profile) as dst:
            dst.write(arr.astype(dtype), 1)

    st.session_state["auto_city"] = city_query
    st.session_state["auto_city_dir"] = city_dir
    st.session_state["selected_cities"] = [city_name]

    st.success(f"✅ Auto preprocessing complete for {city_query}. Data saved in {city_dir}")

    # 🔹 Update available_cities.json inside repo
    import json
    cities_file = os.path.join(os.path.dirname(__file__), "..", "available_cities.json")
    if city_name not in st.session_state["available_cities"]:
        st.session_state["available_cities"].append(city_name)
        with open(cities_file, "w") as f:
            json.dump(st.session_state["available_cities"], f)