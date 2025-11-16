import json
from typing import List

import pandas as pd
import requests
import streamlit as st
from main import get_combined, combo_batch, BatchRequest


# ============== PAGE CONFIG ==============
st.set_page_config(
    page_title="LA Zoning Explorer",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ LA Parcel & Zoning Explorer")
st.caption("Powered by your Dockerized FastAPI API (Assessor PDB + Z-NET zoning).")
st.markdown("---")


# ============== HELPERS ==============

def call_combo_single(ain: str) -> dict:
    """Call GET /combo/{ain} on the FastAPI service."""
    ain = ain.strip()
    url = f"{API_BASE}/combo/{ain}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def call_combo_batch(ains: List[str]) -> dict:
    """Call POST /combo/batch with a list of AINs."""
    clean = [a.strip() for a in ains if a.strip()]
    url = f"{API_BASE}/combo/batch"
    payload = {"ains": clean}
    r = requests.post(url, json=payload, timeout=40)
    r.raise_for_status()
    return r.json()


def render_single_result(res: dict, show_raw: bool = False) -> None:
    """Pretty UI for one combined parcel+zoning result."""
    parcel = res.get("parcel") or {}
    zoning = res.get("zoning") or {}

    st.subheader(f"AIN {res.get('ain', 'Unknown')}")

    col_left, col_right = st.columns(2)

    # --------- LEFT: Parcel/PDB ---------
    with col_left:
        st.markdown("### 🧱 Parcel / PDB Summary")

        st.write(parcel.get("situs_address", ""))

        st.write(f"**Use type:** {parcel.get('use_type')}")
        st.write(f"**Assessor zoning (PDB):** `{parcel.get('zoning')}`")

        st.write(f"**Sqft (PDB):** {parcel.get('total_sqft_pdb')}")
        years = ", ".join(parcel.get("year_built_list") or [])
        st.write(f"**Year built:** {years or 'N/A'}")

        st.write(
            f"**Units / Beds / Baths:** "
            f"{parcel.get('num_units')} / {parcel.get('beds')} / {parcel.get('baths')}"
        )

        st.write(f"**Land dimensions:** {parcel.get('land_width_depth')}")
        st.write(f"**Quality class:** {parcel.get('quality_class')}")

        # Design types as a small table (if any)
        dtypes = parcel.get("subparts_design_types") or []
        if dtypes:
            st.markdown("**Subpart design types:**")
            st.table(pd.DataFrame(dtypes))

    # --------- RIGHT: Zoning + Map ---------
    with col_right:
        st.markdown("### 🗺️ Z-NET Zoning")

        st.write(f"**Z-NET zone:** `{zoning.get('znet_zone')}`")
        st.write(f"**Zone description:** {zoning.get('znet_zone_description')}")
        st.write(f"**Zone category:** {zoning.get('znet_zone_category')}")
        st.write(f"**Use type:** {zoning.get('use_type')}")

        lat = zoning.get("latitude") or parcel.get("latitude")
        lon = zoning.get("longitude") or parcel.get("longitude")

        if lat is not None and lon is not None:
            st.write(f"**Lat / Lon:** {lat}, {lon}")

            # Map wants 'lat'/'lon' columns
            df_map = pd.DataFrame([{"lat": float(lat), "lon": float(lon)}])
            st.map(df_map, latitude="lat", longitude="lon", zoom=16, use_container_width=True)
        else:
            st.info("No latitude/longitude available for this parcel.")

        title22 = zoning.get("znet_title_22_url")
        if title22:
            st.markdown(
                f"[Open Title 22 reference](https://library.municode.com/ca/"
                f"los_angeles_county/codes/code_of_ordinances?nodeId={title22})"
            )

    # --------- Raw JSON (optional) ---------
    if show_raw:
        st.markdown("#### Raw JSON")
        st.code(json.dumps(res, indent=2), language="json")


# ============== UI LAYOUT ==============

col_main, col_side = st.columns([2, 1])

with col_main:
    mode = st.radio(
        "Mode",
        ["Single AIN", "Batch (multiple AINs)"],
        horizontal=True,
    )

    if mode == "Single AIN":
        ain_input = st.text_input("Enter AIN", placeholder="e.g. 5846022043")
    else:
        ain_text = st.text_area(
            "Enter AINs (comma or newline separated)",
            placeholder="5846022043\n5867001001\n...",
            height=160,
        )

with col_side:
    show_raw_json = st.checkbox("Show raw JSON", value=False)
    run_btn = st.button("Fetch zoning data", type="primary")


st.markdown("---")

# ============== ACTION HANDLER ==============

if run_btn:
    try:
        if mode == "Single AIN":
            if not ain_input.strip():
                st.error("Please enter an AIN.")
            else:
                with st.spinner("Fetching zoning data..."):
                    data = call_combo_single(ain_input)
                render_single_result(data, show_raw=show_raw_json)

        else:
            if not ain_text.strip():
                st.error("Please enter at least one AIN.")
            else:
                # split on newline or comma
                tokens: List[str] = []
                for line in ain_text.replace(",", "\n").splitlines():
                    line = line.strip()
                    if line:
                        tokens.append(line)

                with st.spinner("Fetching batch zoning data..."):
                    batch = call_combo_batch(tokens)

                results = batch.get("results") or []
                if not results:
                    st.warning("No results returned.")
                else:
                    for res in results:
                        if res.get("error"):
                            st.error(f"AIN {res.get('ain')}: {res['error']}")
                        else:
                            render_single_result(res, show_raw=show_raw_json)
                            st.markdown("---")

    except requests.HTTPError as e:
        st.error(f"HTTP error from zoning API: {e}")
    except requests.RequestException as e:
        st.error(f"Network error calling zoning API: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
