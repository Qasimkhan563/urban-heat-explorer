import streamlit as st
from fpdf import FPDF
import datetime
import os

# -----------------------------
# PDF Export Helper (fpdf2)
# -----------------------------
def export_pdf_report(include_abs, include_pct, include_carbon, include_sdg, include_recs, include_figs):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ✅ Load fonts from local "fonts" directory (must exist alongside app)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(base_dir, "..", "fonts")

    # Register fonts with Unicode support
    pdf.add_font("DejaVu", "", os.path.join(font_dir, "DejaVuSans.ttf"), uni=True)
    pdf.add_font("DejaVu", "B", os.path.join(font_dir, "DejaVuSans-Bold.ttf"), uni=True)

    pdf.set_font("DejaVu", "", 14)

    # -----------------------------
    # Cover Page
    # -----------------------------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 20)
    pdf.cell(0, 20, "Urban Heat Mitigation Report", ln=True, align="C")
    pdf.set_font("DejaVu", "", 14)
    pdf.cell(0, 10, f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    pdf.ln(20)

    # -----------------------------
    # Executive Summary
    # -----------------------------
    if "df_abs" in st.session_state:
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)
        pdf.cell(0, 10, "Executive Summary", ln=True)
        pdf.set_font("DejaVu", "", 12)
        pdf.ln(5)

        df_abs = st.session_state["df_abs"]

        for city in df_abs.index:
            baseline = df_abs.loc[city, "Baseline"]
            best_scenario = df_abs.loc[city].drop("Baseline").idxmin()
            best_value = df_abs.loc[city, best_scenario]
            reduction = (baseline - best_value) / baseline * 100 if baseline > 0 else 0
            pdf.multi_cell(0, 8,
                f"In {city}, the best intervention is {best_scenario}, reducing high-heat area "
                f"from {baseline:.2f} km² to {best_value:.2f} km² ({reduction:.1f}% reduction)."
            )
            pdf.ln(2)

        if "recommendations" in st.session_state:
            pdf.multi_cell(0, 8, "Key Recommendations:")
            for rec in st.session_state["recommendations"]:
                pdf.multi_cell(0, 8, f"- {rec}")

    # -----------------------------
    # Terminologies & Methods
    # -----------------------------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Terminologies & Methods", ln=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8,
        "This report evaluates urban heat mitigation strategies using Earth Observation (EO) "
        "and participatory digital twin approaches. Key concepts include:\n\n"
        "- Urban Heat Island (UHI) – localized heating effect due to impervious surfaces.\n"
        "- NDVI (Normalized Difference Vegetation Index) – proxy for vegetation cover.\n"
        "- Scenarios – greening interventions (Canopy expansion, Green roofs, Parks).\n"
        "- Baseline – current situation, using Sentinel-2 imagery and urban morphology data.\n\n"
        "Methods involve raster-based analysis, scenario simulation, and integration with participatory inputs "
        "collected via Streamlit interface."
    )

    # -----------------------------
    # Tools & Technologies
    # -----------------------------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Tools & Technologies", ln=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8,
        "The analysis pipeline was built using open-source tools:\n\n"
        "- Streamlit – interactive web app development.\n"
        "- Rasterio & Numpy – geospatial raster processing.\n"
        "- Folium & Geemap – interactive mapping and participatory inputs.\n"
        "- Plotly & Matplotlib – data visualization.\n"
        "- FPDF – report generation.\n\n"
        "Datasets include Sentinel-2 imagery, Copernicus DEM, OpenStreetMap building footprints, "
        "and stakeholder-provided annotations."
    )

    # -----------------------------
    # Helper: Add Tables
    # -----------------------------
    def add_table(title, df):
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)
        pdf.cell(0, 10, title, ln=True)
        pdf.set_font("DejaVu", "", 8)
        pdf.ln(5)

        # Header
        for col in df.columns:
            pdf.cell(40, 8, str(col), border=1)
        pdf.ln()

        # Rows
        for _, row in df.iterrows():
            for val in row:
                pdf.cell(40, 8, str(val), border=1)
            pdf.ln()

    # -----------------------------
    # Results (Tables)
    # -----------------------------
    if include_abs and "df_abs" in st.session_state:
        add_table("High-Heat Area (km²)", st.session_state["df_abs"])

    if include_pct and "df_pct" in st.session_state:
        add_table("Reduction vs Baseline (%)", st.session_state["df_pct"])

    if include_carbon and "df_carbon" in st.session_state:
        add_table("Carbon Benefits (tons CO2/yr)", st.session_state["df_carbon"])

    if include_sdg and "df_sdg" in st.session_state:
        add_table("SDG Alignment", st.session_state["df_sdg"])

    # -----------------------------
    # Insights & Policy Relevance
    # -----------------------------
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Insights & Policy Relevance", ln=True)
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8,
        "The results demonstrate that targeted greening interventions can significantly "
        "reduce urban heat exposure, enhance carbon sequestration, and contribute to multiple SDGs "
        "(11: Sustainable Cities, 13: Climate Action, 15: Life on Land).\n\n"
        "The participatory framework ensures that interventions reflect both technical feasibility "
        "and stakeholder priorities, strengthening policy uptake. The tool also provides a foundation "
        "for cross-city comparisons and scalable digital twin infrastructures."
    )

    # -----------------------------
    # Figures
    # -----------------------------
    if include_figs and "prepared_heatmaps" in st.session_state:
        for title, path in st.session_state["prepared_heatmaps"]:
            pdf.add_page()
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, title, ln=True)
            try:
                pdf.image(path, x=10, y=30, w=180)
            except Exception as e:
                pdf.ln(20)
                pdf.multi_cell(0, 10, f"[Image could not be loaded: {e}]")

    # -----------------------------
    # Save File
    # -----------------------------
    output_path = "UrbanHeat_Report.pdf"
    pdf.output(output_path, "F")
    return output_path


# -----------------------------
# Main Step
# -----------------------------
def run_step():
    st.header("Step 5: Export Report")

    st.markdown("""
    📥 Here you can export a **custom PDF report**.  
    Select the components you want to include:
    """)

    # Checkboxes for content selection
    include_abs = st.checkbox("📊 High-Heat Area (km²)", value=True)
    include_pct = st.checkbox("📉 Reduction vs Baseline (%)", value=True)
    include_carbon = st.checkbox("🌱 Carbon Benefits", value=True)
    include_sdg = st.checkbox("🌐 SDG Alignment", value=False)
    include_recs = st.checkbox("💡 Recommendations", value=True)
    include_figs = st.checkbox("🖼 Heatmaps & Figures", value=True)

    if st.button("📥 Generate PDF Report"):
        pdf_path = export_pdf_report(
            include_abs, include_pct, include_carbon, include_sdg, include_recs, include_figs
        )
        with open(pdf_path, "rb") as f:
            st.download_button("⬇️ Download Report", f, file_name="UrbanHeat_Report.pdf")

    # Navigation
    col1, col2, col3 = st.columns([1,1,1])  # 🔹 added a 3rd column
    with col1:
        if st.button("⬅️ Back"):
            st.session_state["step"] = 4
            st.rerun()
    with col2:
        if st.button("🏁 Finish"):
            st.success("🎉 Workflow complete!")
    with col3:  # 🔹 NEW BUTTON
        if st.button("🔄 New City Selection"):
            st.session_state.clear()  # reset all session state
            st.session_state["step"] = 0
            st.rerun()
