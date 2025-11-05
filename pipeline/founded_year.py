from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests




def Finding_Founded_Year(firms: list[dict]) -> list[dict]:
    """Extracts the founded year for each firm from its website using multiple methods."""
    
    YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b") #matches years from 1800 to 2099 (future component of range will be filtered later)
    ANCHORS = re.compile(r"\b(founded|since|est\.?|established|incorporated|dating|founding|©)\b", re.IGNORECASE) #re.IGNORECASE makes the regex case insensitive
    
    #Note: scraper tends to mistake postcode numbers for years, so we will filter out any years that share the same textbox as address-related keywords
    ADDRESS_KEYWORDS = re.compile(r"\b(address|location|headquarters|hq|office|street|road|ave|avenue|blvd|boulevard|st\.?|rd\.?|suite|zip|postal|city|state|country)\b", re.IGNORECASE)

    #Note: scraper tends to mistake date stamps for founding years, so we will filter out any years that appear alongside date-related keywords
    DATE_KEYWORDS = re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE)

    
    for firm in firms:
        website = firm.get("Website")
        with sync_playwright() as p:
            try:
                # Launch browser with clean context
                browser = p.chromium.launch(headless=True) 
                context = browser.new_context(
                    ignore_https_errors=True,
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()
                # Clear storage before starting
                page.context.clear_cookies()


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
                                #look for any field with "found" in the key name
                                founded = None
                                for key in item.keys():
                                    if "found" in key.lower():
                                        founded = item.get(key)
                                        print(f"Found JSON-LD founding info for {firm['FullName']}: {founded}")
                                
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
                    possibleYears = []
                    if ANCHORS.search(text): #boolean check for presence of any anchor words
                        possibleYears =  [int(y) for y in YEAR_RE.findall(text) if 1800 <= int(y) <= datetime.now().year] #condensed for loop that returns all matching 4-digit year strings within the anchor-containing text as integers
                        #filter out years that appear in address-related textboxes
                        if ADDRESS_KEYWORDS.search(text) or DATE_KEYWORDS.search(text):
                            possibleYears = [] #discard all years if address keywords or date keywords are present
                    return possibleYears #return empty list if no anchor words found
                
                def check_relevant_pages(page) -> list[int]:
                    relevantPages = ["about","about-us","our-story","history","company","who-we-are"]
                    relevantTexts = []
                    for heading in relevantPages:
                        page.goto(f"{page.url.rstrip('/')}/{heading}") #ensures no double slashes in URL
                        
                        #explanation for the creation of potentialTexts:
                        # page.locator("main, body") selects the main content area of the page
                        # .locator("*").all()[:200] selects all child elements (i.e. all text written within that divider) within that content area as a list of locators, but limits to the first 200 elements to avoid overload
                        # e.inner_text() extracts the text content from each locator element (i.e. bypasses all HTML tags)
                        TEXTY = "p,li,span,div,a,section,article,header,h1,h2,h3,h4,h5,h6"
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
                    TEXTY = "p,li,span,div,a,section,article,header,h1,h2,h3,h4,h5,h6"
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
            
                #currently encountering 429 errors when using Google API
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
                        if snippets:
                            print(f"Google API results for {firm['FullName']}: {snippets}")
                        else:
                            print(f"No Google API results for {firm['FullName']}")
                        #explnation of the above line:
                        # data.get("items", []) retrieves the list of search result items from the API response, and defaults to an empty list if "items" key is not present
                        # for each item in that list, item.get("snippet", "") retrieves the text snippet associated with that search result, defaulting to an empty string if "snippet" key is not present
                        # note that the snippet is the brief description text shown below each search result link in Google search results, and due to google's algorithms, it may contain relevant information such as founding years
                        relevantTexts = []
                        for text in snippets:
                            relevantTexts += check_Anchors(text)
                        return sorted(relevantTexts) if relevantTexts else None
                    else:
                        print(f"Google API request failed for {firm['FullName']} with status code {response.status_code}")
                    return None

                jsonExtraction = jsonld_extraction(page) or []
                pageCheck = check_relevant_pages(page) or []
                homepageCheck = check_homepage(page) or []
                googleYears = search_GoogleAPI() or []
                # Will store the final founding year as the one found by all non-None methods, prioritizing reliability

                def consensus_year(*year_lists):
                    year_sets = [set(ys) for ys in year_lists if ys]

                    # If nothing at all was found by any method
                    if not year_sets:
                        return None, []

                    # Safe union/intersection
                    union = set().union(*year_sets)            # OK even if len==1
                    intersection = (set.intersection(*year_sets)
                                    if len(year_sets) > 1 else next(iter(year_sets)))

                    if intersection:
                        return min(intersection), sorted(union)
                    return None, sorted(union)
                

                year, yearUnion = consensus_year(jsonExtraction, googleYears, pageCheck, homepageCheck)
                if year:
                    print(f"Years found by every method for {firm['FullName']}: {yearUnion}")

                    print(f"Consensus founding year for {firm['FullName']} found: {year}")
                    firm["Founded_Year"] = year
                    continue  # move to next firm
                else:
                    print(f"No consensus founding year for {firm['FullName']}, trying weaker rule...")

                                        
                    # Weaker rule: year must appear in Google results + at least one other method
                    year_counts = {}
                    for y in yearUnion:
                        count = 0
                        if y in jsonExtraction:
                            count += 1
                        if y in googleYears:
                            count += 10
                        if y in pageCheck:
                            count += 1
                        if y in homepageCheck:
                            count += 1
                        year_counts[y] = count
                    
                    candidates = [y for y, c in year_counts.items() if c >= 11]
                    if candidates:
                        year = min(candidates)
                        print(f"Weaker rule founding year for {firm['FullName']} found: {year} (candidates: {candidates})")
                    else:
                        print(f"No founding year found for {firm['FullName']}, will set in order of reliability to None.")
                        if jsonExtraction:
                            print(f"Years found from JSON-LD: {min(jsonExtraction)} (all: {jsonExtraction})")
                            year = min(jsonExtraction)
                        elif pageCheck:
                            print(f"Years found from relevant pages: {min(pageCheck)} (all: {pageCheck})")
                            year = min(pageCheck)
                        elif homepageCheck:
                            print(f"Years found from homepage: {min(homepageCheck)} (all: {homepageCheck})")
                            year = min(homepageCheck)

                        elif googleYears:
                            print(f"Years found from Google API: {min(googleYears)} (all: {googleYears})")
                            year = min(googleYears)
                        else:
                            print("No years found by any method.")
                            year = None
                        
                    firm["Founded_Year"] = year

                

    
        
            except Exception as e:
                print(f"Error occurred while processing page: {e}")
                firm["Founded_Year"] = None
                continue

       
        

    return firms


if __name__ == "__main__":
    # Test: ensure founding year extraction works on sample data
    print("Testing founding year extraction on sample data...")
    df = pd.read_csv("output/PE_firms.csv")
    sample_firms = df.to_dict(orient="records")  # Get list of firm dicts: orient="records" converts each row to a dict, and stores all dicts in a list
    firms_with_years = Finding_Founded_Year(sample_firms)
    print(firms_with_years)