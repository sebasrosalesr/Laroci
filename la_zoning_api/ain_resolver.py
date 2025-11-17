# ain_resolver.py
import requests

def resolve_address_to_ain(house_number: str, street_name: str) -> str:
    """Use LA City Open Data to resolve address → AIN"""
    url = "https://data.lacity.org/api/views/3r7r-b5nq/rows.json"
    params = {
        "house_number": house_number,
        "street_name": street_name.replace(" ", "%20")
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        for row in data.get("rows", []):
            if row.get("house_number") == house_number and row.get("street_name", "").upper().startswith(street_name.upper()):
                return row.get("ain")
    except:
        pass
    return None
