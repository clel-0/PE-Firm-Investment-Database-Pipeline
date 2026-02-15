# PE Firm Database Pipeline

Python-based automation to extract PE Firm members of the Australian Investment Council and construct a comprehensive database of their portfolio companies as well as the founders/owners who sold them.

**Prerequisites:**
- Python 3.8+
- Node.js (required for Playwright)

## Installation
Within the terminal enter each of the following commands sequentially
```bash
git clone https://github.com/clel-0/PE-Firm-Investment-Database-Pipeline
cd pipeline
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
playwright install
```

Also ensure to provide your Google CX and API keys within portCo_Identification/.env:
```bash

API_KEY = "{Google API Key Here}"
CX = "{CX Key Here}"

```


Currently, only the seed_aic.py is fully operational and accurate, with the portCo_Identification pipeline being fully operational but not completely accurate. founded_year.py is not yet being used to add founding years to PE_firms.csv due to the appearance of 429 errors in response to GoogleAPI requests, that still need to be resolved. 

To run seed_aic.py, enter the following within the terminal:

```bash
python seed_aic.py
```

Then, to run the portCo_Identification pipeline, enter the following within the terminal:

```bash
python portCo_Identification/manual_HTML_analysis/main_portCo.py
```
NOTE: All of the code for the portCo identification process can be found in pipeline/portCo_Identification.


By running seed_aic.py followed by portCo_Identification.py, the system:
Collects data on all PE firms listed on the AIC website
Then visits each firm’s site to identify and extract their Portfolio Companies

### Current Results

- Successfully identifies all 28 AIC member PE firms
(output/PE_firms.csv)

- Locates Portfolio pages for 22 out of 28 firms (78%)
(output/PortCo_Website_Example.csv)

- Extracts full Portfolio Company lists from 11 of those 22 pages (50%).
These lists are complete but currently include some incorrect entries (false positives).
Firms: Anchorage, Bridgeport, CPE, Fortitude, LivingBridge, Mercury, Navis, Next, PEP, Salter Brothers, Riverside
(folder: output/unclean_portco_names)

- Implemented a cleaning system (text_scoring.py) which has successfully removed incorrect entries from 8 of the 11 extracted lists so far.
Examples can be cumulatively seen in:
output/PortCoName_Results_Cleaned_Example.csv
output/PortCoName_Results_Cleaned_Example_2.csv


## Methodology

### Phase 1: Australian PE firms identification

#### Aim
Seed list: crawl Australian Investment Council members page and parse PE firms.

#### Context
AIC displays its members on the following website:
"https://investmentcouncil.com.au/site/Shared_Content/Smart-Suite/Smart-Maps/Public/Member-Directory-Search.aspx"


However, in order to receive the required JSON containing the desired investment firm data, the interactive map must been zoomed in (+5) and contain the firm's location within its window.

Furthermore, even though Founded_Year, Focus_Sectors and Portfolio_Count_estimate were required fields to extract from the AIC Members page, without signing up to be a member this information is not on the page nor within any JSON responses received from the site. Thus, these must be found separately through crawling the Firm websites provided by the AIC members page. In order to validate the number chosen from the AIC members page, the number will be cross-referenced with a Google API search.

#### Functional Trace Notation

The following python programs operate through both sequential and nested function calls in order to establish functional modularity within the program. As a result, each step within the procedures below documents a function. Namely, if function1() is being documented, [function1()] will be stated at the start of the step. If function2() is recursively called within function1(), [function2()] will be chained to [function1()] at the start of the step: [function1()][function2()]. For deeper nesting, keep chaining. 

#### Procedure for Extracting Data from the AIC Members Page: seed_aic.py

##### Top-Level Functional Trace:
url: str &ensp; ->  &ensp; *[open_aic_page(url)]* &ensp;  -> &ensp;  None (creates and writes to JSONL file with Path OUTPUT_DIR) <br> 

OUTPUT_DIR: Path &ensp; -> &ensp;  *[extract_PE_firms(Path)]* &ensp; -> &ensp;  firms: list[dict] &ensp; -> &ensp;  *[export_PE_firms(firms, Path)]* &ensp; -> &ensp;  None (creates and writes to csv file)

##### Steps:
open_aic_page(url): Opens the AIC member directory page and performs a map sweep to trigger loading of all member data.

