




"""







NOTE: NOT USED ANYMORE, REPLACED BY PORTCO_IDENTIFICATION FOLDER, WHICH HAS CLEANER STRUCTURE AND BETTER MODULARITY.






(will keep here for reference, and in case multi-file structure breaks)

"""


















"""
(Structure of Docstring: list of approaches, with rankings of implementations. Rankings are designed to be used in confidence scoring later on.)

A: 6pts
B: 5pts
C: 4pts
D: 3pts
E: 2pts
F: 1pt

__Step 1 Attempt 1__: Accessing portfolio subpage (direct):
From a given PE firm's website, access the portfolio subpage:
    Rank:
    A: firm["website"]+"/(portfolio|Portfolio|investments|Investments|companies|Companies|funds|Funds)".
    B: firm["website"]+"/(holdings|Holdings|businesses|Businesses)".
    
    
__Step 1 Attempt 2__: Accessing portfolio subpage (indirect):
Some PE firms are not only PE firms, but also have venture capital arms, or growth equity arms. As a result, there may exist no portfolio subpage on the main website.
In such cases, we will attempt to access the portfolio subpage from the PE firm's website, by entering the PE subpage of site, if available in
   Rank: 
    A: firm["website"]+"/(privateequity|private-equity|pe)" or firm["website"].split(".")[1] + ("privateequity"|"pe"|"investments"|"portfolio") + {".com",".com.au"} (case insensitive).
    (NOTE: The above attempts are done more securely than what is displayed in the docs; see the actual code for implementation)
    Then from the PE subpage, if found using privateequity|pe we will attempt to access the portfolio subpage using the same approach as in Step 1 Attempt 1
    If found using investments|portfolio, we will assume that is the portfolio subpage.

    
__Step 1 Attempt 3__:
If that also fails, we will use the Google Custom Search API to search for the portfolio subpage, by searching for 
    Rank:
    A: site:{firm['website']} (portfolio|investments)

    In order to accurately find the working portfolio subpage, we will first search for the above query with an expoenential backoff on 429 errors (Helper function: google_search),
    and then will ensure that the page is accessible by making a HEAD request and checking for a 200 status code (Helper function: check_page_accessible).
    Both helper functions will be defined within this Step 1 Attempt 3 function, and will both return the same dict structure if successful, namely:
        {
            'step1_method': 'Attempt 3',
            'website_found': str or None,
            'website_confidence': str or None
        }





If any of the above attempts succeed, we will proceed with 2.1 below.


__Step 2 Attempt 1__: Accessing appropriate html classes to find portCos (names and logos):
Within the portfolio subpage html, record all the inner texts with the label "src", that are within a class
with a name containing any of the following. We will rank subsets of words by how strongly they indicate the presence of portfolio companies:
    Rank:
    A: {'Portfolio' and 'Card'}, {'Portfolio' and 'Item'}, {'Investment' and 'Card'}, {'Investment' and 'Item'}, {'Investment' and 'box'}, {'Investment' and 'box'} (case insensitive).
    B: {'Portfolio'}, {'Investment'}, {'Company'} (case insensitive).
    C: {'item'}, {'box'}, {'card'}, {'logo'} (case insensitive).
    D: any class name, but with any of the words within A to C present in the inner text of the class.
    E: any class name.
     
Only ranks A to C will be considered, and D,E will only be used as a last resort if no portCos are found in A to C.







_______________________

__Step 3 Attempt 1__: Extracting portCo names (JSON LD script, name field):
Within the chosen html classes from 2.1, we will search for any JSON LD script tags, and extract the 'name' field from those scripts as portCo names.
If multiple JSON LD scripts are found, we will extract the 'name' field from all of them.
If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.

Given Ranks A,B from 2.1, this method receives rank A.
Given Rank C from 2.1, this method receives rank B.
Otherwise, this method receives rank E, due to the fact that JSON LD scripts also hold other information, and are not specifically designed to hold portCo names.
_______________________

__Step 3 Attempt 2__: Extracting portCo names (<a> inner text, img alt text, <figcaption> text):
Within the chosen html classes from 2.1, we will search for any <a> tags, and extract the inner text of those <a> tags as portCo names.
If no <a> tags are found, we will search for any <img> tags, and extract the 'alt' text of those <img> tags as portCo names.
If no <img> tags are found, we will search for any <figcaption> tags, and extract the inner text of those <figcaption> tags as portCo names.
If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.
Rank:
    A: if <a> tags are found, within a class that is of rank A to B from 2.1.
    B: if <img> tags are found, within a class that is of rank A to B from 2.1.
    C: if <figcaption> tags are found, within a class that is of rank A to B from 2.1.
    D: if <a> tags are found, if lower ranks from 2.1 (C to E).
    E: if <img> tags are found,  if lower ranks from 2.1 (C to E).
    F: if <figcaption> tags are found, if lower ranks from 2.1 (C to E).
_______________________


__Step 3 Attempt 3__: Extracting portCo names ('src' values):
From the 'src' values obtained in 2.1, we will extract the portCo names.
Now, the 'src' value seems to be an upload hyperlink that contains the name of the portCo right after or a couple of back slashes after the substring '/uploads'.
As a result, we will extract the substring of the 'src' values that:
    Rank:
    (for A,B from 2.1):
    A: is the first non-numerical component after '/uploads' (only alphabetic), and bounded to the right by either a hyphen, underscore, or file extension (., jpg, png, svg, etc).
    (Only reason this is Attempt 3 is because it is brittle, but given the high reliability of 2.1 A,B classes, if it is found then it has high confidence).
    (otherwise for C-E from 2.1, E, due to the fact that 'src' values may contain many non-portCo images):


Additionally, we will check the portCo name with a Google API, by searhing 'Who invested in {src_value}', and recording the top result's snippet text. If the snippet text contains the name of the PE firm, we will label that portCo as invested by the PE firm.

Example for 3.3 (Adamantem Capital):

<a href="https://adamantem.com.au/portfolio/hygain-holdings/">
	<div class="portfolio-list-box-logo">
		<div class="img-wrap">
			<img decoding="async" width="150" height="146" src="https://adamantem.com.au/wp-content/uploads/2025/07/logo02.svg" class="attachment-thumbnail size-thumbnail" alt="Hygain Holdings">									</div>
				</div>
					<div class="portfolio-list-box-hover">
						<div class="portfolio-list-box-image">
							<img loading="lazy" decoding="async" width="412" height="412" src="https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-412x412.jpg" 
                            class="attachment-portfolio_list_box size-portfolio_list_box wp-post-image" alt="Hygain Holdings" srcset="https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-412x412.jpg 412w,
                              https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-300x300.jpg 300w, https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-150x150.jpg 150w, 
                              https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-550x550.jpg 550w, https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-372x372.jpg 372w, 
                              https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-384x384.jpg 384w, https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings.jpg 687w" sizes="auto, 
                              (max-width: 412px) 100vw, 412px">									
                        </div>
					        <div class="portfolio-list-box-title">Hygain Holdings</div>
				    </div>
</a>

in this example, we would extract 'Hygain Holdings' as the portCo name from the 'src' value:
https://adamantem.com.au/wp-content/uploads/2025/07/Hygain-Holdings-412x412.jpg



__Step 3 Attempt 4__: Extracting portCo names (href links):
If 3.3 fails to find any portCos, we will scrape the chosen html classes for href links containing the following subsets of words. We will rank the subsets by reliability:
    Rank:
    (A,B from 2.1): 
    A: {'investments/', 'portfolio/', 'companies/' } (case insensitive)
    B: {'company/', 'funds/'} (case insensitive)
    C: any href link.
    (otherwise for C-E from 2.1, E, due to the fact that href links may contain many non-portCo links)

    We will check A,B, and C in order, and only proceed to the next rank if no portCos are found in the previous rank. Rank will be documented for each portCo found, and will be used in confidence scoring later.
    
    
and extract the inner text of those href links as portCo names, namely the text after {'investments/', 'portfolio/'}. 
The rationale behind this is that some PE firms have portfolio subpages that link to individual portCo subpages, and the portCo name is often in the URL. Additionally, the probability of such links being the desired portCo links is high, given the presence of 'investments/' or 'portfolio/' in the href link, and the fact that 
the most obvious subpages of a portfolio page, would be the individual portfolio companies.

Example for 3.4 (Allegro Capital):
<a class="block z-10 relative transition-all duration-200" data-id="66c5ad5e-6bc5-454f-8419-a58c4c14a64b" data-checked="false" 
href="/investments/be-campbell"><div class="z-10"><div class="relative lg:hidden"><div class="absolute z-[1] top-0 left-0 w-full 
h-px bg-black/20" style="width: 100%;"></div></div><div class="md:hidden z-10 relative"><div class="flex justify-between items-center
py-[17px]"><div class="flex items-center"><h5 class="font-semibold text-[16px] leading-[20px] lg:text-[20px] lg:leading-[26px] 
tracking-[-1.5%]">BE Campbell ...  </p><div class="flex justify-center items-center bg-background rounded-[6px] w-[45px] h-[35px]"><span 
class="text-[25px] leading-none row-arrow">→</span></div></div></div><div class="relative"><div class="absolute z-[1] bottom-0 left-0
w-full h-px bg-black/20" style="width: 0px;"></div></div></div></div></a>

From this example, we would extract 'be-campbell' as the portCo name. 


"""



