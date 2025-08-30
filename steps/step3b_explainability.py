import streamlit as st
import numpy as np
import os
import plotly.graph_objects as go
from utils import process_city, load_raster, compute_heat_index, high_heat_area
import rasterio
import tempfile
import geemap.foliumap as geemap
import folium
import branca.colormap as cm
import matplotlib.pyplot as plt
import streamlit.components.v1 as components


def run_step(BASE_DIR):
    st.header("Step 4B: Explainability & Digital Twin Simulation")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        Here the app explains **why certain hotspots occur** and simulates how they evolve over time.  

        - 🏙 **Explainability (XAI)** → shows why hotspots exist (dense buildings, low greenery, or slope effects).  
        - ⏳ **Digital Twin Simulation** → projects changes in heat area over 20 years under greening interventions.  
        - 🗺 **Interactive map comparison** → baseline, 5, 10, 15, 20 years + difference map.  

        🔑 This step builds **trust and foresight**: you see both the *causes* of heat and the *long-term impact* of greening.
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

            # Save snapshots for multiple years
            if year in [5, 10, 15, 20]:
                temporal_results[city][f"heatmap_year{year}"] = heat_sim
        temporal_results[city]["heatmap_baseline"] = heat_baseline

        # --- Interactive comparison Baseline vs Snapshots ---
        if st.checkbox(f"🌍 Show Interactive Baseline + Future Snapshots – {city}"):
            # Controls stacked vertically
            cmap = st.selectbox(
                f"🎨 Choose Color Ramp for {city}",
                ["inferno", "viridis", "plasma", "magma", "cividis"],
                index=0, key=f"cmap_{city}"
            )
            opacity = st.slider(f"🔎 Raster Opacity for {city}", 0.1, 1.0, 0.7, step=0.05, key=f"opacity_{city}")

            baseline_path = os.path.join(city_dir, "heat_index.tif")
            with rasterio.open(baseline_path) as src:
                bounds = src.bounds
                crs = src.crs
                transform = src.transform

            m = geemap.Map(center=[(bounds.top+bounds.bottom)/2, (bounds.left+bounds.right)/2], zoom=12)

            # Add all snapshots
            scenario_maps = {
                "Baseline": temporal_results[city]["heatmap_baseline"],
                "Year 5": temporal_results[city]["heatmap_year5"],
                "Year 10": temporal_results[city]["heatmap_year10"],
                "Year 15": temporal_results[city]["heatmap_year15"],
                "Year 20": temporal_results[city]["heatmap_year20"],
            }

            # Add each snapshot with consistent scale
            for sc, arr in scenario_maps.items():
                tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
                with rasterio.open(
                    tmpfile.name, "w",
                    driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                    count=1, dtype="float32", crs=crs, transform=transform
                ) as dst:
                    dst.write(arr.astype("float32"), 1)

                m.add_raster(tmpfile.name, colormap=cmap, layer_name=f"{city} – {sc}", opacity=opacity, vmin=0, vmax=1)

            # Add difference map (Year 20 - Baseline)
            diff = temporal_results[city]["heatmap_year20"] - temporal_results[city]["heatmap_baseline"]
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            with rasterio.open(
                tmpfile.name, "w",
                driver="GTiff", height=diff.shape[0], width=diff.shape[1],
                count=1, dtype="float32", crs=crs, transform=transform
            ) as dst:
                dst.write(diff.astype("float32"), 1)

            m.add_raster(tmpfile.name, colormap=cmap, layer_name=f"{city} – Cooling Effect (20y - Baseline)", opacity=0.7, vmin=-0.5, vmax=0.5)

            # Basemap and controls
            m.add_basemap("CartoVoyager")
            m.add_child(folium.LayerControl())

            # Show map
            m.to_streamlit(width=800, height=600)

            # --- Legend below the map ---
            colormap = cm.LinearColormap(
                colors=[plt.get_cmap(cmap)(i) for i in np.linspace(0, 1, 256)],
                vmin=0, vmax=1
            )
            colormap.caption = "Heat Index (0 = cool, 1 = hot)"
            legend_html = colormap._repr_html_()
            components.html(legend_html, height=100)

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
