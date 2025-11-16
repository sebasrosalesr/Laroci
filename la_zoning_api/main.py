from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests

import scraper_zoning
import scraper_pdb


app = FastAPI(
    title="LA Parcel & Zoning API",
    description="FastAPI wrapper around Assessor PDB + Z-NET zoning scrapers.",
    version="0.1.0",
)

# ---------- Pydantic models ----------

class ParcelSummary(BaseModel):
    ain: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    situs_address: Optional[str] = None
    use_type: Optional[str] = None
    zoning: Optional[str] = None
    legal_description: Optional[str] = None
    quality_class: Optional[str] = None
    total_sqft_pdb: Optional[int] = None
    land_width_depth: Optional[str] = None
    year_built_list: List[str] = []
    num_units: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    subparts_design_types: List[Dict[str, Any]] = []


class ZoningSummary(BaseModel):
    ain: str
    situs_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    use_type: Optional[str] = None
    assessor_zoning_pdb: Optional[str] = None
    znet_zone: Optional[str] = None
    znet_zone_description: Optional[str] = None
    znet_zone_category: Optional[str] = None
    znet_title_22_url: Optional[str] = None


class CombinedResponse(BaseModel):
    ain: str
    parcel: ParcelSummary
    zoning: ZoningSummary


class BatchRequest(BaseModel):
    ains: List[str]


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/parcel/{ain}", response_model=ParcelSummary)
def get_parcel_summary(ain: str):
    """
    Returns the PDB / assessor summary (build_summary from scraper_pdb).
    """
    try:
        raw = scraper_pdb.fetch_parcel_detail(ain)
        summary = scraper_pdb.build_summary(raw)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Assessor API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not summary:
        raise HTTPException(status_code=404, detail="No parcel data found for this AIN.")
    return summary


@app.get("/zoning/{ain}", response_model=ZoningSummary)
def get_zoning_summary(ain: str):
    """
    Returns assessor + Z-NET zoning info (fetch_zoning_by_ain from scraper_zoning).
    """
    try:
        data = scraper_zoning.fetch_zoning_by_ain(ain)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"HTTP error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not data:
        raise HTTPException(status_code=404, detail="No zoning data found for this AIN.")
    return data


@app.get("/combo/{ain}", response_model=CombinedResponse)
def get_combined(ain: str):
    """
    Full combined view: PDB summary + Z-NET zoning in one call.
    """
    parcel = get_parcel_summary(ain)
    zoning = get_zoning_summary(ain)

    return {
        "ain": ain,
        "parcel": parcel,
        "zoning": zoning,
    }


@app.post("/combo/batch")
def combo_batch(request: BatchRequest) -> Dict[str, Any]:
    """
    Batch combined view: send multiple AINs and get parcel+zoning for each.
    Returns a list of results; if one fails, we include an error field.
    """
    results = []
    for ain in request.ains:
        try:
            parcel = get_parcel_summary(ain)
            zoning = get_zoning_summary(ain)
            results.append({
                "ain": ain,
                "parcel": parcel,
                "zoning": zoning,
            })
        except Exception as e:
            results.append({
                "ain": ain,
                "parcel": None,
                "zoning": None,
                "error": str(e),
            })

    return {"results": results}
