import sys
import json
import requests
from typing import Optional, Dict, Any

# Assessor parcel API base
ASSESSOR_BASE_URL = "https://portal.assessor.lacounty.gov"

# Z-NET Planning layer (Layer 4: Zoning)
ZONING_LAYER_URL = (
    "https://arcgis.gis.lacounty.gov/arcgis/rest/services/DRP/ZNET_Public/MapServer/4/query"
)


# -------------------------------
# 1) Assessor parcel API by AIN
# -------------------------------
def fetch_parcel_detail(ain: str) -> Dict[str, Any]:
    """
    Fetch parcel detail JSON from LA County Assessor by AIN.
    """
    url = f"{ASSESSOR_BASE_URL}/api/parceldetail"
    params = {"ain": ain}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


# -------------------------------
# 2) Z-NET zoning by lat/lon
# -------------------------------
def fetch_zoning(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Query Z-NET for zoning using WGS84 coordinates.
    Returns dict with zone, description, category, Title 22 link.
    """
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",  # x,y = lon,lat
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE,Z_DESC,Z_CATEGORY,TITLE_22",
        "returnGeometry": "false",
    }

    r = requests.get(ZONING_LAYER_URL, params=params)
    r.raise_for_status()
    data = r.json()

    features = data.get("features", [])
    if not features:
        return None

    attrs = features[0].get("attributes", {})

    return {
        "zone": attrs.get("ZONE"),
        "zone_description": attrs.get("Z_DESC"),
        "zone_category": attrs.get("Z_CATEGORY"),
        "title_22_url": attrs.get("TITLE_22"),
    }


# -------------------------------
# 3) Convenience: zoning by AIN
# -------------------------------
def fetch_zoning_by_ain(ain: str) -> Dict[str, Any]:
    """
    High-level helper:
      AIN -> Assessor API (lat/lon, address, PDB code)
          -> Z-NET zoning
          -> combined summary dict
    """
    raw = fetch_parcel_detail(ain)
    parcel = raw.get("Parcel", {})

    lat = parcel.get("Latitude")
    lon = parcel.get("Longitude")
    if lat is None or lon is None:
        raise ValueError("Parcel record does not contain Latitude/Longitude.")

    # Address / basic info
    situs_street = (parcel.get("SitusStreet") or "").strip()
    situs_city = (parcel.get("SitusCity") or "").strip()
    situs_zip = (parcel.get("SitusZipCode") or "").strip()
    situs_address = ", ".join(
        [p for p in [situs_street, situs_city, situs_zip] if p]
    )

    zoning_info = fetch_zoning(lat, lon)

    result: Dict[str, Any] = {
        "ain": parcel.get("AIN") or ain,
        "situs_address": situs_address,
        "latitude": lat,
        "longitude": lon,
        "use_type": parcel.get("UseType"),
        "assessor_zoning_pdb": parcel.get("ZoningPDB"),
    }

    if zoning_info:
        result.update(
            {
                "znet_zone": zoning_info.get("zone"),
                "znet_zone_description": zoning_info.get("zone_description"),
                "znet_zone_category": zoning_info.get("zone_category"),
                "znet_title_22_url": zoning_info.get("title_22_url"),
            }
        )
    else:
        result.update(
            {
                "znet_zone": None,
                "znet_zone_description": None,
                "znet_zone_category": None,
                "znet_title_22_url": None,
            }
        )

    return result


# -------------------------------
# 4) CLI entrypoint
# -------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper_zoning.py <AIN>")
        print("Example: python scraper_zoning.py 5846022043")
        sys.exit(1)

    ain = sys.argv[1].strip()
    data = fetch_zoning_by_ain(ain)

    print("=== ZONING BY AIN ===")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
