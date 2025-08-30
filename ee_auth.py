# ee_auth.py
import ee
import streamlit as st

def init_ee():
    """Initialize Earth Engine with Streamlit secrets (runs only once)."""
    if not ee.data._credentials:  # prevent re-initializing
        service_account = st.secrets["GEE_CLIENT_EMAIL"]
        private_key = st.secrets["GEE_PRIVATE_KEY"]
        credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
        ee.Initialize(credentials)
