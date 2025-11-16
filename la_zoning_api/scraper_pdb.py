import sys
import json
import requests

BASE_URL = "https://portal.assessor.lacounty.gov"


# -------------------------------
# Fetch raw API JSON
# -------------------------------
def fetch_parcel_detail(ain: str) -> dict:
    url = f"{BASE_URL}/api/parceldetail"
    params = {"ain": ain}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


# -------------------------------
# Build the PDB summary you need
# -------------------------------
def build_summary(raw: dict) -> dict:
    p = raw.get("Parcel", {})
    subparts = p.get("SubParts", []) or []

    # -----------------------
    # Address
    # -----------------------
    situs_parts = [
        (p.get("SitusStreet") or "").strip(),
        (p.get("SitusCity") or "").strip(),
        (p.get("SitusZipCode") or "").strip()
    ]
    situs_address = ", ".join([s for s in situs_parts if s])

    # -----------------------
    # SubParts aggregation
    # -----------------------
    total_sqft_pdb = 0
    year_built_set = set()
    total_units = 0
    total_beds = 0
    total_baths = 0
    design_types = []

    for sp in subparts:
        # SqFt
        try:
            sqft = int(str(sp.get("SqftMain", "0")).strip() or "0")
        except ValueError:
            sqft = 0
        total_sqft_pdb += sqft

        # Year built
        yb = (sp.get("YearBuilt") or "").strip()
        if yb:
            year_built_set.add(yb)

        # Units / beds / baths
        try:
            total_units += int(str(sp.get("NumOfUnits", "0")).strip() or "0")
        except:
            pass
        try:
            total_beds += int(str(sp.get("NumOfBeds", "0")).strip() or "0")
        except:
            pass
        try:
            total_baths += int(str(sp.get("NumOfBaths", "0")).strip() or "0")
        except:
            pass

        # Design type dictionary
        design_types.append({
            "design_type": sp.get("DesignType"),
            "d1": sp.get("DesignType1stDigit"),
            "d2": sp.get("DesignType2ndDigit"),
            "d3": sp.get("DesignType3rdDigit"),
            "d4": sp.get("DesignType4thDigit"),
        })

    # Fallbacks if no subparts
    if not subparts:
        total_sqft_pdb = p.get("SqftMain") or 0
        total_units = p.get("NumOfUnits") or 0
        total_beds = p.get("NumOfBeds") or 0
        total_baths = p.get("NumOfBaths") or 0
        if p.get("YearBuilt"):
            year_built_set.add(p.get("YearBuilt"))

    # Normalize year built
    year_built_list = sorted(list(year_built_set)) if year_built_set else []

    # -----------------------
    # Land W x D
    # -----------------------
    land_width = p.get("LandWidth")
    land_depth = p.get("LandDepth")
    land_dimensions = f"{land_width}' x {land_depth}'" if land_width and land_depth else None

    # -----------------------
    # Final summary dict
    # -----------------------
    summary = {
        "ain": p.get("AIN"),
        "latitude": p.get("Latitude"),
        "longitude": p.get("Longitude"),
        "situs_address": situs_address,
        "use_type": p.get("UseType"),       # Single Family Residence
        "zoning": p.get("ZoningPDB"),       # LCR175
        "legal_description": p.get("LegalDescription"),
        "quality_class": p.get("QualityClass"),

        # Aggregated SubParts values
        "total_sqft_pdb": total_sqft_pdb,
        "land_width_depth": land_dimensions,
        "year_built_list": year_built_list,
        "num_units": total_units,
        "beds": total_beds,
        "baths": total_baths,

        # Design types for all subparts
        "subparts_design_types": design_types
    }

    return summary


# -------------------------------
# Main runner
# -------------------------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <AIN>")
        sys.exit(1)

    ain = sys.argv[1].strip()
    raw = fetch_parcel_detail(ain)

    print("=== RAW JSON ===")
    print(json.dumps(raw, indent=2))

    summary = build_summary(raw)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
