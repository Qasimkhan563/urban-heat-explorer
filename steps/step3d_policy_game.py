import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import random
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import shape
from datetime import datetime
import uuid
import os
import rasterio

BASE_DIR = r"C:\Users\hp\Downloads\app2"

def get_city_center(city):
    """Return lat/lon center of the city's raster extent"""
    raster_path = os.path.join(BASE_DIR, city, "ndvi_norm.tif")
    with rasterio.open(raster_path) as src:
        bounds = src.bounds
        lon = (bounds.left + bounds.right) / 2
        lat = (bounds.top + bounds.bottom) / 2
        return lat, lon

def run_step():
    st.header("Step 4D: Policy Alignment & Games")

    # ------------------------
    # Help
    # ------------------------
    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        This step connects results to **policy goals** and adds **interactive games**:  

        - 🌐 **SDG Alignment** → shows how scenarios support UN SDGs.  
        - 🎮 **Budget Game** → allocate €100M to trees, roofs, parks.  
        - 🎯 **Challenge Mode** → meet cooling/climate targets under a budget.  
        - 🗺 **Spatial Planting Mini-Game** → place greening interventions directly on the map.  

        👉 Why? → Makes planning **engaging, participatory, and transparent**.
        """)

    # ------------------------
    # 🎯 Challenge Mode
    # ------------------------
    st.subheader("🎯 Challenge Mode")

    challenges = [
        {"goal": "≥30% heat reduction", "min_reduction": 30, "max_cost": 80},
        {"goal": "≥2000 tons CO₂/yr captured", "min_co2": 2000, "max_cost": 100},
        {"goal": "≥20% reduction with ≤€50M", "min_reduction": 20, "max_cost": 50},
    ]

    if "active_challenge" not in st.session_state:
        st.session_state["active_challenge"] = random.choice(challenges)

    challenge = st.session_state["active_challenge"]
    st.info(f"Your challenge: {challenge['goal']} (Budget ≤ {challenge['max_cost']} M€)")

    if st.button("🔄 New Challenge"):
        st.session_state["active_challenge"] = random.choice(challenges)
        st.session_state.pop("drawn_features", None)
        st.session_state.pop("classified_features", None)
        st.rerun()

    # Evaluate with df_abs if available
    if "df_abs" in st.session_state:
        df_abs = st.session_state["df_abs"]
        df_pct = df_abs.copy()
        for col in df_abs.columns:
            if col != "Baseline":
                df_pct[col] = (df_abs["Baseline"] - df_abs[col]) / df_abs["Baseline"] * 100
        df_pct["Baseline"] = 0.0

        for city in df_pct.index:
            reduction = df_pct.loc[city].drop("Baseline").max()
            cost = random.randint(30, 100)  # ⚠️ placeholder: replace with step 3C cost logic
            if reduction >= challenge.get("min_reduction", 0) and cost <= challenge["max_cost"]:
                st.success(f"✅ {city} meets the challenge! (Reduction {reduction:.1f}%, Cost {cost} M€)")
            else:
                st.warning(f"⚠️ {city} does not meet challenge (Reduction {reduction:.1f}%, Cost {cost} M€), please zoom to your city and select polygon/points within your city of analysis")

    # ------------------------
    # 🗺 Spatial Planting Mini-Game
    # ------------------------
    st.subheader("🗺 Spatial Planting Mini-Game")
    st.markdown("Draw polygons or points for **🌳 Trees, 🏢 Roofs, 🏞 Parks**.")

    # Map
    m = folium.Map(location=[49.0069, 8.4037], zoom_start=5)
    Draw(
        draw_options={"polygon": True, "marker": True},
        edit_options={"edit": True, "remove": True}
    ).add_to(m)

    output = st_folium(m, width=700, height=500)

    # Store drawings if any
    if output and "all_drawings" in output and output["all_drawings"]:
        st.session_state["drawn_features"] = output["all_drawings"]

    # Step 1 → Process button
    if "drawn_features" in st.session_state and not st.session_state.get("classified_features"):
        if st.button("✅ Process My Interventions"):
            st.session_state["classified_features"] = [
                {"geometry": shape(f["geometry"]), "category": None}
                for f in st.session_state["drawn_features"]
            ]
            st.rerun()

    # Step 2 → Classification
    if "classified_features" in st.session_state:
        categories = []
        for idx, f in enumerate(st.session_state["classified_features"]):
            st.write(f"Feature {idx+1}: {f['geometry'].geom_type}")
            cat = st.selectbox(
                f"Select type for feature {idx+1}",
                ["🌳 Tree", "🏢 Roof", "🏞 Park"],
                key=f"class_{idx}"
            )
            categories.append(cat)
            st.write(f"→ Recorded as {cat}")

        # Step 3 → Save button
        if st.button("💾 Save My Inputs"):
            gdf = gpd.GeoDataFrame(
                [{"geometry": f["geometry"], "category": cat,
                  "user_id": st.session_state.get("user_id", str(uuid.uuid4())),
                  "timestamp": datetime.utcnow().isoformat()}
                 for f, cat in zip(st.session_state["classified_features"], categories)],
                crs="EPSG:4326"
            )

            save_path = "stakeholder_inputs.geojson"
            if os.path.exists(save_path):
                existing = gpd.read_file(save_path)
                gdf = pd.concat([existing, gdf], ignore_index=True)
            gdf.to_file(save_path, driver="GeoJSON")

            st.success("✅ Your interventions have been saved!")

            # --------------------
            # 🎯 Scoring / Feedback
            # --------------------
            st.subheader("📊 Impact Score – Your Plan")
            ndvi_boost = {"🌳 Tree": 0.15, "🏢 Roof": 0.10, "🏞 Park": 0.20}

            counts = gdf["category"].value_counts().to_dict()

            base_reduction = 20
            extra_reduction = sum(counts.get(cat, 0) * ndvi_boost[cat] * 2 for cat in ndvi_boost)
            final_reduction = min(100, base_reduction + extra_reduction)

            co2_gain = sum(counts.get(cat, 0) * ndvi_boost[cat] * 100 for cat in ndvi_boost)  # tons/yr
            cost_gain = sum(counts.get(cat, 0) * ndvi_boost[cat] * 5 for cat in ndvi_boost)   # M€

            st.metric("🌡 Heat Reduction", f"{final_reduction:.1f}%")
            st.metric("🌱 Extra Carbon Capture", f"{co2_gain:.0f} tons/yr")
            st.metric("💶 Estimated Cost", f"€{cost_gain:.1f} M")

            st.info("💡 Tip: Try drawing different mixes of 🌳 Trees, 🏢 Roofs, and 🏞 Parks to balance cooling, carbon, and costs.")

            if st.button("🆕 New Round"):
                st.session_state.pop("drawn_features", None)
                st.session_state.pop("classified_features", None)
                st.rerun()

    # ------------------------
    # Navigation
    # ------------------------
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 3.3
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["step"] = 4
            st.rerun()
