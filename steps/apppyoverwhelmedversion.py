import streamlit as st
import numpy as np
import pandas as pd
import rasterio
import os
from io import BytesIO
import plotly.express as px
from pathlib import Path
from fpdf import FPDF
import matplotlib.pyplot as plt
import tempfile
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
import contextily as ctx

# =========================
# CONFIG
# =========================
BASE_DIR = r"C:\Users\hp\Downloads\app2"
AVAILABLE_CITIES = ["Lisbon", "Zurich", "Munster", "Athens", "Karlsruhe"]
pixel_size = 10  # meters

SCENARIO_INFO = {
    "Baseline": "Current urban condition without interventions.",
    "Scenario A (Canopy)": "🌳 Expand street tree canopy in hottest 20% areas (+NDVI).",
    "Scenario B (Roofs)": "🏢 Install green roofs on flat buildings (+NDVI).",
    "Scenario C (Parks)": "🏞 Add pocket parks in vacant low-NDVI parcels (+NDVI)."
}

# =========================
# HELPERS
# =========================
def load_raster(path):
    with rasterio.open(path) as src:
        return src.read(1).astype(float)

def compute_heat_index(ndvi_new, built_raster, slope_norm):
    return built_raster - ndvi_new + slope_norm * 0.2

def high_heat_area(heat, threshold=0.7):
    return np.sum(heat > threshold) * (pixel_size**2) / 1e6  # km²

def process_city(city, canopy_increase, roof_increase, park_increase):
    """Load data, run scenarios, return metrics"""
    city_dir = os.path.join(BASE_DIR, city)
    ndvi_norm     = load_raster(os.path.join(city_dir, "ndvi_norm.tif"))
    slope_norm    = load_raster(os.path.join(city_dir, "slope.tif"))
    built_raster  = load_raster(os.path.join(city_dir, "buildings.tif"))
    heat_baseline = load_raster(os.path.join(city_dir, "heat_index.tif"))

    # Scenario A – Canopy
    threshold = np.nanpercentile(heat_baseline, 80)
    ndvi_A = ndvi_norm.copy()
    ndvi_A[heat_baseline >= threshold] = np.minimum(1, ndvi_A[heat_baseline >= threshold] + canopy_increase)
    heat_A = compute_heat_index(ndvi_A, built_raster, slope_norm)

    # Scenario B – Roofs
    flat_roofs = (slope_norm < 0.05) & (built_raster == 1)
    ndvi_B = ndvi_norm.copy()
    ndvi_B[flat_roofs] = np.minimum(1, ndvi_B[flat_roofs] + roof_increase)
    heat_B = compute_heat_index(ndvi_B, built_raster, slope_norm)

    # Scenario C – Parks
    vacant = (built_raster == 0) & (ndvi_norm < 0.2)
    ndvi_C = ndvi_norm.copy()
    ndvi_C[vacant] = np.minimum(1, ndvi_C[vacant] + park_increase)
    heat_C = compute_heat_index(ndvi_C, built_raster, slope_norm)

    metrics = {
        "Baseline": high_heat_area(heat_baseline),
        "Scenario A (Canopy)": high_heat_area(heat_A),
        "Scenario B (Roofs)": high_heat_area(heat_B),
        "Scenario C (Parks)": high_heat_area(heat_C)
    }

    return metrics

# =========================
# STREAMLIT UI
# =========================
st.title("🌳 Urban Heat Mitigation – Multi-City Scenario Explorer")

