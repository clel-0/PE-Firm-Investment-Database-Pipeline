from playwright.sync_api import sync_playwright
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

# used to create unique jsonl filename for data logging
date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# create unique jsonl output file path
OUTPUT_DIR = Path(f"logs/aic_responses_{date_time}.jsonl")
OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)

aic_url = "https://investmentcouncil.com.au/site/Shared_Content/Smart-Suite/Smart-Maps/Public/Member-Directory-Search.aspx"

# --- robust map locator finder (sync playwright) ---
from typing import Optional
from playwright.sync_api import Page, Locator

MAP_SELECTORS = [
    '[role="region"][aria-label="Map"]',
    'div[aria-roledescription="map"]',
    'div[aria-label="Map"]',
    'div[role="application"][aria-label*="Map"]',
    # fallbacks seen on some Google Maps embeds:
    'div[class*="gm-style"]',
    'div[id^="map"], div[class^="map"]',
]

def find_map_locator(page: Page, timeout_ms: int = 10000) -> Locator:
    # 1) Handle cookie/consent overlays if present (non-fatal if not found)
    for sel in ['button:has-text("Accept")',
                'button:has-text("I agree")',
                'button:has-text("Got it")',
                '[aria-label*="accept"]',
                '[data-testid="cookie"] button']:
        try:
            page.locator(sel).first.click(timeout=1500)
        except Exception:
            pass

    # 2) Wait for page to settle a bit
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass

    # 3) Try on main page first
    for sel in MAP_SELECTORS:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=2000)
            # ensure on-screen or bounding_box() returns None
            try:
                loc.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            if loc.bounding_box() is not None:
                return loc
        except Exception:
            continue

    # 4) Try inside iframes
    for frame in page.frames:
        if frame is page.main_frame:
            continue
        for sel in MAP_SELECTORS:
            loc = frame.locator(sel).first
            try:
                loc.wait_for(state="visible", timeout=2000)
                try:
                    loc.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                if loc.bounding_box() is not None:
                    return loc
            except Exception:
                continue

    # 5) Last resort: use viewport center as a “map click” fallback
    vp = page.viewport_size or {"width": 1280, "height": 720}
    page.mouse.click(vp["width"]//2, vp["height"]//2)
    # retry main selectors once more
    for sel in MAP_SELECTORS:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=1500)
            if loc.bounding_box() is not None:
                return loc
        except Exception:
            continue

    raise Exception("Could not find map locator on page or in iframes.")

