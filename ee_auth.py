import ee
import streamlit as st
import json
import os

def init_ee():
    if "ee_initialized" in st.session_state:
        return
    try:
        # Load full JSON from Streamlit secrets
        key_json = st.secrets["gcp_service_account"]  # name your section like [gcp_service_account] in secrets.toml
        service_account = key_json["client_email"]

        # Convert to proper credentials
        credentials = ee.ServiceAccountCredentials(service_account, key_data=json.dumps(key_json))
        ee.Initialize(credentials)
        st.session_state["ee_initialized"] = True
        st.success("✅ Earth Engine initialized.")
    except Exception as e:
        st.error(f"❌ Failed to initialize Earth Engine: {e}")
