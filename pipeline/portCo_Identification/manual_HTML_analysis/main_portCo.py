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
from datetime import datetime


from step1_attempt1 import *
from step1_attempt2 import *
from step1_attempt3 import *
from step2_attempt1 import *
from step3_attempt1 import *
from step3_attempt2 import *
from step3_attempt3 import *
from step3_attempt4 import *
from helper_functions import *
from step3_helperFunctions import textCandidates_df, step3_attempt_image_src_global
from text_scoring import select_portcos_for_firm
from step1_csv_append import append_to_csv


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
    used_up = False  # Track if Google API quota is used up
    print("Starting PortCo Extraction for PE firms...")
    results = pd.DataFrame()
    current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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


        #######
        # Step 1: Finding portfolio subpage
        #######
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
            #try to use cached data if available
            try:
                web_df = pd.read_csv("output/PortCo_Website_Example.csv")
                cached_row = web_df[web_df['pe_firm_name'] == pe_firm['FullName']]
                if not cached_row.empty:
                    print("Using cached portfolio website data from output/PortCo_Website_Example.csv")
                    portfolio_website = {
                        "pe_firm_name": pe_firm["FullName"],
                        "step1_method": "Cached",
                        "website_found": cached_row.iloc[0]['website_found'],
                        "website_confidence": cached_row.iloc[0]['website_confidence']
                    }
            except Exception as e:
                print("No cached portfolio website data available.")


                print("All Step 1 attempts failed. Trying other PortCo Extractions..")
                print("NOTE: Due to the high flexibility of Step 1 Attempt 3 (Google Search just grabs the top result), it is likely that an error occurred within the implementation.")
            
                
        #######
        # Step 2: Finding classes that contain portCos
        #######
        if portfolio_website:
            print(f"Portfolio subpage found: {portfolio_website['website_found']}, via {portfolio_website['step1_method']}")
            print("Adding portfolio website info to portCo website csv...")
            append_to_csv(f"output/PortCo_Websites/{current_date}.csv", {
                "pe_firm_name": [portfolio_website["pe_firm_name"]],
                "step1_method": [portfolio_website["step1_method"]],
                "website_found":[portfolio_website["website_found"]],
                "website_confidence": [portfolio_website["website_confidence"]]
            })
            #using lists for pd DataFrame compatibility


            print("Now proceeding to Step 2 Attempt 1...")
            portco_class = step2_attempt_1(portfolio_website)
            if not portco_class:
                print(f"Step 2 Attempt 1 failed to find any portCo Classes, on the portfolio subpage: {portfolio_website['website_found']}")
                print("NOTE: Due to the high flexibility of Step 2 Attempt 1 (searching for any class name if all else fails), it is likely that an error occurred within the implementation if no portCo classes were found.")
            else:
                
                #######
                # Step 3: Extracting portCo names
                #######
                
                #
                # Update in step 3 procedure: Attempt 1 will be tried independently first, and then Attempt 2 will be tried to get A2_portcos for Attempts 3 and 4. Note that Attempts 2,3,4 are now more like 2.1,2.2,2.3 respectively,
                # as they are one big attempt to extract portCo names from the classes found in Step 2 Attempt 1.
                #
                candidates = None

                print(f"Step 2 Attempt 1 succeeded in finding portCo Classes, on the portfolio subpage: {portfolio_website['website_found']}")
                print("Now proceeding to Step 3 Attempt 1...")
                A1portcos = step3_attempt_1(portfolio_website, [c for c in portco_class['classes_found']])
                if not A1portcos:
                    print("Step 3 Attempt 1 failed to find any portCos from the portCo Classes found.")
                
                print("Now proceeding to the collation of text candidates by card...")

                A2_portcos = step3_attempt_2( portfolio_website, [c for c in portco_class['classes_found']])
                if not A2_portcos:
                    print("Step 3 Attempt 2 also failed to find any portCos from the portCo Classes found.")
                    print("At this stage, A2_portcos is required for Step 3 Attempt 3 and 4, so we cannot proceed further.")
                else:
                    print("Step 3 Attempt 2 succeeded in finding possible portCo Names, allowing attempts 3 and 4 to proceed.")
                    A3_cards = step3_attempt_3(A2_portcos)
                    candidates = step3_attempt_4(A3_cards)
                    print("Checking all images as well: considered attempt 5...")
                    soup = BeautifulSoup(requests.get(portfolio_website["website_found"]).text, "lxml")
                    if not soup:
                        print("Error fetching or parsing portfolio website HTML for image src extraction.")
                    else:
                        print(f"Successfully fetched and parsed portfolio website HTML from {portfolio_website['website_found']} for image src extraction.")
                        image_candidates = step3_attempt_image_src_global(soup, name_from_src) 
                   
                if candidates:
                    
                    dir_path = f"output/candidates/{current_date}"
                    Path(dir_path).mkdir(parents=True, exist_ok=True)
                    

                    print("DataFrame of text candidates below:")
                    textCandidates = textCandidates_df(candidates, image_candidates, dir_path, pe_firm['FullName'].replace(" ","_")) #prints head by default
                    # Having all the text candidates collated, we can now use the site confidence, class confidence, number of texts extracted from the given location, 
                    # name_hint value, and other heuristics to determine the final portCo names. Note that a key component of this is that all true portCo names from a given site should have identical surrounding html structure.
                    # Thus, we can group all texts by their html structure (card), and for a given PE firm, choose which collection cards (or one card) contains the portCo names. It is very unlikely that 
                    # two cards of different structures will combine to form the full set of portCo names for a given PE firm, as the listing of portCos is usually uniform in structure.
                    
                    #currently no difference between if A1portcos exist or not, but in future we can use A1portcos to help with scoring if they exist.
                    #reason: no A1 portcos found.
                    if A1portcos:
                        print("Now proceeding to scoring text candidates with A1 portCos available...")
                        used_up, nameResults = select_portcos_for_firm(textCandidates, pe_firm['FullName'], google_search, used_up)
                        if not nameResults.empty: #checking if not empty
                            print(f"Results after scoring with A1 portCos: {nameResults.head()}")
                            nameResults["PE_Firm_Name"] = pe_firm['FullName']
                            finalResults = nameResults["clean_text","PE_Firm_Name"].copy()
                            results = pd.concat([results, finalResults], ignore_index=True)
                        else:
                            print("No portCos selected after scoring with A1 portCos.")
                    else:
                        print("Now proceeding to scoring text candidates without A1 portCos...") 
                        used_up, nameResults = select_portcos_for_firm(textCandidates, pe_firm['FullName'], google_search, used_up)
                        if not nameResults.empty: #checking if not empty
                            print(f"Results after scoring with A1 portCos: {nameResults.head()}")
                            nameResults["PE_Firm_Name"] = pe_firm['FullName']
                            finalResults = nameResults[["clean_text","PE_Firm_Name"]].copy()
                            results = pd.concat([results, finalResults], ignore_index=True)
                        else:
                            print("No portCos selected after scoring without A1 portCos.")
                else:
                    print("Step 3 Attempt 4 failed to find any portCos from the portCo Classes found.")
                    print("Note: even if Step 3")
                
                
    
    
    return results

   





#writing this first to get overall structure:
if __name__ == "__main__":
    df = pd.read_csv("output/PE_Firms.csv")
    pe_firms = df.to_dict(orient="records") #meaning: list of dicts, where each dict is a row with column names as keys
    portco_results = PortCo_Extraction(pe_firms)
    portco_results.to_csv("output/PortCoName_Results_Cleaned.csv", index=False)
    
        
    #with open("output/PortCo_Results.json", "w") as f:
    #    json.dump(portco_results, f, indent=4)

