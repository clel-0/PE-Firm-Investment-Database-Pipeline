
from helper_functions import *
from step1_attempt1 import *
from step1_attempt2 import *
from step1_attempt3 import *
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
import lxml
from bs4 import BeautifulSoup


def step2_attempt_1(portfolio_website: dict) -> dict[list[dict]]:
    
    """
    __Step 2 Attempt 1__: Accessing appropriate html classes to find portCos (names and logos):
    Within the portfolio subpage html, record all the inner texts with the label "src", that are within a class
    with a name containing any of the following. We will rank subsets of words by how strongly they indicate the presence of portfolio companies:
        Rank:
        A: {'Portfolio' and 'Card'}, {'Portfolio' and 'Item'}, {'Investment' and 'Card'}, {'Investment' and 'Item'}, {'Investment' and 'box'}, {'Investment' and 'box'} (case insensitive).
        B: {'Portfolio'}, {'Investment'}, {'Company'} (case insensitive).
        C: {'item'}, {'box'}, {'card'}, {'logo'} (case insensitive).
        D: any class name, but with any of the words within A to C present in the inner text of the class.
        E: any class name.
        
    Only ranks A to C will be considered, and D,E will only be used as a last resort if no portCos are found in A to C.

    
    Returns dict for each PE firm that contains:
        'classes_found': list[dict], 'class_confidence': int
        where each dict in 'classes_found' has keys:
            'class_rank': int, 'class_path': str

    """

    RANK_SETS = {
    "A": [("portfolio", "card"), ("portfolio", "item"),
          ("investment", "card"), ("investment", "item"),
          ("investment", "box")],
    "B": [("portfolio",), ("investment",), ("company",)],
    "C": [("item",), ("box",), ("card",), ("logo",)],


    } 

    # avoid obvious noise containers
    CLASS_BLACKLIST = re.compile(
    r"(footer|header|nav|menu|cookie|subscribe|social|share|breadcrumb|search|hero|banner|modal|popup)",
    re.I,
    )  


    def _class_rank(class_list):
        """Return 'A'/'B'/'C' or None based on class tokens (substring match)."""
        if not class_list:
            return None
        tokens = [c.lower() for c in class_list if isinstance(c, str)]
        if any(CLASS_BLACKLIST.search(t) for t in tokens):
            return None

        def has_all(words):
            # any token containing each word (substring)
            return all(any(w in t for t in tokens) for w in words)

        for rank in ("A", "B", "C"):
            for words in RANK_SETS[rank]:
                if has_all(words):
                    return rank
        return None

    #helper function to determine class rank
    def extract_candidate_classnames(html: str):
        """
        Parse HTML and return unique class names per rank.
        Output:
        {
            "A": [...],
            "B": [...],
            "C": [...],
            "stats": {"A": nA, "B": nB, "C": nC, "total_elements_scanned": N}
        }
        """
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            print(f"Error parsing HTML with BeautifulSoup: {e}")
            print("Returning empty class buckets.")
            return {"A": [], "B": [], "C": [], "stats": {"A": 0, "B": 0, "C": 0, "total_elements_scanned": 0}}
        buckets = {"A": set(), "B": set(), "C": set()}
        scanned = 0
        #looking through all elements with a class attribute
        for e in soup.find_all(True):
            scanned += 1
            cls = e.get("class")
            r = _class_rank(cls)
            if r:
                # store the literal class attribute string (space-joined)
                buckets[r].add(" ".join(cls))

        # sort for stable output
        out = {k: sorted(list(v)) for k, v in buckets.items()}
        out["stats"] = {
            "A": len(out["A"]),
            "B": len(out["B"]),
            "C": len(out["C"]),
            "total_elements_scanned": scanned,
        }
        print(f"Class extraction stats for {portfolio_website['website_found']}: {out['stats']}")
        return out
    


    try:
        response = requests.get(portfolio_website["website_found"], timeout=15)
        response.raise_for_status()
        html_content = response.text

        class_buckets = extract_candidate_classnames(html_content)
        classes_found = []
        for cls in class_buckets["A"]:
            classes_found.append({"class_rank": "A", "class_path": cls})
        for cls in class_buckets["B"]:
            classes_found.append({"class_rank": "B", "class_path": cls})
        for cls in class_buckets["C"]:
            classes_found.append({"class_rank": "C", "class_path": cls})
        
        if not classes_found:
            print(f"No portCo-related classes found on portfolio subpage for Step 2 (Screening for classes): {portfolio_website['website_found']}.")
            return None
        else:
            return {"classes_found": classes_found} 


    except requests.RequestException as e:
        print(f"Error accessing portfolio subpag for Step 2 (Screening for classes): {portfolio_website['website_found']}. Error: {e}")
        return None