# =========================
# INTRODUCTION / USER GUIDE
# =========================
with st.expander("📖 User Guide – Click to expand/collapse"):
    st.markdown("""
    ## 🔍 1. Background
    Urban areas suffer from heat stress due to dense construction and limited vegetation.  
    This tool allows **planners, researchers, and citizens** to explore **greening strategies** that can reduce high-heat areas, store carbon, and improve liveability.

    ## 🛠 2. Methods & Data
    - **Input data**: Normalized NDVI, slope raster, building raster, and heat index map for each city.
    - **Heat Index**: Computed as `built-up density – NDVI + slope * 0.2`, ranging from 0 (cool) to 1 (hot).
    - **Threshold**: High-heat zones are defined as pixels with Heat Index > 0.7.

    ## 🌱 3. Scenarios
    - **Baseline**: Current condition, no intervention.  
    - **Scenario A (Canopy)**: 🌳 Expand tree canopy in the top 20% hottest areas.  
    - **Scenario B (Roofs)**: 🏢 Add green roofs on flat buildings.  
    - **Scenario C (Parks)**: 🏞 Convert vacant land with low NDVI into pocket parks.

    ## 📊 4. Metrics
    The tool reports:
    - High-heat area (km²)  
    - % reduction vs baseline  
    - Extended metrics (costs, carbon, % area affected)  
    - Optional equity analysis  

    ## 👥 5. Stakeholder Feedback
    Users can submit info, rate interventions, and download feedback as CSV.  
    This bridges **scientific scenarios** with **citizen preferences**.

    ## ⚠️ 6. Challenges & Limitations
    - Simplified NDVI-based greening impact  
    - Demographics optional  
    - Results are comparative, not forecasts  

    ## 🧭 7. How to Use
    1. Select cities from sidebar  
    2. Choose scenario parameters  
    3. Explore heatmaps, charts, SDGs  
    4. Submit feedback & download reports  
    """)


# =========================
# ENHANCEMENT 1: City thumbnails
# =========================
st.sidebar.header("🏙 Select cities")
cols = st.sidebar.columns(2)
selected_cities = []
for i, city in enumerate(AVAILABLE_CITIES):
    col = cols[i % 2]
    preview_path = Path(BASE_DIR) / city / "preview.png"
    if preview_path.exists():
        col.image(str(preview_path), caption=city, use_column_width=True)
    if col.checkbox(city, key=f"chk_{city}"):
        selected_cities.append(city)

# =========================
# ENHANCEMENT 2: Preset scenarios
# =========================
st.sidebar.markdown("### 🔧 Scenario Parameters (ΔNDVI)")
preset = st.sidebar.radio("Select preset:", ["Custom", "Moderate Greening", "Aggressive Greening"], key="preset_choice")

if preset == "Moderate Greening":
    canopy_increase = 0.2
    roof_increase   = 0.3
    park_increase   = 0.25
elif preset == "Aggressive Greening":
    canopy_increase = 0.4
    roof_increase   = 0.5
    park_increase   = 0.5
else:  # Custom mode
    st.sidebar.caption("NDVI ranges 0–1, higher = more vegetation")
    canopy_increase = st.sidebar.slider("🌳 Canopy increase in hotspots", 0.0, 0.5, 0.2, 0.05, key="canopy_slider")
    roof_increase   = st.sidebar.slider("🏢 Green roof NDVI increase", 0.0, 0.5, 0.3, 0.05, key="roof_slider")
    park_increase   = st.sidebar.slider("🏞 Pocket park NDVI increase", 0.0, 0.5, 0.25, 0.05, key="park_slider")

# =========================
# ENHANCEMENT: Cost & Carbon Parameters
# =========================
st.sidebar.markdown("### 💶 Cost & Carbon Parameters")

cost_levels = {
    "Low": (20, 40),
    "Medium": (50, 100),
    "High": (80, 150)
}
roof_levels = {
    "Low": (80, 120),
    "Medium": (100, 180),
    "High": (150, 220)
}
park_levels = {
    "Low": (30, 70),
    "Medium": (50, 100),
    "High": (80, 140)
}

