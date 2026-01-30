from step1_attempt1 import *

from helper_functions import *
import os
from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests
from urllib.parse import urljoin, urlparse
import time

def step1_attempt_2(pe_firm: dict) -> dict:
    """
    __Step 1 Attempt 2__: Accessing portfolio subpage (indirect):
    Some PE firms are not only PE firms, but also have venture capital arms, or growth equity arms. As a result, there may exist no portfolio subpage on the main website.
    In such cases, we will attempt to access the portfolio subpage from the PE firm's website, by entering the PE subpage of site, if available in
    Rank: 
        A: firm["website"]+"/(privateequity|private-equity|pe)" or firm["website"].split(".")[1] + ("privateequity"|"pe"|"investments"|"portfolio") + {".com",".com.au"} (case insensitive).
        (NOTE: The above attempts are done more securely than what is displayed in the docs; see the actual code for implementation)
        Then from the PE subpage, if found using privateequity|pe we will attempt to access the portfolio subpage using the same approach as in Step 1 Attempt 1
        If found using investments|portfolio, we will assume that is the portfolio subpage.
   
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
            candidate_url_slash = urljoin(base_url + "/", subpath) + "/"
            
        else:
            #remove www. if present for domain extraction
            parsed_url = urlparse(base_url)
            domain = parsed_url.netloc.replace("www.", "")
            candidate_url = urljoin(domain,subpath)
            candidate_url_slash = urljoin(domain,subpath) + "/"
            hyphen_candidate = urljoin(domain + "-",subpath)

        try:
            # Make a lightweight HEAD request (no full page download)
            # requests.head() asks the website for headers only, to check if the page exists
            isAccessible, final_url = check_page_accessible(candidate_url)
            
            cands = [check_page_accessible(x) for x in [candidate_url, candidate_url_slash,hyphen_candidate]]

            isAccessible = False
            for tup in cands:
                isAccessible, final_url = tup
                if isAccessible:
                    break
            if isAccessible:
                if doAttempt1:
                    # replace current url with final_url from HEAD request
                    print(f"Accessible PE subpage found with Attempt 2: {final_url}")
                    df = pd.read_csv("output/PE_Firms.csv")
                    df.loc[df["FullName"] == pe_firm["FullName"], "Website"] = final_url
                    df.to_csv("output/PE_Firms.csv", index=False)

                    # Now attempt Step 1 Attempt 1 on this subpage
                    subpage_result = step1_attempt_1({"Website": final_url})
                    if subpage_result:
                        return subpage_result
                    else:
                        continue  # proceed to next pattern if Step 1 Attempt 1 fails
                
                return {
                    "pe_firm_name": pe_firm["FullName"],
                    "step1_method": "Attempt 2",
                    "website_found": final_url,
                    "website_confidence": confidence
                }
        except requests.RequestException:
            continue  # skip if timeout or connection error

    return None
