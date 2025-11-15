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





    
