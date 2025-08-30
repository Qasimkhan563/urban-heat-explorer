import streamlit as st
import os, json
from ee_auth import init_ee
init_ee()

# Make layout wide
st.set_page_config(layout="wide")
from steps import (
    step0_select_city, step1_parameters, step2_costs,
    step3a_heatmaps, step3b_explainability, step3c_costs,
    step3d_policy_game, step4_feedback, step5_results_export
)

BASE_DIR = os.path.join(os.path.dirname(__file__), "data")
CITIES_FILE = os.path.join(os.path.dirname(__file__), "available_cities.json")

# --- Initialize session state ---
if "step" not in st.session_state:
    st.session_state["step"] = 0

# --- Load available cities (persistent) ---
if "available_cities" not in st.session_state:
    if os.path.exists(CITIES_FILE):
        with open(CITIES_FILE, "r") as f:
            st.session_state["available_cities"] = json.load(f)
    else:
        # default list if no JSON exists
        st.session_state["available_cities"] = [
            "Lisbon", "Zurich", "Munster", "Tirana",
            "Podgorica Montenegro", "Karlsruhe", "Seville Spain", "Copenhagen"
        ]
        with open(CITIES_FILE, "w") as f:
            json.dump(st.session_state["available_cities"], f)

st.title("🌳 Urban Heat Mitigation – Guided Explorer")

# --- Routing ---
if st.session_state["step"] == 0:
    step0_select_city.run_step(BASE_DIR, st.session_state["available_cities"])
elif st.session_state["step"] == 1:
    step1_parameters.run_step()
elif st.session_state["step"] == 2:
    step2_costs.run_step()
elif st.session_state["step"] == 3.1:
    step3a_heatmaps.run_step(BASE_DIR)
elif st.session_state["step"] == 3.2:
    step3b_explainability.run_step(BASE_DIR)
elif st.session_state["step"] == 3.3:
    step3c_costs.run_step()
elif st.session_state["step"] == 3.4:
    step3d_policy_game.run_step()
elif st.session_state["step"] == 4:
    step4_feedback.run_step()
elif st.session_state["step"] == 5:
    step5_results_export.run_step()
