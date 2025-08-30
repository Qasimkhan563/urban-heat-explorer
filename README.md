# 🌍 Urban Heat Mitigation App

An interactive **Streamlit web application** to analyze and simulate **Urban Heat Island (UHI) mitigation strategies** such as **tree canopy expansion, rooftop greening, and park development**.  

The app integrates **Google Earth Engine (EE)**, **OpenStreetMap (OSM)**, and **geospatial Python libraries** to allow planners, researchers, and communities to:  
- Map **baseline heat hotspots**  
- Run **scenario-based greening interventions**  
- Compare costs and impacts  
- Export results for reporting and decision-making  

---

## 🚀 Features

- ✅ Predefined cities (Lisbon, Zürich, Münster, Athens, Karlsruhe)  
- ✅ Upload custom datasets (AOI, DEM, NDVI, Buildings)  
- ✅ Auto-fetch new cities (via OSM + EE)  
- ✅ Compute **baseline heat index**:  
  \[
  HI = B - NDVI + (S \times 0.2)
  \]  
- ✅ Simulate greening scenarios (trees, roofs, parks)  
- ✅ Interactive maps with layer toggles & legends  
- ✅ Export metrics, maps, and reports (CSV / PDF / GeoTIFF)  
- ✅ Stakeholder feedback & policy prioritization modules  

---

## 📦 Installation

Clone the repository:

```bash
git clone https://github.com/your-username/urban-heat-mitigation-app.git
cd urban-heat-mitigation-app
```

Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔑 Earth Engine Authentication

This app requires a **Google Earth Engine service account**.  

1. Create a service account in your GCP project.  
2. Download the JSON key file.  
3. Add it to **Streamlit secrets**:

Create `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "XXXX"
private_key = """-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_CONTENT
-----END PRIVATE KEY-----"""
client_email = "your-service-account@your-project-id.iam.gserviceaccount.com"
client_id = "XXXX"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

---

## ▶️ Running the App

Run locally:

```bash
streamlit run app.py
```

Deploy to [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push your repo to GitHub.  
2. Go to Streamlit Cloud → "New App".  
3. Select your repo & branch.  
4. Add your service account to **App secrets**.  
5. Deploy 🎉  

---

## 📂 Workflow

The app is structured into **modular steps**:

- **Step 0: City Selection**  
  - Predefined cities  
  - Upload custom dataset  
  - Auto-fetch (OSM + EE)  

- **Step 1: Parameters**  
  - Select canopy %, roof %, and park increases  

- **Step 2: Costs**  
  - Preprocess costs for interventions  

- **Step 3a: Heatmaps**  
  - Baseline & scenario heat maps  
  - Area metrics in km²  

- **Step 3b: Explainability**  
  - Drivers of UHI (NDVI, slope, buildings)  

- **Step 3c: Costs**  
  - Scenario cost estimation  

- **Step 3d: Policy Game**  
  - Gamified prioritization of interventions  

- **Step 4: Feedback**  
  - Collect stakeholder/user input  

- **Step 5: Results Export**  
  - Export maps, metrics, and PDFs  

---

## 📊 Example (Lisbon)

```python
from ee_auth import init_ee
import geemap.foliumap as geemap
import ee

init_ee()

m = geemap.Map(center=[38.7169, -9.139], zoom=11)

# Example: NDVI from Sentinel-2
aoi = ee.Geometry.Point([-9.139, 38.7169]).buffer(5000)

s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
    .filterBounds(aoi) \
    .filterDate("2023-06-01", "2023-08-31") \
    .map(lambda img: img.normalizedDifference(['B8','B4']).rename('NDVI'))

ndvi = s2.median().clip(aoi)

vis_params = {"min":0, "max":1, "palette":["blue","yellow","green"]}
m.add_layer(ndvi, vis_params, "NDVI Lisbon")
m
```

---

## 📸 Screenshots

_Add screenshots of your app here (e.g., Step 0, Step 3a heatmaps, Step 5 export)._  

---

## ⚠️ Limitations

- UHI modeled via proxy heat index, not actual temperature.  
- Data quality depends on Sentinel-2 cloud masking and OSM completeness.  
- Streamlit Cloud does not support `localtileserver` (EE/folium layers recommended).  

---

## 🔮 Future Directions

- Integrate time-series NDVI and climate projections.  
- Equity-based targeting of greening.  
- Explainable AI (SHAP, GAM) for UHI drivers.  
- Participatory mapping and feedback loops.  

---

## 📄 License

MIT License  

---

## 👥 Contributors

- Muhammad Qasim (khanjiqasim@gmail.com)  

---

## 🙏 Acknowledgements

- **Google Earth Engine**  
- **OpenStreetMap (OSM)**  
- **Copernicus DEM / Sentinel-2**  
- **Streamlit + geemap community**  
