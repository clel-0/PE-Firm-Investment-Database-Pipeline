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
from helper_functions import *


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

#helper function to extract inner text

def inner_text(el, tag:str, link_type:str, provenance:str):
    texts = []
    for t in el.find_all(tag):
        text = inner_text_logic(t, link_type, provenance)
    if text:
            #if not t.get(link_type):
                
                #print("__________")
                #print(f"Warning: <{t.name}> tag with no {link_type} found in element with classes: {' '.join(cls)}")
            texts.append({"text": _norm(text), "raw_text": text, "url": t.get(link_type), "provenance": provenance, "tag_name": t.name, "link_attr": link_type})
            #print("__________")
            #print(f"Found anchor text: {text} in element with classes: {' '.join(cls)}")

    return texts


#need this for the GNN extraction
def inner_text_logic(t:str, link_type:str, provenance:str):
    if t.name == "a":   
        text = t.get_text(strip=True)
        #print(f"text found in <a>: {text}")
    if t.name == "img":
        text = t.get("alt", "").strip()
        #print(f"text found in <img>: {text}")
    if t.name == "figcaption":
        text = t.get_text(strip=True)
        #print(f"text found in <figcaption>: {text}")
        
    if text:
        return text
    return None
        
    


def _collect_cards(soup, card_class_tokens, attempt_num=1):
    """
    takes a BeautifulSoup object (soup) derived from the html of the PE firm site, and a list of class tokens (card_class_tokens) found from step 2, as the input parameters.
    attempt_num: 1 = basic (for JSON-LD), 2 = full inner-text extraction for step 3.
    ALGORITHM:
    1) lowercase all the class tokens provided in card_class_tokens and stores them in a set called tokens. 
    2) initialize an empty list called cards to store the matched card elements.
    3) for each element (tag) in the soup that has a class attribute:
        a) get the list of class names within that element (cls).
        b) if any of the classnames found in step 2 (tokens) are present in the class names of the element (cls), then:
            i) extract signals from the element:
                - find the first anchor tag within the element and get its href attribute (href).
                - find the first img tag within the element and get its src attribute (img).
                - extract the domain from the href and img URLs using the _domain helper function (link_dom, img_dom).
                - extract rank of the class (cls_rank) by checking which token matched and taking the highest rank among them.
                - attempt to extract a name hint from common title-like nodes within the element (name_hint):
                    * check for elements with aria-label, img alt attributes, h1-h4 tags, and common class names like title or name.
                    * if found, normalize the text content using _norm() and store it in name_hint, then break the loop. 
                    (Note: this name_hint is weak in confidence as it may not always correspond to the portCo name,
                    namely we are just traversing through the alts and headings).

            ii) if for the first attempt of step 3:
                - append a tuple of (element, joined class string, signals dict) to the cards list.
            iii) if for the second attempt of step 3:
                - take text from <a>, <img>, and <figcaption> tags within the element, and store them along with their provenance in the signals dict.
                - for each extracted text, append a tuple of (element, joined class string, signals dict with extracted text) to the cards list.
    
    4) Return cards list.

            

    
    """

    tokens = set()
    for cls_str in card_class_tokens:
        # split the big "summary-item summary-item-record-type-image ..." into pieces
        for t in cls_str["class_path"].split():
            tokens.add((t.lower(),cls_str["class_rank"]))  # also keep track of rank
    if not tokens:
        print ("No class tokens provided for card extraction. Note that this means step 2 must have failed.")
        return []
    cards = []
    #looking through all elements with a class attribute
    #the find_all method of BeautifulSoup is used to find all HTML elements that have a class attribute in this case, as its first argument collates all tags, and the second argument specifies the tag must have a class attribute.
    for el in soup.find_all(True, class_=True):
        cls = [c for c in el.get("class") if isinstance(c, str)]
        lowered = [c.lower() for c in cls]
        if any(tok[0] in lowered for tok in tokens):
            # signals: anchor & image domains + visible title-ish text
            a_tag = el.find("a", href=True)
            href = a_tag["href"] if a_tag else ""
            img_tag = el.find("img", src=True)
            img = img_tag["src"] if img_tag else ""
            link_dom = _domain(href)
            img_dom  = _domain(img)
            cls_rank = "E"  # default lowest
            for tok in tokens:
                #maximize rank
                if tok[0] in lowered and tok[1] < cls_rank:
                    cls_rank = tok[1]
            
                    


            
            # quick name hint from typical title nodes or alt
            name_hint = None
            for sel in ["[aria-label]","img[alt]","h1","h2","h3","h4",".title",".name","strong"]:
                node = el.select_one(sel)
                if node:
                    #try to get aria-label then inner text then alt attribute
                    name_hint = _norm(node.get("aria-label") or getattr(node, "get_text", lambda *_: "")(" ") or node.get("alt"))
                    if name_hint: break
                #these will be used as reasoning for matching later on (in extract_portcos_from_jsonld)
            
            
            if attempt_num == 1:
                # basic extraction for attempt 1
                cards.append((el, " ".join(cls), cls_rank, {"link_domain":link_dom, "img_domain":img_dom, "name_hint":name_hint}))



            elif attempt_num == 2:
                # full detail extraction for attempt 2

                #____1____#
                # Search for any <a> tags, and extract the inner text of those <a> tags as portCo names.
                ###########
                inner_texts = inner_text(el, "a", "href", "a_inner_text")

                #____2____#
                # Search for any <img> tags, and extract the 'alt' text of those <img> tags as portCo names.
                ###########
                inner_texts.extend(inner_text(el, "img", "src", "img_alt_text"))
                
                #____3____#
                # Search for any <figcaption> tags, and extract the inner text of those <figcaption> tags as portCo names.
                ###########
                inner_texts.extend(inner_text(el, "figcaption", "src", "figcaption_text"))




                if inner_texts:
                    for it in inner_texts:
                        cards.append((el, " ".join(cls), cls_rank, {"link_domain":link_dom, "img_domain":img_dom, "name_hint":name_hint, "extracted_text": it}))
    return cards



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


