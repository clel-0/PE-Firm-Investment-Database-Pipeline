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
from urllib.parse import urljoin
import time

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
                    "pe_firm_name": pe_firm["FullName"],
                    "step1_method": "Attempt 2",
                    "website_found": final_url,
                    "website_confidence": confidence
                }
        except requests.RequestException:
            continue  # skip if timeout or connection error

    return None
