import os
try:
    from playwright.sync_api import sync_playwright, Error
    import playwright
except Exception:
    sync_playwright = None
    Error = Exception
    playwright = None
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



__Step 3 Attempt 3__: Extracting portCo names ('src' values):
From the 'src' values obtained in 2.1, we will extract the portCo names.
Now, the 'src' value seems to be an upload hyperlink that contains the name of the portCo right after or a couple of back slashes after the substring '/uploads'.
As a result, we will extract the substring of the 'src' values that:
    Rank:
    (for A,B from 2.1):
    A: is the first non-numerical component after '/uploads' (only alphabetic), and bounded to the right by either a hyphen, underscore, or file extension (., jpg, png, svg, etc).
    (Only reason this is Attempt 3 is because it is brittle, but given the high reliability of 2.1 A,B classes, if it is found then it has high confidence).
    (otherwise for C-E from 2.1, E, due to the fact that 'src' values may contain many non-portCo images):




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

"""

from collections import defaultdict






def group_candidates_by_card(A2_portCos):
    """
    Group Attempt 2 portCos by their card identifier, so we can reference them in Attempt 3, and then for a given text,
    use texts in the same card to estimate confidence.
    """
    
    #using lambda function to initialize default, customised structure.
    #changed srcTexts and hrefTexts to dicts to store the raw url along with the text
    cards = defaultdict(lambda: {"texts": [], "meta": {}, "srcTexts": {}, "hrefTexts": {}})

    for portco in A2_portCos:
        if portco.get("step3_method") != 2:
            continue  # Skip non-Attempt 2 portCos
    
        info = portco.get("attempt2_specific_info", {})
        card_id = info.get("card_id")
        if card_id is None:
            continue  # Skip if no card_id is found

        if not cards[card_id]["meta"]:
            cards[card_id]["meta"] = {
                "class_used": info.get("class_used"),
                "class_rank": info.get("class_confidence_used")
            }   
        


        cards[card_id]["texts"].append(portco)#appending full portco dict for later reference
    
    return cards

def name_from_src(src: str, image_mode = False) -> list[str]|str|None:
    """
    Given a src string:
    ALGORITHM:
    1. Parse the src through urlparse, and extract the path component.
    2. find the index of '/uploads/' in the path, if present.
    3. If found:
        a) set path_after_uploads to the substring after '/uploads/' (path[idx + len('/uploads/'):])
    4. else:
        a) set path_after_uploads to path.split('/')[-1] (last component of path)

    5. Split path_after_uploads by '/' to get components.
    6. For each component:
        a) Remove file extensions using re.sub.
        b) If the cleaned component has more than 3 alpahabetic characters, (use .isalpha() and iterate through the chars), as well as not containing numbers, set that as the candiate name.
        c) Break the loop, or continue if in image mode to collect all candidates.
    7. use re.sub to replace hyphens and underscores with spaces in the candidate name.
    8. If not image mode, return the normalised candidate name (using _norm function) within a list, else return a list of all candidate names found in image mode.
    9. If no candidate name found, return None.

    """    

    if not src:
        return None

    parsed = urlparse(src)
    path = parsed.path or ""
    lower = path.lower()



    # Prefer the portion after /uploads/, if present
    idx = lower.find("/uploads/")
    if idx != -1:
        path_after = path[idx + len("/uploads/"):]
    else:
        idx = lower.find("/portfolio/")
        if idx != -1:
            path_after = path[idx + len("/portfolio/"):]
        else:
            if image_mode:
                idx = lower.find("//")
                path_after = path[idx + len("//"):]
            else:
                # fallback: use the last segment of the path
                path_after = path.split("/")[-1]



    segments = [seg for seg in path_after.split("/") if seg]
    if not segments:
        return None

    candidate_seg = None
    cand_segs = []
    # Find the first segment that looks at least vaguely like a name.
    for seg in segments:
        # remove file extension
        base = re.sub(r"\.[a-zA-Z0-9]+$", "", seg)
        # need some letters, not all digits
        if sum(ch.isalpha() for ch in base) >= 3 and not base.isdigit():
            candidate_seg = base
            if not image_mode:
                break
            else:
                cand_segs.append(base)

    if not candidate_seg:
        return None

    # Bound by hyphen, underscore, or dot as you described
    # (first non-numeric component, only alphabetic-ish)
    if image_mode and cand_segs:
        for i,cs in enumerate(cand_segs):
            cand_segs[i] = re.split(r"[.]", cs)[0]
            if "//" in cand_segs[i]:
                cand_segs[i] = cand_segs[i].split("//")[0]
            cand_segs[i] = re.sub(r"[-_]+", " ", cand_segs[i])  # replace hyphens/underscores with spaces
            cand_segs[i] = cand_segs[i].strip()
            
        return [ _norm(cs) for cs in cand_segs if cs]

    if 'logo' in candidate_seg.lower():
        #likely in the same segment as cand name from manual examination
        cand_list = re.split(r"[.]", candidate_seg)
        for cs in cand_list:
            if 'logo' in cs.lower():
                base = cs
                base = base.replace('logo','')
                break
    else:
        base = re.split(r"[.]", candidate_seg)[0]
        
    base = re.sub(r"[-_]+", " ", base)  # replace hyphens/underscores with spaces
    base = base.strip()

    # Normalise, you can add titlecasing if you want:
    return _norm(base)
    


def step3_attempt_3(A2_portCos: list) -> list[dict]:
    
    
    cards = group_candidates_by_card(A2_portCos)

    for cls in cards.values():
        for i,portCo in enumerate(cls.get("texts", [])):
             
            if portCo.get("step3_method") != 2:
                continue  # Skip non-Attempt 2 portCos

            info = portCo.get("attempt2_specific_info", {})
            
            if info.get("link_attr") != "src":
                continue  # Skip non-src portCos
        
            src = info.get("url")
            srcText = name_from_src(src)
            if srcText:
                #print(f"Extracted srcText: {srcText} from src: {src} from text {i} in card {info.get('card_id')}") 
                cls["srcTexts"][srcText] = {"text": src, "soup_object": portCo.get("soup_object")}

    return cards
