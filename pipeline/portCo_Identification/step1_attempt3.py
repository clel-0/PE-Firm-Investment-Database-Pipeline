from helper_functions import *
from step1_attempt1 import *
from step1_attempt2 import *
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
"""
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
"""

def step1_attempt_3(pe_firm: dict) -> dict:
    """
    Use the Google Custom Search API to search for the portfolio subpage, by searching for 
    Rank:
    A: site:{firm['website']} (portfolio|investments)

    and access the top result.
    Returns:
        {
            "pe_firm_name": pe_firm["FullName"],
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
                    "pe_firm_name": pe_firm["FullName"],
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

    
    