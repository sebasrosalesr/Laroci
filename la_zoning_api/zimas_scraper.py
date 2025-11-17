# zimas_scraper.py
# Author: Sebastian Rosales
# Portfolio: https://github.com/yourusername/zimas-ultra-pro
# Description: Blazing-fast, headless, CSV-exporting ZIMAS scraper.
#              Zero screenshots. Zero retries. Zero Reddit vibes.

import json
import re
import asyncio
import csv
from typing import Dict
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page

ZIMAS_URL = "https://zimas.lacity.org/"

# ----------------------------------------------------------------------
# Ultra-Clean Helpers
# ----------------------------------------------------------------------
def clean_street_name(name: str) -> str:
    suffixes = [" st", " street", " ave", " avenue", " blvd", " boulevard",
                " dr", " drive", " rd", " road", " pl", " place", " ln", " lane",
                " way", " ct", " court", " cir", " circle", " ter", " terrace"]
    n = name.lower().strip()
    for s in suffixes:
        if n.endswith(s):
            n = n[: -len(s)]
            break
    return n.strip().title()

def _normalize_label(label: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", re.sub(r"[()/]", " ", " ".join(label.split()))).strip("_")

# ----------------------------------------------------------------------
# Tab Intelligence
# ----------------------------------------------------------------------
SECTIONS = [
    {"tab_text": "Jurisdictional", "keywords": ["Community Plan Area", "Council District"]},
    {"tab_text": "Planning and Zoning", "keywords": ["Zoning", "General Plan Land Use"]},
    {"tab_text": "Additional", "keywords": ["Airport Hazard", "Very High Fire Hazard"]},
    {"tab_text": "Environmental", "keywords": ["Santa Monica Mountains", "Biological Resource"]},
    {"tab_text": "Seismic Hazards", "keywords": ["Nearest Fault", "Slip Rate"]},
]

# ----------------------------------------------------------------------
# Silent Terms Handler
# ----------------------------------------------------------------------
async def handle_terms_popup(page: Page):
    selectors = ["input[value*='Accept' i]", "button:has-text('Accept')", "input[type='button']:has-text('Accept')"]
    for sel in selectors:
        try:
            btn = page.locator(sel)
            if await btn.is_visible(timeout=2000):
                try: await page.locator("#ckDoNotShow, input[type='checkbox']").check(timeout=1000)
                except: pass
                await btn.click()
                return
        except: pass
    await page.evaluate("""() => {
        const cb = document.getElementById('ckDoNotShow') || document.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = true;
        const btn = Array.from(document.querySelectorAll('input, button'))
            .find(el => /accept/i.test(el.value || el.textContent));
        if (btn) btn.click();
    }""")

# ----------------------------------------------------------------------
# Core Engine: GPU-Friendly, Headless-Optimized
# ----------------------------------------------------------------------
async def scrape_zimas_ultra(
    house_number: str,
    street_name: str,
    headless: bool = True,
    slow_mo: int = 0,
) -> Dict:
    result = {
        "Overlay_Zones_Data": {},
        "_debug": {
            "house_number": house_number,
            "street_name_input": street_name,
            "street_name_clean": clean_street_name(street_name),
        },
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=["--disable-gpu", "--no-sandbox", "--disable-setuid-sandbox"]  # GPU-friendly
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = await context.new_page()

        try:
            await page.goto(ZIMAS_URL, wait_until="domcontentloaded", timeout=60000)
            await handle_terms_popup(page)

            await page.fill("input[title*='House' i], input[id*='House' i]", house_number.strip())
            await page.fill("input[title*='Street' i], input[id*='Street' i]", clean_street_name(street_name))
            await page.click("#btnSearchGo")
            await asyncio.sleep(5)

            # Auto-select first result
            try:
                link = page.locator("table td a").first
                if await link.is_visible(timeout=3000):
                    await link.click()
                    await asyncio.sleep(3)
            except: pass

            # Intelligent tab scraping
            for sec in SECTIONS:
                tab_text = sec["tab_text"]
                keywords = [k.upper() for k in sec["keywords"]]
                sec_id = tab_text.replace(" ", "_")

                tab = None
                candidates = await page.locator(f"button:has-text('{tab_text}'), a:has-text('{tab_text}'), span:has-text('{tab_text}')").all()
                for c in candidates:
                    if tab_text.lower() in (await c.inner_text()).lower():
                        tab = c
                        break
                if not tab:
                    tab = page.locator(f"*:has-text('{tab_text}')").first

                if not await tab.is_visible(timeout=5000):
                    result["Overlay_Zones_Data"][sec_id] = {}
                    continue

                await tab.click()
                await asyncio.sleep(2)

                frame = page.main_frame
                for f in page.frames:
                    try:
                        body = await f.locator("body").inner_text(timeout=2000)
                        if any(k in body.upper() for k in keywords):
                            frame = f
                            break
                    except: continue

                data = {}
                counts = defaultdict(int)
                rows = await frame.locator("tr").all()
                for row in rows:
                    cells = await row.locator("th, td").all()
                    if len(cells) < 2: continue
                    label = (await cells[0].inner_text()).strip()
                    value = (await cells[1].inner_text()).strip()
                    if not label or not value: continue
                    key = _normalize_label(label)
                    counts[key] += 1
                    final_key = f"{key}_{counts[key]}" if counts[key] > 1 else key
                    data[final_key] = value

                result["Overlay_Zones_Data"][sec_id] = data

            # === ULTRA CLEAN OUTPUT ===
            clean_data = {
                "General_Plan_Land_Use": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("General_Plan_Land_Use", "Not found"),
                "Occupancy": "Not listed in ZIMAS",
                "Community_Plan_Area": result["Overlay_Zones_Data"].get("Jurisdictional", {}).get("Community_Plan_Area", "Not found"),
                "Liquefaction_Zone": result["Overlay_Zones_Data"].get("Seismic_Hazards", {}).get("Liquefaction", "Not found"),
                "Flood_Zone": result["Overlay_Zones_Data"].get("Additional", {}).get("Flood_Zone", "Not found"),
                "Specific_Plan": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("Specific_Plan_Area", "Not found"),
                "High_Quality_Transit_Corridor_within_half_mile": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("High_Quality_Transit_Corridor_within_1_2_mile", "Not found"),
                "California_Building_Codes": "Not listed in ZIMAS",
                "Alquist_Priolo_Fault_Zone": result["Overlay_Zones_Data"].get("Seismic_Hazards", {}).get("Alquist_Priolo_Fault_Zone", "Not found"),
                "Hillside_Area_Zoning_Code": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("Hillside_Area_Zoning_Code", "Not found"),
                "Special_Land_Use_or_Zoning": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("Special_Land_Use_Zoning", "Not found"),
                "Historic_Preservation_Review": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("Historic_Preservation_Review", "Not found"),
                "HistoricPlacesLA": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("HistoricPlacesLA", "Not found"),
                "CDO_Community_Design_Overlay": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("CDO_Community_Design_Overlay", "Not found"),
                "RFA_Residential_Floor_Area_District": result["Overlay_Zones_Data"].get("Planning_and_Zoning", {}).get("RFA_Residential_Floor_Area_District", "Not found"),
                "Airport_Hazard": result["Overlay_Zones_Data"].get("Additional", {}).get("Airport_Hazard", "Not found"),
                "Coastal_Zone": result["Overlay_Zones_Data"].get("Additional", {}).get("Coastal_Zone", "Not found"),
                "Very_High_Fire_Hazard_Severity_Zone": result["Overlay_Zones_Data"].get("Additional", {}).get("Very_High_Fire_Hazard_Severity_Zone", "Not found"),
                "Special_Grading_Area": result["Overlay_Zones_Data"].get("Additional", {}).get("Special_Grading_Area_BOE_Basic_Grid_Map_A_13372", "Not found"),
                "Wildland_Urban_Interface_WUI": result["Overlay_Zones_Data"].get("Environmental", {}).get("Wildland_Urban_Interface_WUI", "Not found"),
            }

            final_result = {
                "Overlay_Zones_Data": clean_data,
                "_debug": result["_debug"]
            }

            # === AUTO CSV EXPORT ===
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"zimas_{house_number}_{clean_street_name(street_name)}_{timestamp}.csv"
            Path("csv_output").mkdir(exist_ok=True)
            csv_path = Path("csv_output") / filename

            row = {"House_Number": house_number, "Street_Name": street_name, **clean_data}
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                writer.writeheader()
                writer.writerow(row)

            await browser.close()
            return final_result

        except Exception as e:
            await browser.close()
            return {"_error": str(e), "_debug": result["_debug"]}

# ----------------------------------------------------------------------
# CLI: Portfolio-Ready
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ZIMAS Ultra Pro Scraper — GPU-friendly, production-grade")
    parser.add_argument("house_number", help="House number")
    parser.add_argument("street_name", help="Street name (e.g., Cosmo)")
    parser.add_argument("--visible", action="store_true", help="Run in visible mode")
    parser.add_argument("--slow", type=int, default=0, help="Slow motion delay")
    args = parser.parse_args()

    data = asyncio.run(scrape_zimas_ultra(
        args.house_number,
        args.street_name,
        headless=not args.visible,
        slow_mo=args.slow,
    ))
    print(json.dumps(data, indent=2))
