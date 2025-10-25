# PE Firm Database Pipeline

Python-based automation to extract PE Firm members of the Australian Investment Council and construct a comprehensive database of their portfolio companies as well as the founders/owners who sold them.

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
Currently, only the seed_aic.py is fully operational and accurate. founded_year.py is not yet being used to add founding years to PE_firms.csv due to the appearance of 429 errors in response to GoogleAPI requests, that still need to be resolved. 

Then to run seed_aic.py, enter the following within the terminal:

```bash
python seed_aic.py
```

and to execute the test run for founded_year.py enter the following within the terminal:

```bash
python founded_year.py
```

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
url: str ->  &ensp; [open_aic_page(url)]  -> &ensp;  None (creates and writes to JSONL file with Path OUTPUT_DIR) <br> 
OUTPUT_DIR: Path  -> &ensp;  [extract_PE_firms(Path)]  -> &ensp;  firms: list[dict]  -> &ensp;  [export_PE_firms(firms, Path)]  -> &ensp;  None (creates and writes to csv file)

##### Steps:
open_aic_page(url): Opens the AIC member directory page and performs a map sweep to trigger loading of all member data.

1. [open_aic_page(url)] Use sync_playwright to open a chromium browser, and attach a response_handler(response) function that logs any relevant responses (Note: this runs for every response received by the page) (The response_handler is covered in more detail in steps 4, 5, and 6). Then, on the chromium page navigate to the AIC members page. 

2. [open_aic_page(url)][map_sweep(page)] Now, with the chromium members page as the argument, execute map_sweep(page):<br>

[open_aic_page(url)][map_sweep(page)][find_map_locator(page)] Firstly, we need to find the locator of the interactive map within the html code of the page. find_map_locator() attempts to robustly find the map locator on the given Playwright page, including within iframes. Within the find_map_locator() function, we first allow the AIC members page to completely load (in this case we need to wait for the googleMapsAPI response be received). 

Through manually reading the html element code of the AIC members page, it was discovered that '[role="region"][aria-label="Map"]' was the map selector in this case. Fallback map selectors were also included (i.e. common CSS and Google Map embedding selectors). Thus, using these map selectors, we attempt to assign the variable 'loc' to the page locator, and determine which locator is correct by ensuring its bounding_box() method doesn't return None. If no selectors work, scroll down and re-attempt the same procdure. 

If no selectors work anywhere on the page, we attempt the same check, but for any iframes within the AIC members HTML document. If none of the selectors work within any of the iframes, we fall back to using the viewport of the HTML itself as the bounding box, however we raise an exception to let the user know of the unsuccessful determination of the locator, where in this case the map sweep attempted will most likely not work. Note that within this case, the correct locator was found. [Returns Locator object: 'loc']

3. [open_aic_page()][map_sweep()] Using the bounding_box() info from the locator discovered find_map_locator(), we centre the map about the top-left corner of the default window (with a 1/8 margin to save time and stil ensure all cities are covered), and zoom in 5 times. Them we perform a serpentine sweep of the map. Once the investment firms' markers for a given city appear on the window, a JSON response is received by the page, that contains a dictionary for each investment firm, which contain the following useful keys: 

"Website", "FullName", "Phone", "Email", "FullName5", "UserId", "Latitude", "Longitude", "LongLatAddress", "filter-Member Type". 

Like all other responses, these responses are fed through the response_handler():

4. [open_aic_page()][response_handler()] response_handler(): Handles network responses, filtering for AIC JSON payloads and logging them to a file. Firstly, we check that the request type is either "xhr" or "fetch". If not, this indicates that the response isn't a result of an interaction with the site. Then, we ignore any requests that are from the Google Map API. Note: while interaction with the Google Map interface results in the desired JSON being sent, the JSON is not requests from Google Maps. Namely, it is held by the AIC. For this reason, we ensure that the AIC url is within the request url. Then, we check whether "json" is listed as the content-type of the request (Note that the desired information is within a JSON file, as manually discovered through analysing the fetch/xhr responses from the AIC site).

5. [open_aic_page()][response_handler()] Following this, since we know the reponse is of type JSON, we capture the json string from the file. Now, we check the structure of the json file: from manual analysis, the desired file has a first-layer dict with key 'items', whose value is a dictionary containing a key '$values', and finally the value of data["items"]["$values"] is itself a list of dicts, where each dict hold info on a given investment firm (Example Snippet Below): 

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

6. [open_aic_page()][response_handler()] For any response that passes the filtering of step 5, it will be wrapped with its metadata (time of retreival, url, status, headers, JSON string), and appended to this session's JSONL file, to allow for testing analysis to occur, i.e. debugging which tests and ensures performance. Note that each JSONL file is named with the date-time stamp corresponding to when the program was run. Thus, since the date-time stamp measures to the second, this ensures that even if there are multiple JSONL files within the logs, the program will only append and read the JSONL file created this session. Furthermore the JSONL file has path OUTPUT_DIR.

