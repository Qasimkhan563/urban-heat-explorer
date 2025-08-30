import ee
import streamlit as st
import json

def init_ee():
    if "ee_initialized" in st.session_state:
        return
    try:
        # Convert AttrDict → dict
        key_json = dict(st.secrets["gcp_service_account"])
        service_account = key_json["client_email"]

        # Build credentials directly from JSON string
        credentials = ee.ServiceAccountCredentials(service_account, key_data=json.dumps(key_json))
        ee.Initialize(credentials)

        st.session_state["ee_initialized"] = True
        st.success("✅ Earth Engine initialized.")
    except Exception as e:
        st.error(f"❌ Failed to initialize Earth Engine: {e}")
