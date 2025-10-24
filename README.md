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

To run seed_aic.py, enter the following within the terminal:

```bash
python seed_aic.py
```

and to execute the test run for founded_year.py enter the following within the terminal:

```bash
python founded_year.py
```

## Description of Methodology

### Phase 1: Australian PE firms identification

#### Aim
Seed list: crawl Australian Investment Council members page and parse PE firms.

#### Context
AIC displays its members on the following website:
"https://investmentcouncil.com.au/site/Shared_Content/Smart-Suite/Smart-Maps/Public/Member-Directory-Search.aspx"


However, in order to receive the required JSON containing the desired investment firm data, the interactive map must been zoomed in (+5) and contain the firm's location within its window.

Furthermore, even though Founded_Year, Focus_Sectors and Portfolio_Count_estimate were required fields to extract from the AIC Members page, without signing up to be a member this information is not on the page nor within any JSON responses received from the site. Thus, these must be found separately through crawling the Firm websites provided by the AIC members page. In order to validate the number chosen from the AIC members page, the number will be cross-referenced with a Google API search.

#### Procedure
1. open_aic_page(): Opens the AIC member directory page and performs a map sweep to trigger loading of all member data.

Detail:
Use sync_playwright to open a chromium browswer, and attach a response_handler(response) function that logs any relevant responses (Note: this runs for every response received by the page) (This will be covered in more detail below). Then, on the chromium page navigate to the AIC members page. 

Now, with the chromium members page as the argument, execute map_sweep(page):<br>

- Firstly, we need to find the locator of the interactive map within the html code of the page. find_map_locator() attempts to robustly find the map locator on the given Playwright page, including within iframes. Within the find_map_locator() function, we first allow the AIC members page to completely load (in this case we need to wait for the googleMapsAPI response be received). 

Through manually reading the html element code of the AIC members page, it was discovered that '[role="region"][aria-label="Map"]' was the map selector in this case. Fallback map selectors were also included (i.e. common CSS and Google Map embedding selectors). Thus, using these map selectors, we attempt to assign the variable 'loc' to the page locator, and determine which locator is correct by ensuring its bounding_box() method doesn't return None. If no selectors work, scroll down and re-attempt the same procdure. 

If no selectors work anywhere on the page, we attempt the same check, but for any iframes within the AIC members HTML document. If none of the selectors work within any of the iframes, we fall back to using the viewport of the HTML itself as the bounding box, however we raise an exception to let the user know of the unsuccessful determination of the locator, where in this case the map sweep attempted will most likely not work. Note that within this case, the correct locator was found. 

- Then, using the bounding_box() info from the locator discovered find_map_locator(), we centre the map about the top-left corner of the default window (with a 1/8 margin to save time and stil ensure all cities are covered), and zoom in 5 times. Them we perform a serpentine sweep of the map. Once the investment firms' markers for a given city appear on the window, a JSON response is received by the page, that contains a dictionary for each investment firm, which contain the following useful keys: 

"Website", "FullName", "Phone", "Email", "FullName5", "UserId", "Latitude", "Longitude", "LongLatAddress", "filter-Member Type". Like all other responses, these responses are fed through the response_handler():

- response_handler(): Handles network responses, filtering for AIC JSON payloads and logging them to a file. Firstly, we check that the request type is either "xhr" or "fetch". If not, this indicates that the response isn't a result of an interaction with the site. Then, we ignore any requests that are from the Google Map API. Note: while interaction with the Google Map interface results in the desired JSON being sent, the JSON is not requests from Google Maps. Namely, it is held by the AIC. For this reason, we ensure that the AIC url is within the request url. Then, we check whether "json" is listed as the content-type of the request (Note that the desired information is within a JSON file, as manually discovered through analysing the fetch/xhr responses from the AIC site).

Following this, since we know the reponse is of type JSON, we capture the json string from the file. Now, we check the structure of the json file: from manual analysis, the desired file has a first-layer dict with key 'items', whose value is a dictionary containing a key '$values', and finally the value of data["items"]["$values"] is itself a list of dicts, where each dict hold info on a given investment firm (Example Snippet Below): 

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

For any response that passes this filtering, it will be wrapped with its metadata (time of retreival, url, status, headers, JSON string), and appended to this session's JSONL file, to allow for testing analysis to occur to debug and ensure performance. Note that each JSONL file is named with the date-time stamp corresponding to when the program was run. Thus, since the date-time stamp measures to the second, this ensures that even if there are multiple JSONL files within the logs, the program will only append and read the JSONL file created this session. 



        