7. [extract_PE_firms(Path)]: Extracts and returns a list of private equity firms based in Australia from the logged AIC member data JSONL file. For each JSON object in the JSONL file, we recheck the structure, this time ensuring that "FullName" is a key within the dictionaries in the list data["items"]["$values"]. Furthermore, given this is true (which confirms the identity of the JSON as one of the desired files), we then only accept firms whose member type is "PE" and whose Address ends in "Australia" (last condition is due to the case where the map might scan over another country and detect a non-Australian PE firm). Given the firm is accepted, the corresponding dictionary is added to a lise of firms. [Returns list[dict] object: 'firms]

8. [export_PE_firms(firms, Path)]: Exports the list of private equity firms to a CSV file at the specified path. Firstly, turn the list of PE firm dicts into a pandas DataFrame. The desired CSV (PE_firms.csv) only requires the "FullName" and "Website" values from the AIC site, so filter for those columns, and convert the filtered df into a csv, and save within the output directory. Note that it was also decided to save more fields within a separate csv ("detailed_PE.csv"), as such data may be useful for future phases.


#### Current Procedure for Finding the Founding Year of Each Firm (NOTE: NOT COMPLETED. ISSUES: 429 Error raised on Google API requests, false positives provided by searching the firm's website)

##### Top-Level Functional Trace:

firms: list[dict] &ensp; -> Finding_Founded_Year(firms) &ensp; -> firms: list[dict]

Finding_Founded_Year(firms): Extracts the founded year for each firm from its website using multiple methods.

1. [Finding_Founded_Year(firms)] Enter each firm's website using a chromium playwright browser. Then, attempt the following methods (steps 2 to 8) to find the founding year for that firm (listed in order of reliability)

2. [Finding_Founded_Year(firms)][jsonld_extraction()] Search the JSON-LD scripts within the website, and return any value that contains the correct regex pattern of a founding year and has key containing the string "found" within it. Note: JSON-LD scripts are intentionally included for search engines to parse, increasing their reliability. On the other hand, other script may not contain reliable data.

3. [Finding_Founded_Year(firms)][check_relevant_pages()] Check possible pages within the site that could contain relevant information regarding the founding date of the firm ("about","about-us","our-story","history","company","who-we-are"). Namely, check the "main", "body" and "footer section of the pages, and within these locators check sub-locators that tend to hold the HTML code for text that is visible on the website: (p,li,span,div,a,section,article,header,h1,h2,h3,h4,h5,h6). Within these sub-locators, parse the inner-text (i.e. the final layer of HTML code) through the function check_Anchors(text):

- [Finding_Founded_Year(firms)][check_Anchors(text)] check_Anchors(text) returns the 4-digit numbers that match the correct regex patter of a founding year, if Anchors such as {founded, since, est., established,incorporated, dating, founding, ©}, are found within the same text. This increases the likehood that the context of the text includes the founding date, increasing the validity of the 4-digit numbers being considered as the firm's founding year.

Have check_relevant_pages() return a list of the potential founding years that were found by check_Anchors(text) within this step. 

4. [Finding_Founded_Year(firms)][check_homepage()] Then, apply the same analysis for step 3, but to the homepage of the website, also returing a list of the potential founding years that were found by check_Anchors(text) within this step. 

5. [Finding_Founded_Year(firms)][search_GoogleAPI()] Search "site:{firm['Website']} founded OR since OR established" automatically using the GoogleAPI request process, and given the response is successful (status_code = 200), apply check_Anchors() to the 'snippets' of text provided by each search result item. Note that the snippet is the brief description text shown below each search result link in Google search results, and due to google's algorithms, it may contain relevant information such as founding years. Have search_GoogleAPI() return a list of the potential founding years that were found by check_Anchors(text) within this step. 
        
6. [Finding_Founded_Year(firms)][consensus_year()] Check if there are years that was returned to be a potential founding year by steps 2, 3, 4, and 5. If the intersection (only between non-empty turns) contains at least one year, return the year as the the minimum of the intersection.

7. [Finding_Founded_Year(firms)][consensus_year()] Else, return the year as the minimum of the intersection between the the googleAPI result (if it exists), as well as at least one other method. 

8. [Finding_Founded_Year(firms)][consensus_year()] If within both step 6 and 7 an empty intersection is received, check if any method produces a non-empty list of possible founding years (Prioritising Reliable Methods). For the first method to return a non-empty list (in order of reliability), return the year as the minimum of the list.

9. [Finding_Founded_Year(firms)] Complete steps 2 to 8 for each firm in firms (as previously stated in step 1), with each year being assigned to the value of the "Founded_Year" key within the firm's dictionary, in firms. Then return firms. 
