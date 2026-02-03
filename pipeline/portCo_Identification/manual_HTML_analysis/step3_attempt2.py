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
import lxml
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from .helper_functions import *
from .step3_helperFunctions import _norm, _domain, _name_matches, _collect_cards


"""

__Step 3: Extracting portCo names (various methods)__:
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int



__Step 3 Attempt 2__: Extracting portCo names (<a> inner text, img alt text, <figcaption> text):
Within the chosen html classes from 2.1, we will search for any <a> tags, and extract the inner text of those <a> tags as portCo names.
Then, search for any <img> tags, and extract the 'alt' text of those <img> tags as portCo names.
Then, search for any <figcaption> tags, and extract the inner text of those <figcaption> tags as portCo names.
If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.
Rank:
    A: if only <a> tags and below are found, within a class that is of rank A to B from 2.1.
    B: if only <img> tags and below are found, within a class that is of rank A to B from 2.1.
    C: if only  <figcaption> tags and below are found, within a class that is of rank A to B from 2.1.
    D: if only <a> tags and below are found, if lower ranks from 2.1 (C to E).
    E: if only <img> tags and below are found,  if lower ranks from 2.1 (C to E).
    F: if only <figcaption> tags and below are found, if lower ranks from 2.1 (C to E).


"""







def step3_attempt_2(portfolio_website: dict, portco_classes: list[dict]) -> list[dict]:
    
    try:
        response = requests.get(portfolio_website["website_found"], timeout=15)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, "lxml")
    except Exception as e:
        print(f"Error fetching or parsing portfolio website HTML: {e}")
        return None

    cards = _collect_cards(soup, portco_classes, 2)

    portcos_found = []
    
    for card_id, (card, class_used, rank, signals) in enumerate(cards):
        #print(f"Processing card {card_id} for Step 3 Attempt 2, class used: {class_used}, rank: {rank}")
        extracted_text = signals.get("extracted_text", {})
        portco_name = extracted_text.get("text", "").strip()
        if portco_name:
            if sum(ch.isalpha() for ch in portco_name) > 0:
                #print(f"Extracted portCo name: {portco_name} from card {card_id}")
                # Determine class confidence used
                class_confidence_used = None
                if rank in ["A","B"]:
                    if extracted_text.get("provenance") == "a_inner_text":
                        class_confidence_used = "A"  
                    elif extracted_text.get("provenance") == "img_alt_text":
                        class_confidence_used = "B"
                    else:
                        class_confidence_used = "C"
                else:
                    if extracted_text.get("provenance") == "a_inner_text":
                        class_confidence_used = "D"
                    elif extracted_text.get("provenance") == "img_alt_text":
                        class_confidence_used = "E"
                    else:
                        class_confidence_used = "F"

                portcos_found.append({
                    
                    "soup_object": card,
                    "name": portco_name,
                    "raw_text": extracted_text.get("text", ""), #this is very important for debugging
                    "step3_method": 2,
                    "portco_name_hint": signals.get("name_hint"),
                    #portCo confidence rank to be determined later, as it depends on multiple factors
                    "portCo_confidence_rank": class_confidence_used, #for now, same as class confidence used. 
                    "attempt2_specific_info": {
                        "card_id": card_id,
                        "provenance": extracted_text.get("provenance"),
                        "class_used": class_used,
                        "class_confidence_used": class_confidence_used,
                        #now universal info for src and href
                        "url": extracted_text.get("url"),
                        "tag_name": extracted_text.get("tag_name"),
                        "link_attr": extracted_text.get("link_attr"),

                        
                    }   
                    
                })

            #print(f"PortCo found in Step 3 Attempt 2: {portco_name}, via class: {class_used}, rank: {class_confidence_used}")
    
       
    if not portcos_found:
        print("No portCos found in Step 3 Attempt 2.")
        return None
    return portcos_found
    
