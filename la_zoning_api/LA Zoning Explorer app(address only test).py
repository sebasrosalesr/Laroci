# app.py
import streamlit as st
import asyncio
import json
import pandas as pd
from zimas_scraper import scrape_zimas_ultra
from ain_resolver import resolve_address_to_ain  # Optional
from main import get_combined  # Optional: your AIN API

st.set_page_config(page_title="LA Zoning Explorer", page_icon="Zoning", layout="wide")
st.title("LA Zoning Explorer")
st.caption("Enter **address only** → Get **ZIMAS + Parcel + Z-NET** instantly")

# ============== INPUT ==============
col1, col2 = st.columns(2)
with col1:
    house = st.text_input("House Number", placeholder="1617")
with col2:
    street = st.text_input("Street Name", placeholder="Cosmo")

show_raw = st.checkbox("Show raw JSON")
run_btn = st.button("Get Zoning Data", type="primary")

# ============== RUN ==============
if run_btn:
    if not house.strip() or not street.strip():
        st.error("Please enter both house number and street name.")
    else:
        with st.spinner("Scraping ZIMAS..."):
            zimas_data = asyncio.run(scrape_zimas_ultra(house, street, headless=True))

        # Optional: Try to get AIN → enrich with your API
        ain = None
        parcel_data = {}
        with st.spinner("Looking up AIN (optional)..."):
            ain = resolve_address_to_ain(house, street)
            if ain:
                try:
                    parcel_data = get_combined(ain)  # Your existing API
                except:
                    parcel_data = {}

        # ============== DISPLAY ==============
        st.success("ZIMAS Data Retrieved!")
        col_zimas, col_parcel = st.columns([1, 1])

        with col_zimas:
            st.markdown("### ZIMAS Zoning (Address-Based)")
            z = zimas_data.get("Overlay_Zones_Data", {})
            st.write(f"**General Plan Land Use:** `{z.get('General_Plan_Land_Use', 'N/A')}`")
            st.write(f"**Community Plan Area:** `{z.get('Community_Plan_Area', 'N/A')}`")
            st.write(f"**Specific Plan:** `{z.get('Specific_Plan', 'N/A')}`")
            st.write(f"**Transit Corridor (½ mi):** `{z.get('High_Quality_Transit_Corridor_within_half_mile', 'N/A')}`")
            st.write(f"**Liquefaction Zone:** `{z.get('Liquefaction_Zone', 'N/A')}`")
            st.write(f"**Flood Zone:** `{z.get('Flood_Zone', 'N/A')}`")
            st.write(f"**Fire Hazard Zone:** `{z.get('Very_High_Fire_Hazard_Severity_Zone', 'N/A')}`")

            if show_raw:
                st.code(json.dumps(zimas_data, indent=2), language="json")

        with col_parcel:
            if ain and parcel_data:
                st.markdown("### Parcel + Z-NET (AIN-Based)")
                p = parcel_data.get("parcel", {})
                zn = parcel_data.get("zoning", {})
                st.write(f"**AIN:** `{ain}`")
                st.write(f"**Address:** {p.get('situs_address', 'N/A')}")
                st.write(f"**Z-NET Zone:** `{zn.get('znet_zone', 'N/A')}`")
                st.write(f"**Use Type:** {p.get('use_type', 'N/A')}")
                st.write(f"**Units:** {p.get('num_units', 'N/A')}")
                lat = zn.get("latitude") or p.get("latitude")
                lon = zn.get("longitude") or p.get("longitude")
                if lat and lon:
                    df_map = pd.DataFrame([{"lat": float(lat), "lon": float(lon)}])
                    st.map(df_map, zoom=16)
            else:
                st.info("AIN not found or API unavailable — ZIMAS data still valid.")

        # ============== CSV EXPORT ==============
        export_data = {
            "House_Number": house,
            "Street_Name": street,
            "AIN": ain or "Not found",
            **zimas_data.get("Overlay_Zones_Data", {})
        }
        df = pd.DataFrame([export_data])
        csv = df.to_csv(index=False).encode()
        st.download_button(
            "Download CSV",
            csv,
            f"zimas_{house}_{street.replace(' ', '_')}.csv",
            "text/csv"
        )
