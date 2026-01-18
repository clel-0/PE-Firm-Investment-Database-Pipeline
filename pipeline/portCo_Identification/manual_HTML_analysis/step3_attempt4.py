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
from step3_helperFunctions import _norm, _domain, _name_matches



"""

__Step 3: Extracting portCo names (various methods)__:
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int


__Step 3 Attempt 4__: Extracting portCo names (href links):
Scrape the chosen html classes for href links containing the following subsets of words. We will rank the subsets by reliability:
    Rank:
    (A,B from 2.1): 
    A = {"investments", "portfolio", "companies", "investment-portfolio"}
    B = {"company", "funds"}
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


HREF_ANCHORS_A = {"investments", "portfolio", "companies", "investment-portfolio"}
HREF_ANCHORS_B = {"company", "funds"}


def name_from_href(href: str) -> tuple[str|None,str]:
    """
    ALGORITHM:
    1) Split the href into components using '/' as the delimiter.
    2) for each component, check if the component matches any words in HREF_ANCHORS_A, and is no the last component.
        If a match is found, set the next component as the candidate, and rank 'A'. Break the loop.
    3) If no match found in step 2, repeat for HREF_ANCHORS_B, and if found set rank to 'B', breaking the loop.
    4) If no match found in step 3, set the last component as the candidate, and rank 'C'.
    5) Clean the candidate by:
        - removing file extensions (re.sub() with anything after a dot at the end)
        - replacing hyphens and underscores with spaces
        - require at least 2 alphabetic characters
    6) If the cleaned candidate is valid, return it along with the rank. Otherwise return None.
    
    """
    
    if not href:
        return None, "C"

    parsed = urlparse(href)
    path = parsed.path or ""

    # Split path into segments
    segments = [seg for seg in path.split("/") if seg]
    lower_segments = [seg.lower() for seg in segments]

    candidate = None
    pattern_rank = "C"  # default fallback

    # ----- Try A-patterns -----
    for i, seg in enumerate(lower_segments):
        if seg in HREF_ANCHORS_A and i + 1 < len(segments):
            candidate = segments[i + 1]
            pattern_rank = "A"
            break

    # ----- Try B-patterns -----
    if candidate is None:
        for i, seg in enumerate(lower_segments):
            if seg in HREF_ANCHORS_B and i + 1 < len(segments):
                candidate = segments[i + 1]
                pattern_rank = "B"
                break

    # ----- Fallback: last segment -----
    if candidate is None and segments:
        candidate = segments[-1]
        pattern_rank = "C"

    if not candidate:
        domain = _domain(href)
        candidate = domain.split('.')[0]  # Take first part of domain
        pattern_rank = "D"
        
        if not candidate:
            return None, pattern_rank

    # Remove file extension
    base = re.sub(r"\.[a-zA-Z0-9]+$", "", candidate)

    # Replace hyphens and underscores with spaces
    base = re.sub(r"[-_]+", " ", base).strip()

    # Require some alphabetic content
    if sum(ch.isalpha() for ch in base) < 2:
        return None, pattern_rank

    return _norm(base), pattern_rank


    


def step3_attempt_4(cand_by_card: dict) -> list[dict]:
    

    for cls in cand_by_card.values():
        for i,portCo in enumerate(cls.get("texts", [])):
             
            if portCo.get("step3_method") != 2:
                continue  # Skip non-Attempt 2 portCos

            info = portCo.get("attempt2_specific_info", {})
            
            if info.get("link_attr") != "href":
                continue  # Skip non-src portCos
        
            href = info.get("url")
            hrefText = name_from_href(href)
            if hrefText:
                #print(f"Extracted hrefText: {hrefText} from href: {href} from text {i} in card {info.get('card_id')}") 
                cls["hrefTexts"][hrefText[0]] = {"text": (href, hrefText[1]), "soup_object": portCo.get("soup_object")}
                #note: hrefText is a tuple (name, rank), we only want the name here. This will also be important for confidence ranking later.
    return cand_by_card
