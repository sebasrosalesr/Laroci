# app.py
import json
import pandas as pd
import streamlit as st
from main import get_combined, combo_batch, BatchRequest
from zimas_scraper import scrape_zimas_ultra
from ain_resolver import resolve_address_to_ain
import asyncio
from typing import List, Dict

# ============== PAGE CONFIG ==============
st.set_page_config(page_title="LA Zoning Explorer Pro", page_icon="🏗️", layout="wide")
st.title("🏗️ LA Zoning Explorer Pro")
st.caption("AIN → Parcel + Z-NET | **Address → AIN → ZIMAS**")
st.markdown("---")

# ============== HELPERS ==============
def call_combo_single(ain: str) -> dict:
    return get_combined(ain.strip())

def call_combo_batch(ains: List[str]) -> dict:
    clean = [a.strip() for a in ains if a.strip()]
    return combo_batch(BatchRequest(ains=clean))

async def run_zimas_async(house: str, street: str) -> Dict:
    return await scrape_zimas_ultra(house, street, headless=True)

def render_single_result(res: dict, zimas_data: dict = None, show_raw: bool = False):
    parcel = res.get("parcel") or {}
    zoning = res.get("zoning") or {}
    ain = res.get("ain", "Unknown")
    
    st.subheader(f"AIN: `{ain}`")
    col1, col2 = st.columns([1, 1])

    # LEFT: Parcel + ZIMAS
    with col1:
        st.markdown("### 🧱 Parcel + ZIMAS")
        st.write(parcel.get("situs_address", "N/A"))
        st.write(f"**Use type:** {parcel.get('use_type')}")
        st.write(f"**PDB Zoning:** `{parcel.get('zoning')}`")
        st.write(f"**Z-NET Zone:** `{zoning.get('znet_zone')}`")
        st.write(f"**ZIMAS Land Use:** `{zimas_data.get('Overlay_Zones_Data', {}).get('General_Plan_Land_Use', 'N/A')}`")
        st.write(f"**Specific Plan:** `{zimas_data.get('Overlay_Zones_Data', {}).get('Specific_Plan', 'N/A')}`")
        st.write(f"**Transit Corridor:** `{zimas_data.get('Overlay_Zones_Data', {}).get('High_Quality_Transit_Corridor_within_half_mile', 'N/A')}`")

    # RIGHT: Map + Links
    with col2:
        st.markdown("### 🗺️ Location")
        lat = zoning.get("latitude") or parcel.get("latitude")
        lon = zoning.get("longitude") or parcel.get("longitude")
        if lat and lon:
            df_map = pd.DataFrame([{"lat": float(lat), "lon": float(lon)}])
            st.map(df_map, latitude="lat", longitude="lon", zoom=16)
        title22 = zoning.get("znet_title_22_url")
        if title22:
            st.markdown(f"[Title 22](https://library.municode.com/ca/los_angeles_county/codes/code_of_ordinances?nodeId={title22})")

    if show_raw:
        col_raw1, col_raw2 = st.columns(2)
        with col_raw1:
            st.markdown("#### Raw Parcel+Zoning")
            st.code(json.dumps(res, indent=2), language="json")
        with col_raw2:
            st.markdown("#### Raw ZIMAS")
            st.code(json.dumps(zimas_data, indent=2), language="json")

# ============== UI ==============
col_mode, col_options = st.columns([2, 1])

with col_mode:
    mode = st.radio("Input Mode", ["AIN", "Address"], horizontal=True)

with col_options:
    show_raw = st.checkbox("Show raw JSON")
    export_csv = st.button("Export All to CSV", type="secondary")

# Input fields
if mode == "AIN":
    ain_input = st.text_input("Enter AIN", placeholder="5846022043")
else:
    col_addr1, col_addr2 = st.columns(2)
    with col_addr1:
        house = st.text_input("House Number", placeholder="1617")
    with col_addr2:
        street = st.text_input("Street Name", placeholder="Cosmo")

run_btn = st.button("Run Analysis", type="primary")

# ============== RUN ==============
if run_btn:
    try:
        if mode == "AIN":
            if not ain_input.strip():
                st.error("Enter AIN")
            else:
                with st.spinner("Fetching parcel + zoning..."):
                    data = call_combo_single(ain_input)
                with st.spinner("Running ZIMAS..."):
                    zimas_data = asyncio.run(run_zimas_async("1617", "Cosmo"))  # placeholder
                    # Actually use resolved AIN → but we need AIN → address reverse...
                    # We'll fix this in v2 with reverse lookup
                render_single_result(data, zimas_data={}, show_raw=show_raw)

        else:  # Address Mode
            if not house.strip() or not street.strip():
                st.error("Enter full address")
            else:
                with st.spinner("Resolving address → AIN..."):
                    ain = resolve_address_to_ain(house, street)
                if not ain:
                    st.error("Address not found in LA Assessor database.")
                else:
                    st.success(f"AIN Found: `{ain}`")
                    with st.spinner("Fetching parcel + zoning..."):
                        data = call_combo_single(ain)
                    with st.spinner("Scraping ZIMAS..."):
                        zimas_data = asyncio.run(run_zimas_async(house, street))
                    render_single_result(data, zimas_data, show_raw=show_raw)

    except Exception as e:
        st.error(f"Error: {e}")
