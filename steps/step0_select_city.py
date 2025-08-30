import streamlit as st
import ee
from steps.step2_costs import preprocess_auto_city
import osmnx as ox
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
from ee_auth import init_ee
init_ee()


def run_step(BASE_DIR, AVAILABLE_CITIES):
    st.header("Step 1: Select a City or Upload Custom Data")

    # --- Short Help (top) ---
    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        In this step, you have **three options** to begin the workflow:

        1. ✅ **Select a Pre-processed City**  
           Choose from built-in datasets ("Lisbon", "Zurich", "Munster", "Podgorica Montenegro", "Tirana", "Karlsruhe", "Copenhagen", "Seville Spain").  

        2. 📂 **Upload Your Own Data**  
           Provide four layers:  
           - Study Area (polygon GeoJSON / GPKG)  
           - DEM (GeoTIFF, 10–90 m)  
           - NDVI (GeoTIFF, Sentinel-2, June–Aug median recommended)  
           - Buildings (GeoJSON / GPKG footprints)  

        3. 🌍 **Enter a City Name** *(experimental)*  
           Type in any city name. The app will try to fetch NDVI (from Sentinel-2 via Earth Engine)  
           and buildings (from OpenStreetMap) automatically.  
           ⚠️ Requires internet & EE/OSM availability.  

        ---
        👉 If you’re new, start with a **pre-processed city**.  
        Advanced users can upload or auto-download their own datasets.
        """)
    # -----------------------------
    # Option 1: Pre-processed Cities
    # -----------------------------
    selected_cities = st.multiselect("Choose one or more pre-processed cities:", AVAILABLE_CITIES)

    # -----------------------------
    # Option 2: Upload Custom Data
    # -----------------------------
    st.markdown("### 📂 Upload Your Own Data")
    use_custom = st.checkbox("Upload custom dataset instead of predefined city")

    if use_custom:
        st.warning("⚠️ You selected to upload your own dataset. Please read the help section carefully.")

        uploaded_aoi = st.file_uploader("Upload Study Area (GeoJSON or GPKG)", type=["geojson", "gpkg"])
        uploaded_dem = st.file_uploader("Upload DEM (GeoTIFF, 90m/30m/10m)", type=["tif", "tiff"])
        uploaded_ndvi = st.file_uploader("Upload NDVI raster (GeoTIFF, 30m/10m)", type=["tif", "tiff"])
        uploaded_buildings = st.file_uploader("Upload Buildings (GeoJSON or GPKG)", type=["geojson", "gpkg"])

        if uploaded_aoi and uploaded_dem and uploaded_ndvi and uploaded_buildings:
            try:
                gdf = gpd.read_file(uploaded_aoi)
                crs_aoi = gdf.crs

                with rasterio.open(uploaded_dem) as src:
                    crs_dem = src.crs
                with rasterio.open(uploaded_ndvi) as src:
                    crs_ndvi = src.crs
                gdf_bld = gpd.read_file(uploaded_buildings)
                crs_buildings = gdf_bld.crs

                crs_list = [crs_aoi, crs_dem, crs_ndvi, crs_buildings]
                if len(set(map(str, crs_list))) > 1:
                    st.error(f"❌ CRS mismatch! Please reproject all files to a common CRS (EPSG:3857 recommended).")
                else:
                    city_name = st.text_input("📝 Enter City/District name for your dataset:", "").strip()
                    if not city_name:
                        st.warning("⚠️ No name entered → using 'Custom_AOI'.")
                        city_name = "Custom_AOI"
                    city_name = city_name.replace(" ", "_")

                    st.session_state["custom_city_name"] = city_name
                    st.session_state["custom_aoi"] = uploaded_aoi
                    st.session_state["custom_dem"] = uploaded_dem
                    st.session_state["custom_ndvi"] = uploaded_ndvi
                    st.session_state["custom_buildings"] = uploaded_buildings
                    st.session_state["custom_crs"] = str(crs_aoi)
                    st.session_state["selected_cities"] = [city_name]

                    st.success(f"✅ CRS check passed! City set as **{city_name}**.")

            except Exception as e:
                st.error(f"⚠️ Error reading files: {e}")

    # -----------------------------
    # Option 3: Auto City (EE + OSM)
    # -----------------------------
    st.markdown("### 🌍 Auto Fetch a City/District")
    use_auto = st.checkbox("Search city/district (auto fetch Earth Engine + OSM)")

    if use_auto:
        city_query = st.text_input("Enter a city/district name (e.g., Podgorica, Montenegro)").strip()
        if st.button("🔎 Auto Process City"):
            if city_query:
                try:
                    from ee_auth import init_ee
                    init_ee()
    
                    city_gdf = ox.geocode_to_gdf(city_query).to_crs(4326)
    
                    if city_gdf.empty:
                        st.error("❌ City not found. Try a different spelling or include country name.")
                    else:
                        geom = city_gdf.geometry.values[0]
                        geom_dict = mapping(geom)
                        aoi = ee.Geometry(geom_dict)
                        project = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
                        aoi_m = shp_transform(project, shape(aoi.getInfo()))
                        area_km2 = aoi_m.area / 1e6
    
                        city_clean = city_query.replace(" ", "_")
                        st.session_state["auto_city"] = city_query
                        st.session_state["selected_cities"] = [city_clean]
    
                        st.success(f"✅ City fetched: **{city_query}** ({area_km2:.1f} km²).")
    
                        centroid = city_gdf.geometry.iloc[0].centroid
                        st.info(f"Map preview skipped. AOI centroid at lat={centroid.y:.4f}, lon={centroid.x:.4f}")
    
                except Exception as e:
                    st.error(f"⚠️ Failed to fetch city: {e}")
            else:
                st.warning("⚠️ Please enter a valid city or district name.")

    # -----------------------------
    # Navigation
    # -----------------------------
    col1, col2 = st.columns([1,1])
    with col1:
        st.write(" ")
    with col2:
        if st.button("Next ➡️"):
            if use_custom:
                if "custom_city_name" in st.session_state:
                    st.session_state["step"] = 1
                    st.rerun()
                else:
                    st.error("❌ Please complete the upload process.")
            elif len(selected_cities) > 0:
                st.session_state["selected_cities"] = selected_cities
                st.session_state["step"] = 1
                st.rerun()
            elif "auto_city" in st.session_state:
                st.session_state["step"] = 1
                st.rerun()
            else:
                st.error("❌ Please select a city, upload a dataset, or auto-fetch one.")

    # --- Detailed Methodology (bottom) ---
    with st.expander("📑 Methodology & Technical Details"):
        st.markdown("""
        ### 🔹 SUMMARY OF THE APPLICATION

        This tool evaluates **urban heat mitigation strategies** across multiple European cities (Lisbon, Zurich, Münster, Athens, Karlsruhe).  
        Users can either:  
        - Select a **pre-processed city** (with existing NDVI, slope, building, and heat index data), or  
        - Upload their **own dataset** (Study Area, DEM, NDVI, and Building footprints).

        ---

        ## 1. Terminologies

        - **Urban Heat Island (UHI):** Local warming effect caused by dense urban structures.  
        - **NDVI (Normalized Difference Vegetation Index):** Derived from Sentinel-2 imagery, range -1 to +1.  
        Formula:  
        $$
        NDVI = \frac{(B8 - B4)}{(B8 + B4)}
        $$

        - **DEM (Digital Elevation Model):** Terrain height raster, used to calculate slope.  
        - **Building footprints:** Vector data of urban structures, rasterized for analysis.  
        - **Baseline Heat Index (HI):** Combines built-up density, vegetation, and slope:  
        \[
        HI = B - NDVI + (S \times 0.2)
        \]  

        ---

        ## 2. Dataset Options

        ### A. Pre-defined city datasets
        Provided internally for Lisbon, Zurich, Münster, Athens, Karlsruhe:  
        - `ndvi_norm.tif` → Sentinel-2 NDVI (10 m).  
        - `slope.tif` → DEM-derived slope (10 m).  
        - `buildings.tif` → rasterized building footprints (10 m).  
        - `heat_index.tif` → precomputed baseline heat.  

        ### B. Custom uploads
        If you upload your own datasets, ensure:  

        - **Study Area (AOI):** GeoJSON or GPKG polygon of your study boundary.  
        - **DEM:** GeoTIFF, resolution 90 m (SRTM), 30 m (Copernicus GLO-30), or 10 m (LiDAR).  
        - **NDVI:** GeoTIFF, resolution 10/30 m.  
            - Should represent **summer median NDVI** (June–Aug) or **annual median** from Sentinel-2 SR.  
            - Value range: [-1, +1].  
        - **Buildings:** GeoJSON or GPKG footprint polygons, will be rasterized to 10 m.  

        ⚠️ All rasters will be reprojected/resampled to 10 m and must be in the same CRS.

        ---

        ## 3. Data Sources & Example Downloads

        - 🌱 **NDVI (Sentinel-2 Surface Reflectance)**  
        Google Earth Engine Collection: [COPERNICUS/S2_SR_HARMONIZED](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)  
        Example GEE Code (Summer NDVI 2023):  
        ```javascript
        var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate("2023-06-01", "2023-08-31")
            .map(function(img){return img.divide(10000)})
            .map(function(img){return img.normalizedDifference(['B8','B4']).rename("NDVI")});
        var ndvi = s2.median().clip(aoi);
        Export.image.toDrive({image: ndvi, scale: 10, region: aoi, fileFormat: "GeoTIFF"});
        ```

        - 🏔 **DEM (Copernicus GLO-30 DEM)**  
        Free global DEM at 30 m resolution. Download from:  
        [Copernicus DEM Portal](https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model)  

        - 🏢 **Buildings (OpenStreetMap)**  
        - [GeoFabrik extracts](https://download.geofabrik.de/) (by country/region).  
        - Or use Overpass API:  
            ```
            [out:json];(way["building"](AREA););out body;>;out skel qt;
            ```

        ---

        ## 4. Data Preparation Workflow

        1. **NDVI Normalization**  
        - Scale raw NDVI values to [0,1].  
        - Apply vegetation thresholds (NDVI < 0.2 = low vegetation).  
        2. **Slope Calculation**  
        - DEM → slope (degrees) → normalized [0,1].  
        3. **Building Rasterization**  
        - Footprints → raster (10 m).  
        - 1 = building, 0 = non-building.  
        4. **Baseline Heat Index**  
        - Compute HI = B - NDVI + (S × 0.2).  
        5. **High-Heat Area**  
        - Compute % of pixels above threshold (0.7).  

        ---

        ## 5. Flow of the Application

        1. Select city OR upload dataset.  
        2. Compute baseline heat index.  
        3. Run greening scenarios (trees, roofs, parks).  
        4. Visualize results, SDG alignment, costs, carbon.  
        5. Collect stakeholder feedback & priorities.  

        ---

        ## 6. Limitations

        - Accuracy depends on NDVI quality & cloud masking.  
        - OSM completeness varies by region.  
        - Heat Index is relative, not absolute temperature.  
        - Custom datasets must be aligned to avoid distortions.  

        ---

        ✅ **Why It Matters:**  
        This step ensures transparency and reproducibility.  
        It also allows the tool to be applied anywhere in the world, not just in predefined cities.
        """)