def response_handler(r):
    # Only process network types that can carry JSON
    if r.request.resource_type not in ("xhr", "fetch"):
        return

    url = r.url
    ctype = r.headers.get("content-type", "")
    print(f"[RESP] {r.request.resource_type} {r.status} {ctype} {url}")

    #ignore Google tile noise requests
    if "maps.googleapis.com" in url:
        return

    # Only process AIC URLs
    if "investmentcouncil.com.au" not in url:
        return

    # Only try JSON when likely JSON
    if "json" not in ctype.lower():
        return

    # Parse JSON, safely
    try:
        data = r.json()
    except Exception as e:
        print("[RESP] JSON parse failed:", e)
        return

    # Payload-shape detection (no fragile indexing)
    vals = None
    if isinstance(data, dict):
        items = data.get("Items")
        if isinstance(items, dict):
            vals = items.get("$values")

    if not (isinstance(vals, list) and any(isinstance(x, dict) for x in vals)):
        # Not the members payload shape
        return

    # Good — log it
    record = {
        "datetime": datetime.now().isoformat(),
        "url": url,
        "status": r.status,
        "headers": dict(r.headers),
        "JSON": data,
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(OUTPUT_DIR, "a", encoding="utf-8") as f:
        f.write(line)
    print("[RESP] Logged AIC payload:", url)





def map_sweep(page : playwright.sync_api.Page):
    """Performs a systematic sweep of the map interface on the AIC member directory page to trigger loading of all member data via simulated mouse and keyboard actions."""
    loc = find_map_locator(page)          # <— robust finder
    box = loc.bounding_box()
    if not box:
        # ensure on screen and try again once
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        box = loc.bounding_box()
    if not box:
        raise RuntimeError("Map element is not visible (no bounding box).")
    
    # Calculate map dimensions and center
    map_width = box['width']
    map_height = box['height']
    cx = box['x'] + map_width/2
    cy = box['y'] + map_height/2
    
    # Calculate initial position (⅓ up and left from center)
    dx = map_width/2  # Half map width for horizontal movement
    dy = map_height/2  # Half map height for vertical movement
    start_x = cx - map_width/3
    start_y = cy - map_height/3
    
    # Buffer to ensure map interface recognizes mouse
    e = 5  # pixels

    page.wait_for_timeout(10000)
    
    # click on map to focus
    page.mouse.move(cx, cy)
    page.mouse.click(cx, cy)

    # Move to starting position
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(cx, cy)
    page.mouse.up()
    
    print("Map focused and starting position set.")
    print("zooming in...")
    # Zoom in 5 times
    for _ in range(5):
        page.keyboard.press("Shift+=")
        page.wait_for_timeout(500)  # Wait for zoom animation (0.5 seconds)
    
    # Calculate target distances (4/6 of total map size * 32 due to zoom)
    target_horizontal = (4/6) * 32 * map_width
    target_vertical = (4/6) * 32 * map_height
    
    total_horizontal = 0
    total_vertical = 0
    direction = 1  # 1 for right, -1 for left
    
    # Main sweeping loop
    while total_vertical < target_vertical:
        # Move horizontally across the map
        
        print(f"Starting horizontal sweep at vertical position: {total_vertical}/{target_vertical}")
        while total_horizontal < target_horizontal:
            # Move right to left
            page.mouse.move(cx + direction*(dx - e), cy)
            page.wait_for_timeout(1000)
            page.mouse.down()
            page.mouse.move(cx - direction*(dx - e), cy)
            page.wait_for_timeout(1000)
            page.mouse.up()

            total_horizontal += dx * 2  # Full horizontal sweep
        
        overrreach = total_horizontal - target_horizontal
        # Adjust for any overrreach
        adjust_x = direction * overrreach
        if adjust_x != 0:
            for i in range(2):
                page.mouse.move(cx - adjust_x/2, cy)
                page.wait_for_timeout(1000)
                page.mouse.down()
                page.mouse.move(cx, cy)
                page.wait_for_timeout(1000)
                page.mouse.up()

        # Move down vertically
        page.mouse.move(cx, cy + dy - e)
        page.wait_for_timeout(1000)
        page.mouse.down()
        page.mouse.move(cx, cy - dy + e)
        page.wait_for_timeout(1000) 
        page.mouse.up()

        total_vertical += dy * 2  # Full vertical sweep
        total_horizontal = 0  # Reset horizontal distance for next row
        
        # Reverse direction for serpentine pattern
        direction *= -1
    
    print("Map sweep completed.")
        



def open_aic_page(url = aic_url):
    """Opens the AIC member directory page and performs a map sweep to trigger loading of all member data."""
    try:
        with sync_playwright() as p:
            # Launch browser with clean context
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                ignore_https_errors=True,
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # Clear storage before starting
            page.context.clear_cookies()

            # Attach the response handler to log relevant responses
            page.on("response", response_handler)

            # Navigate to the AIC members page
            page.goto(url)

            map_sweep(page)

            # Wait for some time to ensure all requests are captured
            page.wait_for_timeout(10000)



            browser.close()
    except Exception as e:
        print(f"Error occurred while processing AIC page: {e}")




def extract_PE_firms(PATH: Path = OUTPUT_DIR) -> list[dict]:
    """Extracts and returns a list of private equity firms based in Australia from the logged AIC member data JSONL file."""
    seenFirms = set()
    firms = []

    # Open the logged JSONL file
    with PATH.open("r", encoding="utf-8") as f:
        for i,line in enumerate(f):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON line {i}")
                continue
            
            data  = record.get("JSON", record)

            #check for specific structure in the json data to match AIC member data
            if len(data["Items"]["$values"]) > 0:
                keyIdentifier = "FullName" in data["Items"]["$values"][0] and "FullName" in data["Items"]["$values"][0]
            else:
                keyIdentifier = False

            if isinstance(data, dict):
                if data["Items"]:
                    if data["Items"]["$values"] and keyIdentifier:
                        for firm in data["Items"]["$values"]:
                            # Filter for PE firms in Australia
                            if firm["filter-Member Type"] in {"PE", "private equity"} and "Australia" in firm["LongLatAddress"] and firm["FullName"] not in seenFirms:
                                firms.append(firm)
                                seenFirms.add(firm["FullName"])
                                print(f"Line {i} in {PATH.name} contains the info corresponding to {firm['FullName']}")

                            else:
                                print(f"Line {i} in {PATH.name} does not correspond to a PE firm in Australia.")

                    else:
                        print(f"Line {i} in {PATH.name} does not contain expected member data structure.")

                else:
                    print(f"Line {i} in {PATH.name} does not contain expected member data structure.")


                                
    return firms  




def export_PE_firms(firms: list[dict], main_export_path: Path = Path("output/PE_firms.csv")):
    """Exports the list of private equity firms to a CSV file at the specified path."""
    df = pd.DataFrame(firms)
    original_columns = ["FullName", "Website"]
    detailed_columns = ["FullName", "Website", "Phone", "Email", "Latitude", "Longitude", "LongLatAddress"]

    df_OG = df[original_columns]
    df_detailed = df[detailed_columns]

    df_OG.to_csv(main_export_path, index=False)
    df_detailed.to_csv("output/detailed_PE.csv", index=False)



if __name__ == "__main__":
    print("Starting AIC PE firm seeding process...")
    open_aic_page()
    print("AIC page processing completed. Extracting PE firms...")
    pe_firms = extract_PE_firms()
    print(f"Extracted {len(pe_firms)} PE firms from AIC data. Exporting to CSV...")
    export_PE_firms(pe_firms)
    print("PE firm data export completed.")