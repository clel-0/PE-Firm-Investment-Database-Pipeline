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
from step3_attempt1 import _norm, _domain


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
If no <a> tags are found, we will search for any <img> tags, and extract the 'alt' text of those <img> tags as portCo names.
If no <img> tags are found, we will search for any <figcaption> tags, and extract the inner text of those <figcaption> tags as portCo names.
If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.
Rank:
    A: if <a> tags are found, within a class that is of rank A to B from 2.1.
    B: if <img> tags are found, within a class that is of rank A to B from 2.1.
    C: if <figcaption> tags are found, within a class that is of rank A to B from 2.1.
    D: if <a> tags are found, if lower ranks from 2.1 (C to E).
    E: if <img> tags are found,  if lower ranks from 2.1 (C to E).
    F: if <figcaption> tags are found, if lower ranks from 2.1 (C to E).


"""


#this will also be used in step 3 attempt 2.py and step 3 attempt 3.py
def _collect_cards(soup, card_class_tokens):
    """
    takes a BeautifulSoup object (soup) derived from the html of the PE firm site, and a list of class tokens (card_class_tokens) found from step 2, as the input parameters.
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
                - attempt to extract a name hint from common title-like nodes within the element (name_hint):
                    * check for elements with aria-label, img alt attributes, h1-h4 tags, and common class names like title or name.
                    * if found, normalize the text content using _norm() and store it in name_hint, then break the loop. 
                    (Note: this name_hint is weak in confidence as it may not always correspond to the portCo name,
                    namely we are just traversing through the alts and headings).

            ii) append a tuple of (element, joined class string, signals dict) to the cards list.
    4) Return list of (el, class_string, signals_dict) for candidate cards.
    
    """

    tokens = set(c.lower() for c in card_class_tokens)
    cards = []
    #looking through all elements with a class attribute
    #the find_all method of BeautifulSoup is used to find all HTML elements that have a class attribute in this case, as its first argument collates all tags, and the second argument specifies the tag must have a class attribute.
    for el in soup.find_all(True, class_=True):
        cls = [c for c in el.get("class") if isinstance(c, str)]
        if any(tok in (c.lower() for c in cls) for tok in tokens):
            # signals: anchor & image domains + visible title-ish text
            href = (el.find("a", href=True) or {}).get("href") if el.find("a", href=True) else ""
            img  = (el.find("img", src=True) or {}).get("src") if el.find("img", src=True) else ""
            link_dom = _domain(href)
            img_dom  = _domain(img)
            # quick name hint from typical title nodes or alt
            name_hint = None
            for sel in ["[aria-label]","img[alt]","h1","h2","h3","h4",".title",".name","strong"]:
                node = el.select_one(sel)
                if node:
                    name_hint = _norm(node.get("aria-label") or getattr(node, "get_text", lambda *_: "")(" ") or node.get("alt"))
                    if name_hint: break
            #these will be used as reasoning for matching later on (in extract_portcos_from_jsonld)
            cards.append((el, " ".join(cls), {"link_domain":link_dom, "img_domain":img_dom, "name_hint":name_hint}))
    return cards


def step3_attempt_2(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass
