# ee_auth.py
import streamlit as st
import ee

def init_ee():
    """Initialize Google Earth Engine with Streamlit secrets."""
    try:
        # Load from .streamlit/secrets.toml
        service_account = st.secrets["gcp_service_account"]["client_email"]
        private_key = st.secrets["gcp_service_account"]["private_key"]

        credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
        ee.Initialize(credentials)
        st.success("✅ Earth Engine initialized successfully with service account.")
    except Exception as e:
        st.error(f"⚠️ Failed to initialize Earth Engine: {e}")
