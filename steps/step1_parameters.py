import streamlit as st

def run_step():
    st.header("Step 2: Scenario Parameters")
    with st.expander("ℹ️ Help: About This Step"):
        st.markdown("""
        Here you define **how much greening** to add in the simulation.  

        - 🌳 **Canopy increase in hotspots** → planting more street trees in overheated areas.  
        - 🏢 **Green roof NDVI increase** → making rooftops greener (vegetation) or cooler (reflective).  
        - 🏞 **Pocket park NDVI increase** → converting vacant land to small urban parks.  

        The sliders or presets change the **vegetation index (NDVI)** values in the model.  
        Higher values = stronger greening interventions.  

        💡 You can use **Custom** for precise control, or choose one of the presets:  
        - **Moderate Greening** → represents a *realistic but feasible level of intervention*, such as targeted street tree planting, incentivized roof greening programs, and a few small new parks.  
        - **High / Transformative Greening** → represents a *bold and visionary strategy*, where greenery is integrated across the city fabric (widespread tree planting, extensive roof greening, and larger-scale park creation).  

        ---

        ### 🔹 How does this affect the model?

        The app adjusts **NDVI values** to simulate new greenery:  
        - **Canopy** → raises NDVI in the **hottest 20% of pixels**.  
        - **Roofs** → raises NDVI on **flat rooftops (low slope, built-up areas)**.  
        - **Parks** → raises NDVI on **vacant/under-vegetated land**.  

        These updated NDVI rasters are plugged into the **Heat Index formula**:

        \[
        HI=B−(NDVI+Increase)+(S×0.2)
        \]

        where:  
        - \(B\) = Built-up density (1 = building, 0 = no building)  
        - \(NDVI\) = Vegetation cover (0–1 normalized)  
        - \(S\) = Slope (0–1 normalized)  

        🔑 Interpretation: Higher NDVI reduces the heat index, meaning **cooler areas**.
        """)

    preset = st.radio("Select preset:", ["Custom", "Moderate Greening", "High Greening"])

    if preset == "Moderate Greening":
        st.markdown("""
        **🌿 Moderate Greening (Realistic, feasible)**
        - 🌳 Targeted street tree planting in the hottest districts  
        - 🏢 Incentivized green roofs on selected public/private buildings  
        - 🏞 Creation of small pocket parks in vacant plots  
        """)
        canopy_increase, roof_increase, park_increase = 0.2, 0.3, 0.25

    elif preset == "High Greening":
        st.markdown("""
        **🌍 High / Transformative Greening (Bold, visionary)**
        - 🌳 Widespread tree planting along streets and boulevards  
        - 🏢 Large-scale adoption of green roofs across the city  
        - 🏞 Development of larger new parks and connected green corridors  
        """)
        canopy_increase, roof_increase, park_increase = 0.4, 0.5, 0.5

    else:
        canopy_increase = st.slider("🌳 Canopy increase in hotspots", 0.0, 0.5, 0.2, 0.05)
        roof_increase   = st.slider("🏢 Green roof NDVI increase", 0.0, 0.5, 0.3, 0.05)
        park_increase   = st.slider("🏞 Pocket park NDVI increase", 0.0, 0.5, 0.25, 0.05)

    # --- Preview for presets
    if preset != "Custom":
        st.info(f"Preset applied → 🌳 {canopy_increase}, 🏢 {roof_increase}, 🏞 {park_increase}")

    # --- Validation for zero increases
    if preset == "Custom" and canopy_increase == 0 and roof_increase == 0 and park_increase == 0:
        st.warning("⚠️ All greening increases are 0. The results will be identical to the baseline.")

    # --- Navigation buttons
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 0   # back to city selection
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state["canopy_increase"] = canopy_increase
            st.session_state["roof_increase"] = roof_increase
            st.session_state["park_increase"] = park_increase
            st.session_state["step"] = 2   # forward to cost & carbon params
            st.rerun()
