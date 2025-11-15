import os
import time
from bs4 import BeautifulSoup
import lxml
from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests
from urllib.parse import urljoin
from dotenv import load_dotenv


from step1_attempt1 import *
from step1_attempt2 import *
from step1_attempt3 import *
from step2_attempt1 import *
from step3_attempt1 import *
from step3_attempt2 import *
from step3_attempt3 import *
from step3_attempt4 import *
from helper_functions import *

load_dotenv()  # Load environment variables from .env file
API_KEY = os.getenv("API_KEY")
CX = os.getenv("CX")
if not API_KEY or not CX:
    raise ValueError("Google API Key and CX must be set in environment variables.")

def PortCo_Extraction(pe_firms: list[dict]) -> list[dict]:
    """
    Goes through attempts for each step, returning a list of dicts, where the dict will contain a list of dicts for the portCos for each PE firm.
    Within each element of the overall list, the dict will have keys:
        'firm_name': str, 'step1_method': int, 'website_found': str, 'website_confidence': int, 'portcos': list[dict] (for attempts 1,2 of step 1, 'website_found' will be the portfolio subpage used, for attempt 3 of step 1, it will be the googled website (also possibly portfolio subpage), 'step1_method' is the int of the attempt number).
    
    Each element of the 'portcos' list will be a dict with keys:
        'portco_name': str, 'step3_method_used': int, 'class_confidence_used': int, 'extraction_confidence': int (for attempts 1,2 of step 3, 'extraction_method' will be the int of the attempt number).

    """
    print("Starting PortCo Extraction for PE firms...")
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
                    print(f"PortCos found: {[pc['name'] for pc in portcos]}")
                    results.append({
                        "firm_name": pe_firm["FullName"],
                        "step1_method": portfolio_website["step1_method"],
                        "website_found": portfolio_website["website_found"],
                        "website_confidence": portfolio_website["website_confidence"],
                        "portcos": portcos
                        #structure 
                    })

    return results

   





#writing this first to get overall structure:
if __name__ == "__main__":
    df = pd.read_csv("output/PE_Firms.csv")
    pe_firms = df.to_dict(orient="records")
    portco_results = PortCo_Extraction(pe_firms)
    with open("output/PortCo_Results.json", "w") as f:
        json.dump(portco_results, f, indent=4)