1. *[open_aic_page(url)]* Use sync_playwright to open a chromium browser, and attach a response_handler(response) function that logs any relevant responses (Note: this runs for every response received by the page) (The response_handler is covered in more detail in steps 4, 5, and 6). Then, on the chromium page navigate to the AIC members page. 

2. *[open_aic_page(url)][map_sweep(page)]* Now, with the chromium members page as the argument, execute map_sweep(page):<br>

*[open_aic_page(url)][map_sweep(page)][find_map_locator(page)]* Firstly, we need to find the locator of the interactive map within the html code of the page. find_map_locator() attempts to robustly find the map locator on the given Playwright page, including within iframes. Within the find_map_locator() function, we first allow the AIC members page to completely load (in this case we need to wait for the googleMapsAPI response be received). 

Through manually reading the html element code of the AIC members page, it was discovered that '[role="region"][aria-label="Map"]' was the map selector in this case. Fallback map selectors were also included (i.e. common CSS and Google Map embedding selectors). Thus, using these map selectors, we attempt to assign the variable 'loc' to the page locator, and determine which locator is correct by ensuring its bounding_box() method doesn't return None. If no selectors work, scroll down and re-attempt the same procdure. 

If no selectors work anywhere on the page, we attempt the same check, but for any iframes within the AIC members HTML document. If none of the selectors work within any of the iframes, we fall back to using the viewport of the HTML itself as the bounding box, however we raise an exception to let the user know of the unsuccessful determination of the locator, where in this case the map sweep attempted will most likely not work. Note that within this case, the correct locator was found. [Returns Locator object: 'loc']

3. *[open_aic_page()][map_sweep()]* Using the bounding_box() info from the locator discovered find_map_locator(), we centre the map about the top-left corner of the default window (with a 1/8 margin to save time and stil ensure all cities are covered), and zoom in 5 times. Them we perform a serpentine sweep of the map. Once the investment firms' markers for a given city appear on the window, a JSON response is received by the page, that contains a dictionary for each investment firm, which contain the following useful keys: 

"Website", "FullName", "Phone", "Email", "FullName5", "UserId", "Latitude", "Longitude", "LongLatAddress", "filter-Member Type". 

Like all other responses, these responses are fed through the response_handler():

4. *[open_aic_page()][response_handler()]* response_handler(): Handles network responses, filtering for AIC JSON payloads and logging them to a file. Firstly, we check that the request type is either "xhr" or "fetch". If not, this indicates that the response isn't a result of an interaction with the site. Then, we ignore any requests that are from the Google Map API. Note: while interaction with the Google Map interface results in the desired JSON being sent, the JSON is not requests from Google Maps. Namely, it is held by the AIC. For this reason, we ensure that the AIC url is within the request url. Then, we check whether "json" is listed as the content-type of the request (Note that the desired information is within a JSON file, as manually discovered through analysing the fetch/xhr responses from the AIC site).

5. *[open_aic_page()][response_handler()]* Following this, since we know the reponse is of type JSON, we capture the json string from the file. Now, we check the structure of the json file: from manual analysis, the desired file has a first-layer dict with key 'items', whose value is a dictionary containing a key '$values', and finally the value of data["items"]["$values"] is itself a list of dicts, where each dict hold info on a given investment firm (Example Snippet Below): 