cost_canopy = cost_levels[st.sidebar.selectbox("🌳 Canopy cost level", list(cost_levels.keys()), index=1, key="canopy_cost")]
cost_roofs  = roof_levels[st.sidebar.selectbox("🏢 Green roofs cost level", list(roof_levels.keys()), index=1, key="roof_cost")]
cost_parks  = park_levels[st.sidebar.selectbox("🏞 Pocket parks cost level", list(park_levels.keys()), index=1, key="park_cost")]

carbon_factor = st.sidebar.number_input("🌱 Carbon sequestration (kg CO₂/m²/yr)", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="carbon_input")

# =========================
# STAKEHOLDER FEEDBACK FORM
# =========================
st.sidebar.markdown("### 👥 Stakeholder Feedback")
with st.sidebar.form(key="survey_form"):
    st.write("### 👤 Stakeholder Information")
    name = st.text_input("Full Name")
    profession = st.text_input("Profession")
    nationality = st.text_input("Nationality")

    st.write("### 📝 Rate the feasibility of each intervention (1 = Not feasible, 5 = Highly feasible)")
    canopy_rating = st.slider("🌳 Street Trees", 1, 5, 3, key="canopy_rating")
    roof_rating   = st.slider("🏢 Green Roofs", 1, 5, 3, key="roof_rating")
    park_rating   = st.slider("🏞 Pocket Parks", 1, 5, 3, key="park_rating")

    submit_feedback = st.form_submit_button("Submit Feedback")


