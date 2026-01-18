from helper_functions import *
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
__Step 1 Attempt 1__: Accessing portfolio subpage (direct):
From a given PE firm's website, access the portfolio subpage:
    Rank:
    A: firm["website"]+"/(portfolio|Portfolio|investments|Investments|companies|Companies|funds|Funds)".
    B: firm["website"]+"/(holdings|Holdings|businesses|Businesses)".

"""


def step1_attempt_1(pe_firm: dict) -> dict | None:
    from urllib.parse import urljoin

    subpage_patterns = [
        ("portfolio", "A"),
        ("investments", "A"),
        ("companies", "A"),
        ("funds", "A"),
        ("holdings", "B"),
        ("businesses", "B"),
        # common variants
        ("our-companies", "A"),
        ("portfolio-companies", "A"),
    ]

    base_url = pe_firm["Website"].rstrip("/")

    for subpath, confidence in subpage_patterns:
        candidate_url = urljoin(base_url + "/", subpath)  # tries both /portfolio and /portfolio/
        accessible, final_url = check_page_accessible(candidate_url)
        if accessible:
            print(f"Accessible portfolio subpage found with Attempt 1: {final_url}")
            return {
                "pe_firm_name": pe_firm["FullName"],
                "step1_method": "Attempt 1",
                "website_found": final_url,
                "website_confidence": confidence
            }
        else:
            candidate_url = urljoin(base_url + "/", subpath) + "/"  # try with trailing slash
            accessible, final_url = check_page_accessible(candidate_url)
            if accessible:
                print(f"Accessible portfolio subpage found with Attempt 1: {final_url}")
                return {
                    "pe_firm_name": pe_firm["FullName"],
                    "step1_method": "Attempt 1",
                    "website_found": final_url,
                    "website_confidence": confidence
                }

    return None