def _name_matches(a, b):
    """
    Checks if to strings match regardless of formatting differences, through normalization and lowercasing.
    Additionally, accepts strong substring matches where one string is contained within the other and is at least 3 characters long.
    """
    if not a or not b: return False
    aa, bb = _norm(a).lower(), _norm(b).lower()
    if aa == bb: return True
    # Accept strong substring containing whole words
    print(f"Checking name match between '{aa}' and '{bb}', they are not exactly equal.")
    return (aa in bb and len(aa) >= 3) or (bb in aa and len(bb) >= 3)


import pandas as pd
def textCandidates_df(candidates, image_candidates, filePath, PE_name) -> pd.DataFrame: 
    import pandas as pd
    """
    Reminder of structure of candidates:
    { card_id:
        {
            "texts": [
                portco
            ],

            "meta": {
                "class_used": str,
                "class_rank": str
            }, 
            
            "srcTexts": {
                portco_name: {"text": raw_href_url, "soup_object": card}
            },

            "hrefTexts": {
                portco_name: {"text": (raw_href_url,rank), "soup_object": card}
            }
        }
    }

    where portco is of structure: 
    {
    "soup_object": card,
    "name": portco_name,
    "raw_text": extracted_text.get("text", "")
    "step3_method": 2,
    "portCo_confidence_rank": class_confidence_used, 
    "attempt2_specific_info": {
        "card_id": card_id,
        "provenance": extracted_text.get("provenance"),
        "class_used": class_used,
        "class_confidence_used": class_confidence_used,
        "url": extracted_text.get("url"),
        "tag_name": extracted_text.get("tag_name"),
        "link_attr": extracted_text.get("link_attr"),
    }
    _____________________________________________________________________

    Structure of the DataFrame to be produced:
    Columns:
    [card_id, text, raw_text, type: {inner: {a, img figcaption}, src, href}, rank, soup_object]
    (where {} brackets indicate options for discrete values)


    """
    
    rows = []
    for card_id, card in candidates.items():
        texts = card.get("texts", [])
        for portco in texts:
            
            text = portco.get("name")
            raw_text = portco.get("raw_text")
            typ = portco.get("attempt2_specific_info", {}).get("provenance")
            rank = portco.get("portCo_confidence_rank")
            soup_object = portco.get("soup_object")
            rows.append({
                "card_id": card_id,
                "text": text,
                "raw_text": raw_text,
                "type": typ,
                "rank": rank,
                "soup_object": soup_object
            })

        #check srcTexts
        for src_text, src_url in card.get("srcTexts", {}).items():
            rows.append({
                "card_id": card_id,
                "text": src_text,
                "raw_text": src_url.get("text"),
                "type": "src",
                "rank": card.get("meta", {}).get("class_rank"), #using class rank as src rank
                "soup_object": src_url.get("soup_object")
            })
        #check hrefTexts
        for href_text, href_url in card.get("hrefTexts", {}).items():
            rows.append({
                "card_id": card_id,
                "text": href_text,
                "raw_text": href_url["text"][0] or "",  #href_url is a tuple (name, rank)
                "type": "href",
                "rank": href_url["text"][1] or "",  #href_text is a tuple (name, rank)
                "soup_object": href_url.get("soup_object") or None
            })
    
    for i,img_portco in enumerate(image_candidates):
        rows.append({
            "card_id": i + len(rows),
            "soup_object": img_portco.get("soup_object"),
            "text": img_portco.get("name"),
            "raw_text": img_portco.get("raw_text"),
            "type": "image_src",
            "rank": img_portco.get("portCo_confidence_rank")
        })


    df = pd.DataFrame(rows)
    print("Text candidates DataFrame head:")
    print(df.drop("soup_object", axis=1).head())
    #save to CSV
    df.drop("soup_object", axis=1).to_csv(os.path.join(filePath,f"{PE_name}.csv"), index=False)
    print(f"Text candidates DataFrame saved to {PE_name}.csv")
    return df


def step3_attempt_image_src_global(soup,name_from_src) -> list[dict]:
    """
    Attempt N: global image src scan.
    Look at *all* <img src=...> tags on the page, try to extract portCo-like names
    from the src URL via name_from_src(), and return them as low-rank candidates.
    """
    candidates = []

    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        name = name_from_src(src,image_mode=True)
        if not name:
            src = img.get("data-src", "")  # try data-src as fallback
            name = name_from_src(src,image_mode=True)
        if not name:
            continue
        for n in name:
            candidates.append({
                
                "soup_object": img,
                "name": n,
                "raw_text": src,             # the raw URL
                "step3_method": 5,           # or whatever attempt number
                "portCo_confidence_rank": "I",  # mark as image-based, low-ish rank
                "attempt_image_src_info": {
                    "src_url": src,
                    "alt": img.get("alt"),
                    "tag_name": "img",
                    "card_id": None,         # we don't have card structure here
                },
            })
    return candidates