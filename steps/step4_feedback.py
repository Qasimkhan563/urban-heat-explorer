import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import shape
import os
import pandas as pd
import uuid
from datetime import datetime

def run_step():
    st.header("Step 5: Stakeholder Input & Co-Design")

    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        Here stakeholders provide **basic feedback** on the feasibility of interventions.  

        Example:  
        - 🌳 How realistic is planting more street trees in your city?  
        - 🏢 Are green roofs widely feasible?  
        - 🏞 Can new parks be built easily?  

        Why it matters:  
        - Collects **qualitative perceptions** of interventions.  
        - Reveals barriers (cost, regulations, space availability).  
        - Ensures the tool reflects **social as well as technical feasibility**.  
        """)

    st.markdown("🗺 Draw points or polygons on the map and classify them as 🌳 Trees, 🏢 Roofs, or 🏞 Parks.")

    # Create unique ID for each user/session
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = str(uuid.uuid4())  # random unique ID

    # Base map
    m = folium.Map(location=[49.0069, 8.4037], zoom_start=12)
    folium.plugins.Draw(
        export=True,
        draw_options={'polygon': True, 'marker': True, 'circle': False, 'polyline': False},
        edit_options={'edit': True}
    ).add_to(m)

    output = st_folium(m, width=700, height=500)

    if output and "all_drawings" in output and output["all_drawings"]:
        features = output["all_drawings"]

        # Convert drawn features into GeoDataFrame
        geoms = [shape(f["geometry"]) for f in features]
        gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326")

        # Per-feature classification
        categories = []
        for idx, geom in enumerate(gdf.geometry):
            cat = st.selectbox(
                f"Category for feature {idx+1}", 
                ["🌳 Trees", "🏢 Roofs", "🏞 Parks"], 
                key=f"cat_{idx}"
            )
            categories.append(cat)

        gdf["category"] = categories

        # Metadata
        gdf["user_id"] = st.session_state["user_id"]
        gdf["timestamp"] = datetime.utcnow().isoformat()
        gdf["timestamp"] = gdf["timestamp"].astype(str)

        st.write("### Your Selected Areas")
        st.write(gdf)

        # ✅ Save button (instead of export to user)
                # ✅ Save button (with metadata form)
        if st.button("💾 Save My Inputs"):
            st.session_state["show_metadata_form"] = True

    # If metadata form is triggered
    if st.session_state.get("show_metadata_form", False):
        st.subheader("👤 Please provide your details for records")

        with st.form("metadata_form"):
            name = st.text_input("Full Name")
            profession = st.text_input("Profession")
            company = st.text_input("Company/Organization")
            nationality = st.text_input("Nationality")
            submitted = st.form_submit_button("Submit ✅")

            if submitted:
                # --- Ensure save directory exists ---
                save_dir = os.path.join(os.path.dirname(__file__), "..", "data", "stakeholder_inputs")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, "stakeholder_inputs.geojson")
            
                if os.path.exists(save_path):
                    existing = gpd.read_file(save_path)
                    gdf = pd.concat([existing, gdf], ignore_index=True)
            
                # Add metadata
                gdf["name"] = name
                gdf["profession"] = profession
                gdf["company"] = company
                gdf["nationality"] = nationality
            
                gdf["timestamp"] = gdf["timestamp"].astype(str)  # ensure JSON serializable
                gdf.to_file(save_path, driver="GeoJSON")
            
                st.success("✅ Your inputs and details have been saved for research and policy analysis.")
                st.session_state["show_metadata_form"] = False


    # -----------------------
    # Navigation
    # -----------------------
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 3.4
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["step"] = 5
            st.rerun()

