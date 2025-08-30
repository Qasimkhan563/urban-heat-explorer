import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import geopandas as gpd
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio
import contextily as ctx
from utils import process_city
import os
import geemap.foliumap as geemap
import folium
from fpdf import FPDF
import matplotlib.pyplot as plt
import numpy as np



def reproject_to_latlon(input_arr, src_transform, src_crs, dst_crs="EPSG:4326"):
    """Reproject raster array to EPSG:4326"""
    height, width = input_arr.shape
    transform, width, height = calculate_default_transform(
        src_crs, dst_crs, width, height, *src_transform.bounds
    )
    dst_arr = np.empty((height, width), dtype=np.float32)

    reproject(
        source=input_arr,
        destination=dst_arr,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
    )
    return dst_arr, transform


def run_step(BASE_DIR):
    st.header("Step 4A: Heatmaps & Metrics")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        In this step you see **heatmaps and key metrics** for your selected city.  

        - 🌡 **Baseline** → current high-heat areas (km²).  
        - 🌳 **Canopy / Trees scenario** → effect of planting more street trees.  
        - 🏢 **Roof scenario** → effect of greening rooftops.  
        - 🏞 **Parks scenario** → effect of creating new pocket parks.  

        These results show how each intervention changes the extent of **urban heat hotspots**.  
        """)

    # Retrieve greening parameters
    canopy_increase = st.session_state["canopy_increase"]
    roof_increase   = st.session_state["roof_increase"]
    park_increase   = st.session_state["park_increase"]

    all_metrics = {}
    st.session_state["heatmap_figs"] = []

    for city in st.session_state["selected_cities"]:
        metrics, heatmaps = process_city(BASE_DIR, city, canopy_increase, roof_increase, park_increase)
        all_metrics[city] = metrics

        if city == "Custom":
            st.info(f"📂 Using **custom uploaded dataset** from: `{st.session_state['custom_city_dir']}`")
        else:
            st.info(f"📂 Using predefined dataset for: **{city}**")

        st.subheader(f"🌡 Interactive Heatmaps – {city}")

        # Always load georeferencing from baseline raster
        baseline_path = os.path.join(BASE_DIR, city, "heat_index.tif")
        with rasterio.open(baseline_path) as src:
            bounds = src.bounds
            crs = src.crs
            transform = src.transform

        # Create interactive map
                # --- Controls for colormap and opacity ---
        cmap = st.selectbox(
            f"🎨 Choose Color Ramp for {city}",
            ["inferno", "viridis", "plasma", "magma", "cividis"],
            index=0, key=f"cmap_{city}"
        )
        opacity = st.slider(
            f"🔎 Raster Opacity for {city}",
            0.1, 1.0, 0.7, step=0.05, key=f"opacity_{city}"
        )

        # Create interactive map
        m = geemap.Map(center=[(bounds.top+bounds.bottom)/2, (bounds.left+bounds.right)/2], zoom=12)

        # Add each scenario with selected colormap + opacity
        for sc, arr in heatmaps.items():
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            with rasterio.open(
                tmpfile.name, "w",
                driver="GTiff",
                height=arr.shape[0],
                width=arr.shape[1],
                count=1,
                dtype="float32",
                crs=crs,
                transform=transform
            ) as dst:
                dst.write(arr.astype("float32"), 1)
        
            # Use rio-tiler instead of localtileserver
            from rio_tiler.io import Reader
        
            with Reader(tmpfile.name) as reader:
                minx, miny, maxx, maxy = reader.bounds
                bounds = [[miny, minx], [maxy, maxx]]
        
            # Add raster to map
            m.add_cog_layer(
                tmpfile.name,
                colormap=cmap,  # keep your selected colormap
                layer_name=f"{city} – {sc}",
                opacity=opacity,
                vmin=0, vmax=1
            )
        
            # Save for PDF later
            st.session_state["heatmap_figs"].append((f"{city} – {sc}", tmpfile.name))


        # Add basemap + layer control
        m.add_basemap("CartoVoyager")
        m.add_child(folium.LayerControl())

        # Show interactive map
        m.to_streamlit(width=800, height=600)

        # --- Legend below map ---
        from branca.colormap import LinearColormap
        import matplotlib.pyplot as plt, numpy as np
        import streamlit.components.v1 as components

        colormap = LinearColormap(
            colors=[plt.get_cmap(cmap)(i) for i in np.linspace(0, 1, 256)],
            vmin=0, vmax=1
        )
        colormap.caption = "Heat Index (0 = cool, 1 = hot)"
        legend_html = colormap._repr_html_()
        components.html(legend_html, height=100)


    # --- Metrics table ---
    df_abs = pd.DataFrame(all_metrics).T.round(2)
    st.subheader("📊 High-Heat Area (km²)")
    st.dataframe(df_abs)
    st.session_state["df_abs"] = df_abs

    # --- Quick summary insight ---
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

    # --- Collect Heatmaps for Export Later ---
        # --- Collect Heatmaps for Export Later ---
    if "heatmap_figs" in st.session_state:
        st.session_state["prepared_heatmaps"] = []  # reset each run

        for title, raster_path in st.session_state["heatmap_figs"]:
            with rasterio.open(raster_path) as src:
                arr = src.read(1)
                plt.figure(figsize=(5,4))
                plt.imshow(arr, cmap="inferno")
                plt.title(title)

                tmp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                plt.savefig(tmp_png.name, dpi=150, bbox_inches="tight")
                plt.close()

                # store for later export
                st.session_state["prepared_heatmaps"].append((title, tmp_png.name))

        st.success("✅ Heatmaps prepared for final export (stored in session).")




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