if submit_feedback:
    feedback = {
        "Name": name,
        "Profession": profession,
        "Nationality": nationality,
        "Cities": selected_cities,
        "Canopy": canopy_rating,
        "Roofs": roof_rating,
        "Parks": park_rating
    }
    st.session_state.setdefault("survey_responses", []).append(feedback)

    # Append directly to feedback.csv
    import csv
    feedback_file = os.path.join(BASE_DIR, "feedback.csv")
    file_exists = os.path.isfile(feedback_file)
    with open(feedback_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=feedback.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(feedback)

    st.success("✅ Feedback submitted. Thank you!")

if "survey_responses" in st.session_state and st.sidebar.button("📥 Download Survey Responses"):
    df_feedback = pd.DataFrame(st.session_state["survey_responses"])
    csv_feedback = df_feedback.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("⬇️ Download CSV", csv_feedback, "survey_feedback.csv", "text/csv")

# =========================
# SCENARIO SHARING LINK
# =========================
import urllib.parse
params = {
    "cities": ",".join(selected_cities),
    "canopy": canopy_increase,
    "roofs": roof_increase,
    "parks": park_increase,
    "preset": preset
}
base_url = "http://localhost:8501/"  # change if deployed
share_url = base_url + "?" + urllib.parse.urlencode(params)

st.sidebar.markdown("### 🔗 Share Scenario")
st.sidebar.text_input("Copy this link:", share_url)


# =========================
# RUN PROCESSING
# =========================
if len(selected_cities) > 0:
    all_metrics = {}
    for city in selected_cities:
        # Always pass the *current* scenario parameters
        metrics = process_city(city, canopy_increase, roof_increase, park_increase)
        all_metrics[city] = metrics

    df_abs = pd.DataFrame(all_metrics).T.round(2)

    # Compute % reduction
    df_pct = df_abs.copy()
    for col in df_abs.columns:
        if col != "Baseline":
            df_pct[col] = (df_abs["Baseline"] - df_abs[col]) / df_abs["Baseline"] * 100
    df_pct["Baseline"] = 0.0
    df_pct = df_pct.round(1)

    # =========================
# HEATMAP VISUALIZATION (only if one city selected)
# =========================
if len(selected_cities) == 1:
    st.subheader(f"🌡 Heatmaps – {selected_cities[0]}")
    city = selected_cities[0]
    city_dir = os.path.join(BASE_DIR, city)

    # Reload rasters (Baseline + Scenarios)
    ndvi_norm     = load_raster(os.path.join(city_dir, "ndvi_norm.tif"))
    slope_norm    = load_raster(os.path.join(city_dir, "slope.tif"))
    built_raster  = load_raster(os.path.join(city_dir, "buildings.tif"))
    heat_baseline = load_raster(os.path.join(city_dir, "heat_index.tif"))

    # Recompute scenarios
    threshold = np.nanpercentile(heat_baseline, 80)
    ndvi_A = ndvi_norm.copy()
    ndvi_A[heat_baseline >= threshold] = np.minimum(1, ndvi_A[heat_baseline >= threshold] + canopy_increase)
    heat_A = compute_heat_index(ndvi_A, built_raster, slope_norm)

    flat_roofs = (slope_norm < 0.05) & (built_raster == 1)
    ndvi_B = ndvi_norm.copy()
    ndvi_B[flat_roofs] = np.minimum(1, ndvi_B[flat_roofs] + roof_increase)
    heat_B = compute_heat_index(ndvi_B, built_raster, slope_norm)

    vacant = (built_raster == 0) & (ndvi_norm < 0.2)
    ndvi_C = ndvi_norm.copy()
    ndvi_C[vacant] = np.minimum(1, ndvi_C[vacant] + park_increase)
    heat_C = compute_heat_index(ndvi_C, built_raster, slope_norm)

    heatmaps = {
        "Baseline": heat_baseline,
        "Scenario A (Canopy)": heat_A,
        "Scenario B (Roofs)": heat_B,
        "Scenario C (Parks)": heat_C
    }

    # Store figure paths for later PDF use
    st.session_state["heatmap_figs"] = []

    # Open source raster to get CRS + transform
    with rasterio.open(os.path.join(city_dir, "heat_index.tif")) as src:
        src_crs = src.crs
        src_transform = src.transform
        src_bounds = src.bounds

    dst_crs = "EPSG:4326"  # WGS84 lat/long

    for sc, arr in heatmaps.items():
        # Calculate target transform for reprojection
        transform, width, height = calculate_default_transform(
            src_crs, dst_crs, arr.shape[1], arr.shape[0], *src_bounds
        )
        reprojected = np.empty((height, width), dtype=np.float32)

        # Reproject raster to EPSG:4326
        reproject(
            source=arr,
            destination=reprojected,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest
        )

        # Extent in lat/long
        xmin, ymin, xmax, ymax = transform_bounds(src_crs, dst_crs, *src_bounds)
        extent = (xmin, xmax, ymin, ymax)

        # Plot
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(reprojected, cmap="hot", vmin=0, vmax=1,
                       extent=extent, origin="upper")

        # Colorbar
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Heat Index (0 = Cool, 1 = Hot)", fontsize=10)

        # Grid + lat/long ticks
        ax.set_xticks(np.linspace(xmin, xmax, 6))
        ax.set_yticks(np.linspace(ymin, ymax, 6))
        ax.grid(color="white", linestyle="--", linewidth=0.5, alpha=0.7)

        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        ax.set_title(sc, fontsize=14)

        # Show in Streamlit
        st.pyplot(fig)

        # Save temporarily for PDF export
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(tmpfile.name, dpi=150, bbox_inches="tight")
        st.session_state["heatmap_figs"].append((sc, tmpfile.name))
        plt.close(fig)



    # =========================
    # ENHANCEMENT 3: Scenario descriptions
    # =========================
    st.subheader("ℹ️ Scenario Details")
    for scenario, desc in SCENARIO_INFO.items():
        with st.expander(scenario):
            st.write(desc)

    # =========================
    # Tables with ENHANCEMENT 4: Color-coded signals
    # =========================
    def signalize(val, baseline):
        if val < baseline * 0.6:
            return "🟢 Good"
        elif val < baseline * 0.85:
            return "🟡 Medium"
        else:
            return "🔴 Poor"

    st.subheader("📊 High-Heat Area (km²)")
    df_signals = df_abs.copy()
    for city in df_signals.index:
        base = df_signals.loc[city, "Baseline"]
        for col in df_signals.columns:
            df_signals.loc[city, col] = f"{df_signals.loc[city, col]:.2f} km² ({signalize(df_abs.loc[city,col], base)})"
    st.dataframe(df_signals)

    st.subheader("📊 Reduction vs Baseline (%)")
    st.dataframe(df_pct.style.format("{:.1f}%").highlight_max(color="lightblue", axis=0))

    # =========================
    # ENHANCEMENT 5: Auto-save last selection
    # =========================
    if "last_selection" not in st.session_state:
        st.session_state["last_selection"] = []
    st.session_state["last_selection"] = selected_cities

    # CSV Download
    csv_buf = BytesIO()
    df_out = df_abs.copy()
    for col in df_abs.columns:
        if col != "Baseline":
            df_out[col+"_reduction_%"] = df_pct[col]
    df_out.to_csv(csv_buf)
    st.download_button("📥 Download Metrics (CSV)", data=csv_buf.getvalue(),
                       file_name="multi_city_heat_metrics.csv", mime="text/csv")

    # Chart toggle
    chart_mode = st.radio("📊 Select chart view:", ["Absolute (km²)", "Reduction (%)"])
    if chart_mode == "Absolute (km²)":
        df_long_abs = df_abs.reset_index().melt(id_vars="index", var_name="Scenario", value_name="High Heat Area (km²)")
        df_long_abs.rename(columns={"index": "City"}, inplace=True)
        fig = px.bar(df_long_abs, x="City", y="High Heat Area (km²)", color="Scenario",
                     barmode="group", text="High Heat Area (km²)",
                     title="High-Heat Area across Cities and Scenarios")
        fig.update_traces(texttemplate="%{text:.2f} km²", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        df_long_pct = df_pct.reset_index().melt(id_vars="index", var_name="Scenario", value_name="Reduction (%)")
        df_long_pct.rename(columns={"index": "City"}, inplace=True)
        fig = px.bar(df_long_pct, x="City", y="Reduction (%)", color="Scenario",
                     barmode="group", text="Reduction (%)",
                     title="% Reduction in High-Heat Areas vs Baseline")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    # Ranking summary
    st.subheader("🏆 Key Insights")
    summary = []
    for scenario in df_pct.columns:
        if scenario != "Baseline":
            best_city = df_pct[scenario].idxmax()
            best_val = df_pct.loc[best_city, scenario]
            summary.append(f"- **{scenario}**: {best_city} achieved the greatest reduction (**{best_val:.1f}%**).")
    st.markdown("\n".join(summary))

    # =========================
    # EXTENDED METRICS & RESULTS (Phase 2)
    # =========================
    st.subheader("🌍 Extended Metrics & Co-Benefits")

    # --- 1. % of City Affected ---
    st.markdown("### 📏 % of City Area Affected")
    city_area_km2 = {}
    for city in selected_cities:
        city_dir = os.path.join(BASE_DIR, city)
        with rasterio.open(os.path.join(city_dir, "ndvi_norm.tif")) as src:
            width, height = src.width, src.height
        city_area_km2[city] = (width * height * (pixel_size**2)) / 1e6

    df_pct_area = pd.DataFrame(index=selected_cities, columns=df_abs.columns)
    for city in selected_cities:
        df_pct_area.loc[city] = (df_abs.loc[city] / city_area_km2[city]) * 100
    df_pct_area = df_pct_area.astype(float).round(1)
    st.dataframe(df_pct_area.style.format("{:.1f}%"))

    # --- 2. Population Exposed (placeholder) ---
    st.markdown("### 👥 Population Exposed (placeholder)")
    st.info("Overlay a population raster (e.g. WorldPop, GHSL) with high-heat mask to calculate residents in >0.7 zones.")

    # --- 3. Cost & Carbon Calculations ---
    cost_estimates = {
        "Scenario A (Canopy)": cost_canopy,
        "Scenario B (Roofs)": cost_roofs,
        "Scenario C (Parks)": cost_parks
    }
    cost_table = {}
    for city in df_abs.index:
        city_costs = {}
        for scenario, (low, high) in cost_estimates.items():
            area_diff_km2 = df_abs.loc[city, "Baseline"] - df_abs.loc[city, scenario]
            area_m2 = area_diff_km2 * 1e6
            city_costs[scenario] = (area_m2*low/1e6, area_m2*high/1e6)  # tuple in M€
        cost_table[city] = city_costs
    df_costs = pd.DataFrame(cost_table).T
    df_costs_fmt = df_costs.applymap(lambda x: f"€{x[0]:.1f}–{x[1]:.1f}M")

    df_costs_long = []
    for city in df_costs.index:
        for scenario, (low, high) in df_costs.loc[city].items():
            avg_cost = (low + high) / 2
            df_costs_long.append({"City": city, "Scenario": scenario, "Avg Cost (M€)": avg_cost})
    df_costs_long = pd.DataFrame(df_costs_long)

    carbon_table = {}
    for city in df_abs.index:
        city_carbon = {}
        for scenario in df_abs.columns:
            if scenario != "Baseline":
                area_diff_km2 = df_abs.loc[city, "Baseline"] - df_abs.loc[city, scenario]
                area_m2 = area_diff_km2 * 1e6
                city_carbon[scenario] = area_m2*carbon_factor/1000  # tons CO₂/yr
        carbon_table[city] = city_carbon
    df_carbon = pd.DataFrame(carbon_table).T.round(1)

    df_carbon_long = df_carbon.reset_index().melt(
        id_vars="index", var_name="Scenario", value_name="CO₂ (tons/yr)"
    )
    df_carbon_long.rename(columns={"index": "City"}, inplace=True)

    # --- Tabs for Heat | Cost | Carbon ---
    tab1, tab2, tab3 = st.tabs(["🔥 Heat", "💶 Cost", "🌱 Carbon"])

    with tab1:
        st.markdown("#### High-Heat Area (% of City)")
        st.dataframe(df_pct_area.style.format("{:.1f}%"))

    with tab2:
        st.markdown("#### Estimated Investment Costs (Millions €)")
        st.dataframe(df_costs_fmt)
        fig_costs = px.bar(df_costs_long, x="City", y="Avg Cost (M€)", color="Scenario",
                        barmode="group", text="Avg Cost (M€)",
                        title="Estimated Investment Costs by Scenario")
        fig_costs.update_traces(texttemplate="€%{text:.1f}M", textposition="outside")
        st.plotly_chart(fig_costs, use_container_width=True)

    with tab3:
        st.markdown("#### Estimated CO₂ Sequestration Benefits")
        st.dataframe(df_carbon.style.format("{:.1f} tons"))
        fig_carbon = px.bar(df_carbon_long, x="City", y="CO₂ (tons/yr)", color="Scenario",
                            barmode="group", text="CO₂ (tons/yr)",
                            title="Estimated CO₂ Sequestration Benefits")
        fig_carbon.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        st.plotly_chart(fig_carbon, use_container_width=True)
    
    # =========================
    # GAMIFICATION
    # =========================
    if selected_cities:
        st.sidebar.markdown("### 🎯 Challenge Mode")
        challenge_city = st.sidebar.selectbox("Choose a city for challenge:", selected_cities, key="challenge_city")
        target = st.sidebar.slider("Target reduction (%)", 10, 80, 50, key="challenge_target")

        reduction = df_pct.loc[challenge_city].drop("Baseline").max()
        st.subheader("🎯 Challenge Mode")
        st.write(f"Can you reduce heat by **{target}%** in {challenge_city}?")

        if reduction >= target:
            st.success(f"🏆 You did it! Reduction achieved: {reduction:.1f}%")
        else:
            st.warning(f"Current reduction: {reduction:.1f}%. Adjust sliders or try another strategy!")


    # =========================
    # SDG Benchmarking
    # =========================
    st.subheader("🌐 SDG Alignment")
    st.markdown("""
    - **SDG 11 – Sustainable Cities & Communities** 🏙: Reduced urban heat risk improves liveability.  
    - **SDG 13 – Climate Action** 🌍: Greening supports adaptation to climate change.  
    - **SDG 15 – Life on Land** 🌱: Enhances biodiversity and ecosystem services.  
    """)

    # =========================
    # EQUITY LENS (placeholder)
    # =========================
    st.subheader("⚖️ Equity Lens")
    equity_file = st.file_uploader("Upload demographic data (CSV with neighborhood + population)", type="csv")
    if equity_file:
        equity_df = pd.read_csv(equity_file)
        st.write("Preview of uploaded data:", equity_df.head())
        st.info("Next step: Overlay this with high-heat zones to estimate which groups benefit most.")
    else:
        st.info("Upload census/demographic CSV to analyze equity impacts.")

    # =========================
    # Recommendations
    # =========================
    st.subheader("💡 Custom Recommendations")
    for city in selected_cities:
        best = df_pct.loc[city].drop("Baseline").idxmax()
        best_val = df_pct.loc[city, best]
        st.markdown(f"- In **{city}**, {best} yields the highest % reduction (**{best_val:.1f}%**).")


    # --- 4. Ranking Dashboard ---
    st.subheader("📊 City Rankings")

    ranking_type = st.selectbox("Select ranking criteria", ["Heat Reduction", "Cost Efficiency", "Carbon Benefit"])

    if ranking_type == "Heat Reduction":
        most_vulnerable = df_pct_area["Baseline"].idxmax()
        most_resilient = df_pct_area.min(axis=1).idxmin()
        st.markdown(f"- **Most vulnerable city (Baseline % area affected)**: {most_vulnerable}")
        st.markdown(f"- **Most resilient city (lowest % after interventions)**: {most_resilient}")

    elif ranking_type == "Cost Efficiency":
        # Compute € per % reduction (cheapest per unit benefit)
        cost_eff = {}
        for city in df_costs.index:
            total_reduction = df_pct.loc[city].drop("Baseline").max()  # best scenario
            avg_cost = np.mean([np.mean(val) for val in df_costs.loc[city].values])
            cost_eff[city] = avg_cost / total_reduction if total_reduction > 0 else np.inf
        best_city = min(cost_eff, key=cost_eff.get)
        st.markdown(f"- **Most cost-efficient city**: {best_city} (lowest € per % heat reduction)")

    elif ranking_type == "Carbon Benefit":
        best_city = df_carbon.sum(axis=1).idxmax()
        best_val = df_carbon.sum(axis=1).max()
        st.markdown(f"- **City with highest carbon benefit**: {best_city} ({best_val:.1f} tons CO₂/yr)")

        # PDF Export
    st.subheader("📥 Export Report")
    if st.button("Generate PDF Report"):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0,10,"Urban Heat Mitigation Report")

        for city in selected_cities:
            pdf.set_font("Arial", 'B', 12)
            pdf.multi_cell(0,10,f"\nCity: {city}")
            pdf.set_font("Arial", size=12)
            for sc,val in all_metrics[city].items():
                pdf.multi_cell(0,10,f"{sc}: {val:.2f} km² high-heat area")

        # Add heatmaps if available
        if "heatmap_figs" in st.session_state:
            for sc, path in st.session_state["heatmap_figs"]:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0,10,sc, ln=True, align="C")
                pdf.image(path, x=10, y=30, w=180)

        path = "report.pdf"
        pdf.output(path)
        with open(path,"rb") as f:
            st.download_button("⬇️ Download PDF", f, "heat_report.pdf")


else:
    st.info("Please select at least one city to display results.")