{
    "$type": "Asi.Soa.Core.DataContracts.PagedResult, Asi.Contracts",
    "Items": {
        "$type": "System.Collections.Generic.List`1[[System.Object, mscorlib]], mscorlib",
        "$values": [
            {
                "$type": "System.Dynamic.ExpandoObject, System.Core",
                "Website": "https://www.aoshearman.com/en",
                "FullName": "A&O Shearman",
                "Phone": "61 2 9373 7700",
                "Email": "",
                "FullName5": "A&O Shearman",
                "UserId": "113",
                "Latitude": -33.869894900000,
                "Company": null,
                "Longitude": 151.209440900000,
                "ID": 65,
                "Radius": null,
                "LongLatAddress": "85 Castlereagh Street \r Sydney NSW 2000 \r Australia",
                "filter-Member Type": "CORP",
                "ExcludeDirectory": false
            }, 
            ...

Note that other, non-desired responses may also make it through the filtering, however this ensures that the desired responses are logged, with minimal undesired logs.

6. *[open_aic_page()][response_handler()]* For any response that passes the filtering of step 5, it will be wrapped with its metadata (time of retreival, url, status, headers, JSON string), and appended to this session's JSONL file, to allow for testing analysis to occur, i.e. debugging which tests and ensures performance. Note that each JSONL file is named with the date-time stamp corresponding to when the program was run. Thus, since the date-time stamp measures to the second, this ensures that even if there are multiple JSONL files within the logs, the program will only append and read the JSONL file created this session. Furthermore the JSONL file has path OUTPUT_DIR.

7. *[extract_PE_firms(Path)]*: Extracts and returns a list of private equity firms based in Australia from the logged AIC member data JSONL file. For each JSON object in the JSONL file, we recheck the structure, this time ensuring that "FullName" is a key within the dictionaries in the list data["items"]["$values"]. Furthermore, given this is true (which confirms the identity of the JSON as one of the desired files), we then only accept firms whose member type is "PE" and whose Address ends in "Australia" (last condition is due to the case where the map might scan over another country and detect a non-Australian PE firm). Given the firm is accepted, the corresponding dictionary is added to a lise of firms. [Returns list[dict] object: 'firms]

8. *[export_PE_firms(firms, Path)]*: Exports the list of private equity firms to a CSV file at the specified path. Firstly, turn the list of PE firm dicts into a pandas DataFrame. The desired CSV (PE_firms.csv) only requires the "FullName" and "Website" values from the AIC site, so filter for those columns, and convert the filtered df into a csv, and save within the output directory. Note that it was also decided to save more fields within a separate csv ("detailed_PE.csv"), as such data may be useful for future phases.


#### Current Procedure for Finding the Founding Year of Each Firm (NOTE: NOT COMPLETED. ISSUES: 429 Error raised on Google API requests, false positives provided by searching the firm's website): founded_year.py

##### Top-Level Functional Trace:

firms: list[dict] &ensp; -> &ensp; *[Finding_Founded_Year(firms)]* &ensp; -> &ensp; firms: list[dict]

Finding_Founded_Year(firms): Extracts the founded year for each firm from its website using multiple methods.

1. *[Finding_Founded_Year(firms)]* Enter each firm's website using a chromium playwright browser. Then, attempt the following methods (steps 2 to 8) to find the founding year for that firm (listed in order of reliability)

2. *[Finding_Founded_Year(firms)][jsonld_extraction()]* Search the JSON-LD scripts within the website, and return any value that contains the correct regex pattern of a founding year and has key containing the string "found" within it. Note: JSON-LD scripts are intentionally included for search engines to parse, increasing their reliability. On the other hand, other script may not contain reliable data.

3. *[Finding_Founded_Year(firms)][check_relevant_pages()]* Check possible pages within the site that could contain relevant information regarding the founding date of the firm ("about","about-us","our-story","history","company","who-we-are"). Namely, check the "main", "body" and "footer" section of the pages, and within these locators check sub-locators that tend to hold the HTML code for text that is visible on the website: (p,li,span,div,a,section,article,header,h1,h2,h3,h4,h5,h6). Within these sub-locators, parse the inner-text (i.e. the final layer of HTML code) through the function check_Anchors(text):

- *[Finding_Founded_Year(firms)][check_Anchors(text)]* check_Anchors(text) returns the 4-digit numbers that match the correct regex pattern of a founding year, if Anchors such as {founded, since, est., established,incorporated, dating, founding, ©}, are found within the same text. This increases the likehood that the context of the text includes the founding date, increasing the validity of the 4-digit numbers being considered as the firm's founding year.

Have check_relevant_pages() return a list of the potential founding years that were found by check_Anchors(text) within this step. 

4. *[Finding_Founded_Year(firms)][check_homepage()]* Then, apply the same analysis for step 3, but to the homepage of the website, also returing a list of the potential founding years that were found by check_Anchors(text) within this step. 

5. *[Finding_Founded_Year(firms)][search_GoogleAPI()]* Search "site:{firm['Website']} founded OR since OR established" automatically using the GoogleAPI request process, and given the response is successful (status_code = 200), apply check_Anchors() to the 'snippets' of text provided by each search result item. Note that the snippet is the brief description text shown below each search result link in Google search results, and due to google's algorithms, it may contain relevant information such as founding years. Have search_GoogleAPI() return a list of the potential founding years that were found by check_Anchors(text) within this step. 
        
6. *[Finding_Founded_Year(firms)][consensus_year()]* Check if there are years that was returned to be a potential founding year by steps 2, 3, 4, and 5. If the intersection (only between non-empty turns) contains at least one year, return the year as the the minimum of the intersection.

7. *[Finding_Founded_Year(firms)][consensus_year()]* Else, return the year as the minimum of the intersection between the the googleAPI result (if it exists), as well as at least one other method. 

8. *[Finding_Founded_Year(firms)][consensus_year()]* If within both step 6 and 7 an empty intersection is received, check if any method produces a non-empty list of possible founding years (Prioritising Reliable Methods). For the first method to return a non-empty list (in order of reliability), return the year as the minimum of the list.

9. *[Finding_Founded_Year(firms)]* Complete steps 2 to 8 for each firm in firms (as previously stated in step 1), with each year being assigned to the value of the "Founded_Year" key within the firm's dictionary, in firms. Then return firms. 

### Phase 2: PortCo identification

#### Outline of Steps within Phase 2 (Functional Trace Notation not yet added)

- Step 1: Find the portfolio subpage within the PE firm's website.
(Exception: For Step 1 Attempt 2, we check if the firm has a PE subpage. This is because some of the PE firms that are listed with the AIC hold investments in fields other than PE, with PE just being one of the types of investments they have.)


- Step 2: Extract ranked classes (which are attributes of Bs4 tag objects) from the html of the portfolio subpage.


- Step 3: Find PortCo names within the portfolio subpage, checking both the JSON LD scripts and the classes found in step 2.


##### Step 1 Attempt 1: Directly check if any of the following subpage patterns exist:

    - firm["website"]+"/(portfolio|Portfolio|investments Investments|companies|Companies|funds|Funds)".

    - firm["website"]+"/(holdings|Holdings|businesses|Businesses)"

##### Step 1 Attempt 2: Directly check if any of the following subpage patterns exist:

    - firm["website"]+"/(privateequity|private-equity|pe)" or firm["website"].split(".")[1] + ("privateequity"|"pe"|"investments"|"portfolio") + {".com",".com.au"} (case insensitive)

##### Step 1 Attempt 3: Use a Google Custom Search API to search for the portfolio subpage, using the following siteSearch and query values:
    
    - siteSearch: pe_firm["Website"]
    - q: (
        "intitle:portfolio OR intitle:investments OR intitle:companies"
            
        "OR inurl:portfolio OR inurl:investments OR inurl:companies"
        
        "OR \"our companies\" OR \"portfolio companies\" OR porfolio OR investments"
        )

##### Step 2 Attempt 1: Collate the tag objects that contain the class attributes, and create a set of the distinct classes from that portfolio subpage. Furthermore, rank the classes on whether the following words are also found within the same Bs4 tag object:
    
    - A:[("portfolio", "card"), ("portfolio", "item"),
        ("investment", "card"), ("investment", "item"),
        ("investment", "box")], 
    - B:[("portfolio",), ("investment",), ("company",)],
    - C:[("item",), ("box",), ("card",), ("logo",)]

    Additionally, any tag objects that contain any of the following words are not considered:
    - footer|header|nav|menu|cookie|subscribe|social|share|breadcrumb|search|hero|banner|modal|popup


##### Step 3 Attempt 1: Collate further information on all the tag objects containing the classes found in step 2 (see below) and collate the JSON-LD scripts from the portfolio subpage:

    
- INFO TUPLE ON CLASSES FOUND IN STEP 2: (element, class_string, signals_dict)
    Where element is a BeautifulSoup tag object, 
    class_string is the joined string of class names, and signals_dict contains extracted signals like link domain, image domain, and name hint.

##### Additionally, filter out any JSON-LD scripts that have properties indicating they do not contain the list of PortCos, i.e. contain Blacklist words and not Whitelist words (see sets of both below), doesn't contain a name attribute or if so, contains the PE firm as the name attribute:

- WHITELIST: {"Organization","Corporation","LocalBusiness","Brand","Company"}
- BLACKLIST: {"WebPage","WebSite","BreadcrumbList","Article","NewsArticle","Person","FAQPage","HowTo","BlogPosting"}


##### Then, for each JSON-LD script, using the info tuples above for each selected class in step 2, match the JSON-LD script to the most likely class it corresponds to. 
If the class is found, using the rank of the class, the similarities between the JSON-LD script and the class, as well as the presence of WHITELIST words, score the JSON-LD scripts and determine if any can be classified as the list of PortCos. If the class isn't found, but the JSON-LD script is org-like, add to candidates but with low confidence.



##### Step 3 Attempt 2:  Extracting portCo names (a inner text, img alt text, figcaption> text):
Within the chosen html classes from 2.1, we will search for any a tags, and extract the inner text of those a tags as portCo names. Then, search for any img tags, and extract the 'alt' text of those img tags as portCo names. Then, search for any figcaption tags, and extract the inner text of those figcaption tags as portCo names. If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.

Rankings of PortCo name candidates:
- A: if only a tags and below are found, within a class that is of rank A to B from 2.1.
- B: if only img tags and below are found, within a class that is of rank A to B from 2.1.
- C: if only figcaption tags and below are found, within a class that is of rank A to B from 2.1.
- D: if only a tags and below are found, if lower ranks from 2.1 (C to E).
- E: if only img tags and below are found,  if lower ranks from 2.1 (C to E).
- F: if only figcaption tags and below are found, if lower ranks from 2.1 (C to E).

###### (FOLLOWING ATTEMPTS ONLY CAN OCCUR IF ATTEMPT 2 PRODUCED A NON-EMPTY LIST)

##### Step 3 Attempt 3: Extracting portCo names ('src' values):
Firstly, group text candidates from attempt 2 by the card (soup tag object) they were derived from. (This will allow us to boost confidence for high confidence tags in the same card)

Then, if an 'src' link is found adjacent to an attempt 2 text candidate, extract the text from where the name of the portCo is most likely to be:

- the first non-numerical component after '/uploads' (only alphabetic), and bounded to the right by either a hyphen, underscore, or file extension (., jpg, png, svg, etc).

Finally, append the extracted 'src' text to the set of srcTexts for that given card.

##### Step 3 Attempt 4: Extracting portCo names (href links):
If a 'href' link is found adjacent to an attempt 3 text candidate, split the link by the "/" characters, and extract the text element that follows:

- {"investments", "portfolio", "companies", "investment-portfolio"} (consider A-rank extraction)
- {"company", "funds"} (considered B-rank extraction)

If none of these words are found within the text elements in the href, extract the last text element in the href list. (C-rank extraction)

Append the final candidate to the set of hrefTexts for that given card.


##### AT THIS STAGE, ALL THE PORTCO NAME CANDIDATES (Text, Src, Href, Image) FOR A GIVEN PE FIRM ARE COLLATED INTO A CSV AND EXPORTED TO: output/unclean_portco_names/pe_firm['FullName'].csv

##### REFINEMENT OF PORTCO NAME CANDIDATES: Text Scoring:

(Initially, move all candidates from the csv into a Pandas DataFrame object for more efficient filtration)

1) Cleaning and basic filtering: 
- drop duplicate candidates (only differ due to formatting)
- drop text candidates that match any texts in JUNK_STRINGS:
JUNK_STRINGS = {
    "portfolio", "for investors", "contact", "contact us", "",
    "text hover", "for", "about us", "logo", "read more", "team",
    "investments", "news", "placeholder", "strategies", "sustainability",
    "terms of use", "privacy policy", "growth", "private equity",
    "our people", "our board", "our senior team", "our team",
    "advisory", "news press", "view profile", " ", "plugins", "basic", "assets", "app", "themes", "images"
    }
- drop text candidates that match an email-like structure (non-trivially contains @ symbol)
- drop candidates with too few alphabetic characters
- remove excess whitespace from text candidates

2) Immediate high-confidence collection: rank-A href candidates:
- If there exists rank-A href candidates, accept them all as the portCo names

3) (NEW) Immediate high-confidence collection: "logo" substring:
- If the word "logo" exists in the first 3 strings, accept them all as portCo names (given the cleaning that has already occurred, remaining groups with the word logo indicate reference to portfolio logo imagery with high confidence)

4) PortCo list assumption: within any Portfolio subpage, portfolios will be listed homogenously.
- Group candidates together with the same html path
- If 3 or more of the candidates within a given group satisfy the following google search confirmation, accept the whole group as the list of PortCo names:
    - Use the query "private equity firm {pe_name} invested in company {name}" where name is the text candidate. If the search results the name and the pe_name appearing together in the snippet of at least 3 websites, accept the group.

##### AT THIS STAGE, ALL THE PORTCO NAME CANDIDATES THAT PASSED THE REFINEMENT STAGE FOR A GIVEN PE FIRM ARE COLLATED INTO A CSV AND EXPORTED TO: output/portco_name_results_cleaned_.csv
