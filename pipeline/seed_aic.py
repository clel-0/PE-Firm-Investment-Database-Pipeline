from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests

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
    """Attempts to robustly find the map locator on the given Playwright page, including within iframes.
    If found, returns the Locator object; otherwise raises an exception.
    """

    # 1) Wait for page to settle a bit
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass

    # 2) Try on main page first
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

    # 3) Try inside iframes
    # iframes (short for inline frames) are HTML elements that allow embedding another HTML document within the current document.
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

    # 4) Last resort: use viewport center as a “map click” fallback
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
    """Handles network responses, filtering for AIC JSON payloads and logging them to a file."""
    # Only process network types that can carry JSON
    if r.request.resource_type not in ("xhr", "fetch"):
        return

    url = r.url
    #c-type is short for content-type
    ctype = r.headers.get("content-type", "")
    print(f"[RESP] {r.request.resource_type} {r.status} {ctype}")

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

    # Payload-shape detection — look for Items.$values array of objects
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
    
    # Calculate initial position (3/8 up and left from center (1/8 margin))
    dx = map_width/2  # Half map width for horizontal movement
    dy = map_height/2  # Half map height for vertical movement
    start_x = cx - 3*map_width/8
    start_y = cy - 3*map_height/8
    
    # Buffer to ensure map interface recognizes mouse
    e = 5  # pixels

    page.wait_for_timeout(10000)
    
    # click on map to focus
    page.mouse.move(cx, cy)
    page.mouse.click(cx, cy)
    page.wait_for_timeout(1000)

    # Move to starting position
    page.mouse.move(start_x, start_y)
    page.wait_for_timeout(1000)
    page.mouse.down()
    page.wait_for_timeout(1000)
    page.mouse.move(cx, cy, steps=25)
    page.wait_for_timeout(1000)
    page.mouse.up()
    
    print("Map focused and starting position set.")
    print("zooming in...")
    # Zoom in 5 times
    for _ in range(5):
        page.keyboard.press("Shift+=")
        page.wait_for_timeout(500)  # Wait for zoom animation (0.5 seconds)
    

    # Calculate target distances (6/8 of total map size * 32 due to zoom)
    target_horizontal = (6/8) * 32 * map_width
    target_vertical = (6/8) * 32 * map_height
    
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
            browser = p.chromium.launch(headless=True) #changed to headless=True for silent operation, so real mouse/keyboard cannot interfere
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

