from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests




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
                    union = set.union(*year_sets) if len(year_sets) > 1 else year_sets[0]
                    if not year_sets:
                        if union:
                            return None, union
                        else:
                            return None, []

                    # Compute intersection
                    intersection = set.intersection(*year_sets) if len(year_sets) > 1 else year_sets[0]
                    

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