import os
from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests
from urllib.parse import urljoin

#helper function to perform Google Custom Search with retries on 429 errors
def google_search(params, pe_firm, retries=5, backoff=2):
    """
    Helper function to perform Google Custom Search with retries on 429 errors.
    Returns same dict as step1_attempt_3 if successful, else returns empty list.

    Will return a list of all valid results if successful.
    """
    websites = []
    
    attempt = 0
    while True:
        try:
            #attempt to get results from Google Custom Search API
            response = requests.get(url = "https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
            #handle 429 error with exponential backoff
            if response.status_code == 429:
                # too many requests -> backoff
                print(f"Received 429 error from Google Custom Search API on attempt {attempt}, backing off...")
                attempt += 1
                if attempt > retries:
                    print("Exceeded maximum retries for Google Custom Search API due to 429 errors.")
                    return None  # return empty list on exceeding retries
                
                time.sleep(backoff ** attempt)
                continue

            results = response.json()
            print("------- Google Custom Search API Response -------")
            print({
                "status": response.status_code,
                "searchTerms": results.get("queries", {}).get("request", [{}])[0].get("searchTerms"),
                "totalResults": results.get("searchInformation", {}).get("totalResults"),
                "params_echo": results.get("queries", {}).get("request", [{}])[0],  # what Google thinks you asked for
            })
            print("-------------------------------------------------")
            if response.status_code != 200:
                print(f"Google Custom Search API error: {results.get('error', {}).get('message', 'Unknown error')}")
                return None  # return empty list on other errors
            else:
                print(f"Google Custom Search API returned results successfully.")
            #process results and extract URLs
            if "items" in results and len(results["items"]) > 0:
                for i in range(len(results["items"])):
                    top_result_url = results["items"][i]["link"]
                    websites.append(top_result_url) 
                
            else:
                print(f"No search results found from Google Custom Search API, for site: {pe_firm['Website']}")
            break  # No more results
        except requests.RequestException as e:
            if not hasattr(google_search, "exception_counter"):
                google_search.exception_counter = 0
            if google_search.exception_counter < 3:  # Allow up to 3 passes
                google_search.exception_counter += 1
                print(f"RequestException occurred while accessing Google Custom Search API (attempt {google_search.exception_counter}): {e}. Passing...")
                pass
            else:
                print(f"RequestException occurred while accessing Google Custom Search API: {e}. Exceeded allowed retries.")
                return None  # exit gracefully on exception
    
    if websites:
        return websites
    else:
        print(f"No search results found from Google Custom Search API, for site: {pe_firm['Website']}")
    return None


#commonly required function to check if a page is accessible
def check_page_accessible(url, timeout=10):
    """
    Sends a HEAD request to the given URL. Then, if the status code is 200 AND the page-type is not an image/pdf/video/etc AND response.headers.get("Content-Length") is provided, returns True, as well as the final URL after redirects.
    Else, if the status code is either 405 or 501 or not response.headers.get("Content-Length"), we will instead send a GET request to check accessibility, but with stream version on, and checking the first 8 KB only, to act as a manual HEAD request.
    If returning status code is 200 AND the page-type is not an image/pdf/video/etc, returns True, as well as the final URL after redirects.
    Else, returns False, None.

    Note: we need to check response.headers.get("Content-Length"), because some websites return 200 status codes for pages that do not exist, but have 0 content length (Robustness check).
    """
    BAD_CONTENT_TYPES = re.compile(r"\.(pdf|docx?|pptx?|xlsx?)$", re.I)
    response = requests.head(url, allow_redirects=True, timeout=timeout)
    
    if response.status_code == 200 and not BAD_CONTENT_TYPES.search(response.url) and response.headers.get("Content-Length"):
        print(f"response status OK for {response.url}")
        return True, response.url
    
    elif response.status_code in (405, 501) or (200 <= response.status_code < 400 and not response.headers.get("Content-Length")):
        print(f"trying GET request for {response.url}")
        get = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
        if get.status_code == 200 and not BAD_CONTENT_TYPES.search(get.url):
            print(f"response status OK for {response.url} after GET follow-up")
            return True, get.url
    elif response.status_code == 202:
        # Some sites return 202 for async redirects; try a GET follow-up
        get = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
        print(f"202 detected for {response.url}, trying a GET follow-up")
        if get.status_code == 200:
            print(f"response status OK for {response.url} after GET follow-up")
            return True, get.url
        
    print(f"Nothing seemed to work for {response.url}, with status code {response.status_code}")
    return False, None





    


def step1_attempt_1(pe_firm: dict) -> dict | None:
    from urllib.parse import urljoin

    subpage_patterns = [
        ("portfolio", "A"),
        ("investments", "A"),
        ("companies", "A"),
        ("funds", "A"),
        ("holdings", "B"),
        ("businesses", "B"),
        # common variants
        ("our-companies", "A"),
        ("portfolio-companies", "A"),
    ]

    base_url = pe_firm["Website"].rstrip("/")

    for subpath, confidence in subpage_patterns:
        candidate_url = urljoin(base_url + "/", subpath)  # tries both /portfolio and /portfolio/
        accessible, final_url = check_page_accessible(candidate_url)
        if accessible:
            print(f"Accessible portfolio subpage found with Attempt 1: {final_url}")
            return {
                "step1_method": "Attempt 1",
                "website_found": final_url,
                "website_confidence": confidence
            }
        else:
            candidate_url = urljoin(base_url + "/", subpath) + "/"  # try with trailing slash
            accessible, final_url = check_page_accessible(candidate_url)
            if accessible:
                print(f"Accessible portfolio subpage found with Attempt 1: {final_url}")
                return {
                    "step1_method": "Attempt 1",
                    "website_found": final_url,
                    "website_confidence": confidence
                }

    return None



def step1_attempt_2(pe_firm: dict) -> dict:
    """
   Returns:
        {
            'step1_method': 'Attempt 2',
            'website_found': str or None,
            'website_confidence': str or None
        }
        or None if all subpages fail.
    """

    subpage_patterns = [
        ("privateequity", "A", True, False),
        ("private-equity", "A", True, False),
        ("pe", "A", True, False),
        ("privateequity", "A", True, True),
        ("private-equity", "A", True, True),
        ("pe", "A", True, True),
        ("portfolio", "A", False, True),
        ("investments", "A", False, True),
        
    ]



    base_url = pe_firm["Website"].rstrip("/")

    for subpath, confidence, doAttempt1, subpage in subpage_patterns:
        # Construct full URL safely
        if subpage:
            candidate_url = urljoin(base_url + "/", subpath)
        else:
            #adding the subpage pattern directly to the name of the website
            domain_parts = re.match(r"https?://(www\.)?([^/]+)", base_url)
            if not domain_parts:
                continue  # skip if URL is malformed
            domain_name = domain_parts.group(2)
            # Construct candidate URL by inserting subpath after domain, and before TLD (top-level domain)
            candidate_url = f"https://{domain_name.split('.')[0]}{subpath}.{'.'.join(domain_name.split('.')[1:])}"
        try:
            # Make a lightweight HEAD request (no full page download)
            # requests.head() asks the website for headers only, to check if the page exists
            isAccessible, final_url = check_page_accessible(candidate_url)
            if isAccessible:
                if doAttempt1:
                    # Now attempt Step 1 Attempt 1 on this subpage
                    subpage_result = step1_attempt_1({"Website": final_url})
                    if subpage_result:
                        return subpage_result
                    else:
                        continue  # proceed to next pattern if Step 1 Attempt 1 fails
                
                return {
                    "step1_method": "Attempt 2",
                    "website_found": final_url,
                    "website_confidence": confidence
                }
        except requests.RequestException:
            continue  # skip if timeout or connection error

    return None

import time
#importing time for exponential backoff on 429 errors

def step1_attempt_3(pe_firm: dict) -> dict:
    """
    Use the Google Custom Search API to search for the portfolio subpage, by searching for 
    Rank:
    A: site:{firm['website']} (portfolio|investments)

    and access the top result.
    Returns:
        {
            'step1_method': 'Attempt 3',
            'website_found': str or None,
            'website_confidence': str or None
            
        }
        or None if all subpages fail.
    """
    

    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
     # Google Custom Search API credentials
    API_KEY = os.getenv("API_KEY")
    CX = os.getenv("CX")
    if not API_KEY or not CX:
        raise ValueError("Google API Key and CX must be set in environment variables.")
    #ensure API_KEY and CX are set
    import tldextract
    ext = tldextract.extract(pe_firm["Website"])
    domain = f"{ext.domain}.{ext.suffix}"  # e.g. adamantem.com.au


    params = {
        "key": API_KEY,
        "cx": CX,
        "q": (
            "(intitle:portfolio OR intitle:investments OR intitle:companies "
            "OR inurl:portfolio OR inurl:investments OR inurl:companies "
            "OR \"our companies\" OR \"portfolio companies\" OR porfolio OR investments) "
        ),
        "siteSearch": domain,
        "siteSearchFilter": "i",  # include subdomains
        "num": 10
    }

    
    
    #returns most relevant result that is accessible
    urls = google_search(params,pe_firm)
    if urls:
        for i,result in enumerate(urls):
            accessible, final_url = check_page_accessible(result)
            if accessible:
                print(f"Accessible portfolio subpage found via Google Custom Search API: {final_url}")
                return {
                    "step1_method": "Attempt 3",
                    "website_found": final_url,
                    "website_confidence": "A",
                    "website_reliability_rank": i+1  #1 is most reliable
                }
    else:
        print("No accessible portfolio subpage found via Google Custom Search API.")
        return None
    print("While results were found from Google Custom Search API, none were accessible portfolio subpages.")
    return None

    
    


import lxml
from bs4 import BeautifulSoup
def step2_attempt_1(portfolio_website: dict) -> dict[list[dict]]:
    
    """
    
    Returns dict for each PE firm that contains:
        'classes_found': list[dict], 'class_confidence': int
        where each dict in 'classes_found' has keys:
            'class_rank': int, 'class_path': str

    """

    RANK_SETS = {
    "A": [("portfolio", "card"), ("portfolio", "item"),
          ("investment", "card"), ("investment", "item"),
          ("investment", "box")],
    "B": [("portfolio",), ("investment",), ("company",)],
    "C": [("item",), ("box",), ("card",), ("logo",)],


    } 

    # avoid obvious noise containers
    CLASS_BLACKLIST = re.compile(
    r"(footer|header|nav|menu|cookie|subscribe|social|share|breadcrumb|search|hero|banner|modal|popup)",
    re.I,
    )  


    def _class_rank(class_list):
        """Return 'A'/'B'/'C' or None based on class tokens (substring match)."""
        if not class_list:
            return None
        tokens = [c.lower() for c in class_list if isinstance(c, str)]
        if any(CLASS_BLACKLIST.search(t) for t in tokens):
            return None

        def has_all(words):
            # any token containing each word (substring)
            return all(any(w in t for t in tokens) for w in words)

        for rank in ("A", "B", "C"):
            for words in RANK_SETS[rank]:
                if has_all(words):
                    return rank
        return None

    #helper function to determine class rank
    def extract_candidate_classnames(html: str):
        """
        Parse HTML and return unique class names per rank.
        Output:
        {
            "A": [...],
            "B": [...],
            "C": [...],
            "stats": {"A": nA, "B": nB, "C": nC, "total_elements_scanned": N}
        }
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            print(f"Error parsing HTML with BeautifulSoup: {e}")
            print("Returning empty class buckets.")
            return {"A": [], "B": [], "C": [], "stats": {"A": 0, "B": 0, "C": 0, "total_elements_scanned": 0}}
        buckets = {"A": set(), "B": set(), "C": set()}
        scanned = 0
        #looking through all elements with a class attribute
        for e in soup.find_all(True):
            scanned += 1
            cls = e.get("class")
            r = _class_rank(cls)
            if r:
                # store the literal class attribute string (space-joined)
                buckets[r].add(" ".join(cls))

        # sort for stable output
        out = {k: sorted(list(v)) for k, v in buckets.items()}
        out["stats"] = {
            "A": len(out["A"]),
            "B": len(out["B"]),
            "C": len(out["C"]),
            "total_elements_scanned": scanned,
        }
        print(f"Class extraction stats for {portfolio_website['website_found']}: {out['stats']}")
        return out
    


    try:
        response = requests.get(portfolio_website["website_found"], timeout=15)
        response.raise_for_status()
        html_content = response.text

        class_buckets = extract_candidate_classnames(html_content)
        classes_found = []
        for cls in class_buckets["A"]:
            classes_found.append({"class_rank": "A", "class_path": cls})
        for cls in class_buckets["B"]:
            classes_found.append({"class_rank": "B", "class_path": cls})
        for cls in class_buckets["C"]:
            classes_found.append({"class_rank": "C", "class_path": cls})
        
        if not classes_found:
            print(f"No portCo-related classes found on portfolio subpage for Step 2 (Screening for classes): {portfolio_website['website_found']}.")
            return None
        else:
            return {"classes_found": classes_found} 


    except requests.RequestException as e:
        print(f"Error accessing portfolio subpag for Step 2 (Screening for classes): {portfolio_website['website_found']}. Error: {e}")
        return None


"""

__Step 3: Extracting portCo names (various methods)__:
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int
"""
def step3_attempt_1(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    """
    Extract portCo names from JSON LD scripts within the chosen html classes from step 2, as well as throughout the entire page.






    """
    
    #ChatGPT Attempt 1 implementation: refine and rewrite
    TYPE_WHITELIST = {"Organization","Corporation","LocalBusiness","Brand","Company"}
    TYPE_BLACKLIST = {"WebPage","WebSite","BreadcrumbList","Article","NewsArticle","Person","FAQPage","HowTo","BlogPosting"}
    from urllib.parse import urlparse

    def _norm(s): 
        """
        this normalizes strings by stripping whitespace and collapsing multiple spaces into one space
        it repleaces one or more whitespace characters with a single space, and then trims leading/trailing spaces
        """
        return re.sub(r"\s+"," ", s or "").strip()

    def _domain(u):
        try:
            """
            netloc refers to the network location part of the URL, which includes domain and port
            urlparse splists the URL into components; scheme://netloc/path?query#fragment
            therefore, urlparse(u).netloc gives us the domain (and port if present)
            eg: urlparse("https://www.example.com/path").netloc -> "www.example.com"
            then, we lowercase it and strip "www." prefix if present
            return the cleaned domain, or empty string on error
            """
            netloc = urlparse(u).netloc.lower()
            if netloc.startswith("www."): netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    def _logo_url(val):
        """
        Given the val is a dict, return the 'url' or '@id' field if present, else return empty string
        """
        
        if isinstance(val, dict):
            return val.get("url") or val.get("@id") or ""
        return val or ""

    def _iter_jsonld_nodes(soup):
        """

        1) collates all scripts with type JSON LD. 
        2) Then, loading each soup element as a json object is attempted. 
        3) Given this works, for each json object we then look for the graph tag, 
          and if the graph tag points to a list, we add all the elements of that list to a new 'candidates' list. 
        4) Additionally, if the graph tag doesn't exist, we add all the first layer values in the json that are dicts. 
        5) Then, for all of the candidates of a given JSON LD script, then if the candidate itself is of type itemlist, 
          with the itemlistelement value being of type list, then if each element in the itemlistelement list is of type dict
          and has key item, yield the value of the key item, the JSON LD script it came from, and the type of derivation, 
          in this case "itemlist". 
        6) If the item key doesnt point to a val of type dict, then create a dict for it called synth, 
          that has the type, name and url corresponding to the item, and yield in similar fashion but
          with synth instead of s. 
        7) Then, if the type isnt itemlist, assume the candidate is a single portCo, so then yield the candidate, 
          the JSON LD it came from, and derivation type "jsonld". 


        Yield (node, script_el, source_tag) where node is a dict entity.
        NOTE: Yield is a special type of return that allows the function to be an iterator, producing a sequence of values over time.
        in this case, it yields each JSON-LD node found in the HTML soup, remembering the script element it came from and the source tag type 
        (jsonld or itemlist).
        In essence, yield is essentially a return function, but it remembers its state so that within the next call, it takes the arguments one ahead of the last yielded one.
        """
        for s in soup.find_all("script", attrs={"type":"application/ld+json"}):
            try:
                data = json.loads(s.string or s.text or "")
            except Exception:
                continue
            # normalize to iterable of nodes
            candidates = []
            if isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    candidates.extend([n for n in data["@graph"] if isinstance(n, dict)])
                else:
                    candidates.append(data)
            elif isinstance(data, list):
                candidates.extend([n for n in data if isinstance(n, dict)])
            else:
                continue

            for n in candidates:
                # expand ItemList into its elements as separate nodes
                if n.get("@type") == "ItemList" and isinstance(n.get("itemListElement"), list):
                    for it in n["itemListElement"]:
                        if isinstance(it, dict):
                            # two common shapes
                            if "item" in it and isinstance(it["item"], dict):
                                yield it["item"], s, "itemlist"
                            else:
                                # synthesize an org-like node if keys present
                                synth = {"@type": it.get("@type") or "ListItem"}
                                if "name" in it: synth["name"] = it["name"]
                                if "url" in it: synth["url"] = it["url"]
                                yield synth, s, "itemlist"
                    continue
                yield n, s, "jsonld"

    def _is_company_like(n):
        """
        Returns true if the set of words in the @type field of the JSON LD node intersect with the TYPE_WHITELIST, 
        and false if they intersect with the TYPE_BLACKLIST.
        """
        t = n.get("@type")
        
        types = {t} if isinstance(t, str) else set(t or [])
        #in this case, the and/or logic checks if the types of the JSON LD node intersect with the blacklist or whitelist, i.e. if both contain any common elements
        if types & TYPE_BLACKLIST:
            return False
        if types & TYPE_WHITELIST:
            return True
        # unknown type but has org-ish structure → weak accept (handled by scoring)
        if bool(n.get("name") and (n.get("url") or n.get("logo") or n.get("sameAs"))):
            print(f"Unknown JSON-LD type encountered: {types}, but may have org-like structure.")
            return True
        return False

    def _extract_entity(n):
        """
        
        """
        name = _norm(n.get("name"))
        url  = n.get("url") or ""
        logo = _logo_url(n.get("logo"))
        same = n.get("sameAs") or []
        if isinstance(same, str): same = [same]
        jtype = n.get("@type")
        if isinstance(jtype, list): 
            # prefer an org-like type if present
            jtype = next((t for t in jtype if t in TYPE_WHITELIST), jtype[0] if jtype else None)
        return {
            "name": name,
            "url": url,
            "logo": logo,
            "sameAs": same,
            "jsonld_type": jtype or "",
            "_url_domain": _domain(url),
            "_logo_domain": _domain(logo) or (_domain(same[0]) if same else ""),
        }

    def _collect_cards(soup, card_class_tokens):
        """Return list of (el, class_string, signals_dict) for candidate cards."""
        tokens = set(c.lower() for c in card_class_tokens)
        cards = []
        for el in soup.find_all(True, class_=True):
            cls = [c for c in el.get("class") if isinstance(c, str)]
            if any(tok in (c.lower() for c in cls) for tok in tokens):
                # signals: anchor & image domains + visible title-ish text
                href = (el.find("a", href=True) or {}).get("href") if el.find("a", href=True) else ""
                img  = (el.find("img", src=True) or {}).get("src") if el.find("img", src=True) else ""
                link_dom = _domain(href)
                img_dom  = _domain(img)
                # quick name hint from typical title nodes or alt
                name_hint = None
                for sel in ["[aria-label]","img[alt]","h1","h2","h3","h4",".title",".name","strong"]:
                    node = el.select_one(sel)
                    if node:
                        name_hint = _norm(node.get("aria-label") or getattr(node, "get_text", lambda *_: "")(" ") or node.get("alt"))
                        if name_hint: break
                cards.append((el, " ".join(cls), {"link_domain":link_dom, "img_domain":img_dom, "name_hint":name_hint}))
        return cards

    def _name_matches(a, b):
        if not a or not b: return False
        aa, bb = _norm(a).lower(), _norm(b).lower()
        if aa == bb: return True
        # Accept strong substring containing whole words
        return (aa in bb and len(aa) >= 3) or (bb in aa and len(bb) >= 3)

    def _score(entity, card_signals, inside_bonus):
        score = 0.0
        # type
        if entity["jsonld_type"] in TYPE_WHITELIST: score += 1.0
        # url/logo domain matches
        if entity["_url_domain"] and entity["_url_domain"] == card_signals.get("link_domain"): score += 0.9
        if entity["_logo_domain"] and entity["_logo_domain"] in {card_signals.get("link_domain"), card_signals.get("img_domain")}: score += 0.6
        # name agreement
        if _name_matches(entity["name"], card_signals.get("name_hint")): score += 0.7
        # proximity bonus
        score += inside_bonus  # 0.3 inside card, 0.2 near, 0 otherwise (we only compute inside here)
        return score

    def extract_portcos_from_jsonld(html, page_url, card_class_tokens, pe_firm_name, pe_firm_domain):
        """
        Returns list of records:
        {name, url, logo, jsonld_type, matched_by, container_class, score, rank_label, page_url, provenance}
        """

        #parses HTML into a structured tree using an lxml parser known as a BeautifulSoup object.
        #Using to find all class elements that match the card_class_tokens provided from step 2, and extract JSON-LD entities from the page.
        soup = BeautifulSoup(html, "lxml")
        cards = _collect_cards(soup, card_class_tokens)

        # Gather JSON-LD entities with provenance
        entities = []
        for node, script_el, src_kind in _iter_jsonld_nodes(soup):
            # blacklist hard reject
            t = node.get("@type")
            types = {t} if isinstance(t, str) else set(t or [])
            if types & TYPE_BLACKLIST: 
                continue

            ent = _extract_entity(node)
            # exclude the PE firm itself
            if ent["_url_domain"] and ent["_url_domain"] == pe_firm_domain.lower():
                continue
            if _name_matches(ent["name"], pe_firm_name):
                continue

            # must have at least a name
            if not ent["name"]:
                continue

            entities.append({
                **ent,
                "_script": script_el, 
                "_source": src_kind
            })

        results = []

        # Try to match each entity to each card (inside proximity bonus when script is inside the card subtree)
        for ent in entities:
            best = None
            for el, cls, sig in cards:
                # inside-card check
                inside = ent["_script"] and el in ent["_script"].find_parents()  # True if script nested inside the card
                bonus = 0.3 if inside else 0.0
                sc = _score(ent, sig, bonus)
                if best is None or sc > best[0]:
                    best = (sc, cls, sig, inside)
            if best:
                sc, cls, sig, inside = best
                if sc >= 1.2:  # threshold per plan
                    matched_by = []
                    if ent["jsonld_type"] in TYPE_WHITELIST: matched_by.append("type_whitelist")
                    if ent["_url_domain"] and ent["_url_domain"] == sig.get("link_domain"): matched_by.append("url_domain_match")
                    if ent["_logo_domain"] and ent["_logo_domain"] in {sig.get("link_domain"), sig.get("img_domain")}: matched_by.append("logo_domain_match")
                    if _name_matches(ent["name"], sig.get("name_hint")): matched_by.append("name_match")
                    if inside: matched_by.append("inside_card")

                    rank = "A" if sc >= 1.8 else "B"
                    results.append({
                        "name": ent["name"],
                        "url": ent["url"],
                        "logo": ent["logo"],
                        "jsonld_type": ent["jsonld_type"],
                        "matched_by": matched_by,
                        "container_class": cls if inside else None,
                        "score": round(sc, 3),
                        "rank_label": rank,
                        "page_url": page_url,
                        "provenance": {"source": ent["_source"]},
                    })

        # De-dup by (name, url domain)
        seen, out = set(), []
        for r in sorted(results, key=lambda x: (-x["score"], x["name"].lower())):
            key = (r["name"].lower(), _domain(r["url"]))
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
        pass

def step3_attempt_2(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass

def step3_attempt_3(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass
def step3_attempt_4(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass

def PortCo_Extraction(pe_firms: list[dict]) -> list[dict]:
    """
    Goes through attempts for each step, returning a list of dicts, where the dict will contain a list of dicts for the portCos for each PE firm.
    Within each element of the overall list, the dict will have keys:
        'firm_name': str, 'step1_method': int, 'website_found': str, 'website_confidence': int, 'portcos': list[dict] (for attempts 1,2 of step 1, 'website_found' will be the portfolio subpage used, for attempt 3 of step 1, it will be the googled website (also possibly portfolio subpage), 'step1_method' is the int of the attempt number).
    
    Each element of the 'portcos' list will be a dict with keys:
        'portco_name': str, 'step3_method_used': int, 'class_confidence_used': int, 'extraction_confidence': int (for attempts 1,2 of step 3, 'extraction_method' will be the int of the attempt number).

    """
    results = []
    for pe_firm in pe_firms:
        print(f"Processing PE firm: {pe_firm['FullName']} with website: {pe_firm['Website']}")
        #might use later for steps 2 and 3
        # with sync_playwright() as p:
        #     try:
        #         browser = p.chromium.launch(headless=True)
        #         context = browser.new_context()
        #         page = context.new_page()
        #         page.goto(pe_firm['Website'], timeout=60000)
        #     except Error as e:
        #         print(f"Error accessing PE firm website: {pe_firm['Website']}. Error: {e}")
        #         continue  # Skip to next PE firm if website access fails

        portfolio_website = step1_attempt_1(pe_firm)
        if not portfolio_website:
            print("Step 1 Attempt 1 failed to find any portfolio subpage.")
            print("Now proceeding to Step 1 Attempt 2...")
            portfolio_website = step1_attempt_2(pe_firm)
        if not portfolio_website:
            print("Step 1 Attempt 2 failed to find any portfolio subpage.")
            print("Now proceeding to Step 1 Attempt 3...")
            portfolio_website = step1_attempt_3(pe_firm)
        if not portfolio_website:
            print("Step 1 Attempt 3 failed to find any portfolio subpage.")
            print("All Step 1 attempts failed. Trying other PortCo Extractions..")
            print("NOTE: Due to the high flexibility of Step 1 Attempt 3 (Google Search just grabs the top result), it is likely that an error occurred within the implementation.")
            
                

        if portfolio_website:
            print(f"Portfolio subpage found: {portfolio_website['website_found']}, via {portfolio_website['step1_method']}")
            print("Now proceeding to Step 2 Attempt 1...")
            portco_class = step2_attempt_1(portfolio_website)
            if not portco_class:
                print(f"Step 2 Attempt 1 failed to find any portCo Classes, on the portfolio subpage: {portfolio_website['website_found']}")
                print("NOTE: Due to the high flexibility of Step 2 Attempt 1 (searching for any class name if all else fails), it is likely that an error occurred within the implementation if no portCo classes were found.")
            else:
                success_flag = False

                print(f"Step 2 Attempt 1 succeeded in finding portCo Classes, on the portfolio subpage: {portfolio_website['website_found']}")
                print("Now proceeding to Step 3 Attempt 1...")
                portcos = step3_attempt_1(portfolio_website, [c['class_path'] for c in portco_class['classes_found']])
                if not portcos:
                    print("Step 3 Attempt 1 failed to find any portCos from the portCo Classes found.")
                    portcos = step3_attempt_2(portfolio_website, [c['class_path'] for c in portco_class['classes_found']])
                    if not portcos:
                        print("Step 3 Attempt 2 also failed to find any portCos from the portCo Classes found.")
                        portcos = step3_attempt_3(portfolio_website, [c['class_path'] for c in portco_class['classes_found']])
                        if not portcos:
                            print("Step 3 Attempt 3 also failed to find any portCos from the portCo Classes found.")
                            portcos = step3_attempt_4(portfolio_website, [c['class_path'] for c in portco_class['classes_found']])
                            if not portcos:
                                print("All Step 3 attempts failed. Skipping to next PE firm...")
                                print("NOTE: Due to the high flexibility of Step 3 Attempt 4 (searching for any href link if all else fails), it is likely that an error occurred within the implementation if no portCos were found.")
                                
                            else:
                                print("Step 3 Attempt 4 succeeded in finding portCos from the portCo Classes found.")
                                success_flag = True
                        else:
                            print("Step 3 Attempt 3 succeeded in finding portCos from the portCo Classes found.")
                            success_flag = True
                    else:
                        print("Step 3 Attempt 2 succeeded in finding portCos from the portCo Classes found.")
                        success_flag = True
                else:
                    print("Step 3 Attempt 1 succeeded in finding portCos from the portCo Classes found.")
                    success_flag = True
                
                if success_flag:
                    print(f"PortCos found: {[pc['potential_portco_names'] for pc in portcos]}")
                    results.append({
                        "firm_name": pe_firm["FullName"],
                        "step1_method": portfolio_website["step1_method"],
                        "website_found": portfolio_website["website_found"],
                        "website_confidence": portfolio_website["website_confidence"],
                        "portcos": portcos
                    })

    return results

   





#writing this first to get overall structure:
if __name__ == "__main__":
    df = pd.read_csv("output/PE_Firms.csv")
    pe_firms = df.to_dict(orient="records")
    portco_results = PortCo_Extraction(pe_firms)
    with open("output/PortCo_Results.json", "w") as f:
        json.dump(portco_results, f, indent=4)