def Finding_Founded_Year(firms: list[dict]) -> list[dict]:
    
    YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b") #matches years from 1800 to 2099 (future component of range will be filtered later)
    ANCHORS = re.compile(r"\b(founded|since|est\.?|established|incorporated)\b", re.IGNORECASE) #re.IGNORECASE makes the regex case insensitive
    ANCHOR_KEYS = ["founded","since","est.","established","incorporated", "date_founded", "foundingyear", "year_established"]
    with sync_playwright() as p:
        # Launch browser with clean context
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        # Clear storage before starting
        page.context.clear_cookies()
        for firm in firms:
            website = firm.get("Website")
            try:

                # Navigate to the AIC members page
                page.goto(website)

                years = []

                """below are 5 helper functions used to extract the founded year from the website, in order of reliability."""
                def jsonld_extraction(page: playwright.sync_api.Page) -> list[int]:
                    """Attempts to extract founding years from JSON-LD scripts on the page."""

                    local_years = []
                    jsonScripts = page.locator('script[type="application/ld+json"]').all()
                    # JSON-LD scripts — a standard format for embedding Linked Data / Schema.org metadata.
                    # JSON-LD scripts are intentionally included for search engines to parse, increasing their reliability.
                    # On the other hand, other script may not contain reliable data.
                    for script in jsonScripts:
                        try:
                            data = json.loads(script.text_content() or "{}") #{} to handle None case
                        except Exception:
                            continue
                    
                        #Ensure format is list for uniform processing:
                        if isinstance(data, list):
                            items = data
                        else:
                            items = [data]
                        
                        # iterate items to find foundingDate
                        for item in items:
                            if isinstance(item, dict):
                                #look for foundingDate or foundingYear fields
                                founded = item.get("foundingDate") or item.get("foundingYear")
                                if isinstance(founded, str):
                                    # extract year using regex
                                    match = YEAR_RE.search(founded)
                                    if match:
                                        year = int(match.group(0)) #uses .group(0) to obtain the matched component of the string only
                                        #founding date cannot be in the future
                                        if 1800 <= year <= datetime.now().year:
                                            local_years.append(year)
                    return sorted(local_years) if local_years else None
                      
                def check_Anchors(text) -> list[int]:
                    """Checks for anchor words in the text and extracts years if found."""
                    if ANCHORS.search(text): #boolean check for presence of any anchor words
                        return [int(y) for y in YEAR_RE.findall(text) if 1800 <= int(y) <= datetime.now().year] #condensed for loop that returns all matching 4-digit year strings within the anchor-containing text as integers
                    return [] #return empty list if no anchor words found
                
                def check_relevant_pages(page) -> list[int]:
                    relevantPages = ["about","about-us","our-story","history","company","who-we-are"]
                    relevantTexts = []
                    for heading in relevantPages:
                        page.goto(f"{page.url.rstrip('/')}/{heading}") #ensures no double slashes in URL
                        
                        #explanation for the creation of potentialTexts:
                        # page.locator("main, body") selects the main content area of the page
                        # .locator("*").all()[:200] selects all child elements (i.e. all text written within that divider) within that content area as a list of locators, but limits to the first 200 elements to avoid overload
                        # e.inner_text() extracts the text content from each locator element (i.e. bypasses all HTML tags)
                        TEXTY = "p,li,span,div,a,section,article,header,footer,h1,h2,h3,h4,h5,h6"
                        nodes = page.locator("main, body, footer").locator(TEXTY).all()[:400]
                        potentialTexts = []
                        for el in nodes:
                            try:
                                potentialTexts.append(el.inner_text())
                            except Exception:
                                pass
                        
                        # iterate through potential texts and check for anchors
                        for text in potentialTexts:
                            relevantTexts += check_Anchors(text)
                    return sorted(relevantTexts) if relevantTexts else None

                def check_homepage(page) -> list[int]:
                    """Checks the homepage for founding year information."""
                    TEXTY = "p,li,span,div,a,section,article,header,footer,h1,h2,h3,h4,h5,h6"
                    nodes = page.locator("main, body, footer").locator(TEXTY).all()[:400]
                    potentialTexts = []
                    for el in nodes:
                        try:
                            potentialTexts.append(el.inner_text())
                        except Exception:
                            pass
                    relevantTexts = []
                    # iterate through potential texts and check for anchors
                    for text in potentialTexts:
                        relevantTexts += check_Anchors(text)
                    return sorted(relevantTexts) if relevantTexts else None
            
                def search_GoogleAPI() -> list[int]:
                    """Check first portion of text results for the with check anchors function."""
                    
                    # Google Custom Search API credentials
                    API_KEY = "AIzaSyA7idi5kLLBoPOp43LlFzgctqq9tOGwnn0"
                    CX = "75bd1883284f343f8"
                    query = f"site:{firm['Website']} founded OR since OR established"
                    url = f"https://www.googleapis.com/customsearch/v1?q={requests.utils.quote(query)}&key={API_KEY}&cx={CX}"
                    
                    response = requests.get(url)

                    if response.status_code == 200: #code 200 means successful request
                        data = response.json()
                        
                        snippets = [item.get("snippet", "") for item in data.get("items", [])]
                        #explnation of the above line:
                        # data.get("items", []) retrieves the list of search result items from the API response, and defaults to an empty list if "items" key is not present
                        # for each item in that list, item.get("snippet", "") retrieves the text snippet associated with that search result, defaulting to an empty string if "snippet" key is not present
                        # note that the snippet is the brief description text shown below each search result link in Google search results, and due to google's algorithms, it may contain relevant information such as founding years
                        relevantTexts = []
                        for text in snippets:
                            relevantTexts += check_Anchors(text)
                        return sorted(relevantTexts) if relevantTexts else None
                    return None

                jsonExtraction = jsonld_extraction(page) or []
                googleYears = search_GoogleAPI() or []
                pageCheck = check_relevant_pages(page) or []
                homepageCheck = check_homepage(page) or []

                # Will store the final founding year as the one found by all non-None methods, prioritizing reliability

                def consensus_year(*year_lists: list[int]) -> tuple[int, list[int]] | tuple[None, list[int]]:
                    """Take the minimum of the intersection of all year lists."""
                    # Filter out None or empty lists
                    year_sets = [set(ys) for ys in year_lists if ys]
                    if not year_sets:
                        return None

                    # Compute intersection
                    intersection = set.intersection(*year_sets) if len(year_sets) > 1 else year_sets[0]
                    union = set.union(*year_sets) if len(year_sets) > 1 else year_sets[0]

                    if union and intersection:
                        
                        return min(intersection), union
                        
                    # If intersection empty, try a weaker rule (see below)
                    return None, union
                

                year, yearUnion = consensus_year(jsonExtraction, googleYears, pageCheck, homepageCheck)
                if year:
                    print(f"Years found by every method for {firm['FullName']}: {yearUnion}")

                    print(f"Consensus founding year for {firm['FullName']} found: {year}")
                    firm["Founded_Year"] = year
                    continue  # move to next firm
                else:
                    print(f"No consensus founding year for {firm['FullName']}, trying weaker rule...")

                    # If no consensus, try a weaker rule: year must appear in at least two methods
                    year_counts = {}
                    for y in yearUnion:
                        count = 0
                        if y in jsonExtraction:
                            count += 1
                        if y in googleYears:
                            count += 1
                        if y in pageCheck:
                            count += 1
                        if y in homepageCheck:
                            count += 1
                        year_counts[y] = count
                    # Find years that appear in at least two methods
                    candidates = [y for y, c in year_counts.items() if c >= 2]
                    if candidates:
                        year = min(candidates)
                        print(f"Weaker rule founding year for {firm['FullName']} found: {year} (candidates: {candidates})")
                    firm["Founded_Year"] = year

                

    
        
            except Exception as e:
                print(f"Error occurred while processing AIC page: {e}")
                firm["Founded_Year"] = None
                continue

        # Wait for some time to ensure all requests are captured
        page.wait_for_timeout(10000)
        browser.close()

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
    # print("Starting AIC PE firm seeding process...")
    # open_aic_page()
    # print("AIC page processing completed. Extracting PE firms...")
    # pe_firms = extract_PE_firms()
    # print(f"Extracted {len(pe_firms)} PE firms from AIC data. Adding founded years...")
    # pe_firms_with_years = Finding_Founded_Year(pe_firms)
    # if pe_firms_with_years is None:
    #     print("Error occurred while adding founded years. Unable to add founded years.")
    #     export_PE_firms(pe_firms)
    # else:
    #     export_PE_firms(pe_firms_with_years)
    # print("PE firm data export completed.")

    # Test: ensure founding year extraction works on sample data
    print("Testing founding year extraction on sample data...")
    df = pd.read_csv("output/PE_firms.csv")
    sample_firms = df.to_dict(orient="records")  # Get list of firm dicts
    firms_with_years = Finding_Founded_Year(sample_firms)
    print(firms_with_years)
