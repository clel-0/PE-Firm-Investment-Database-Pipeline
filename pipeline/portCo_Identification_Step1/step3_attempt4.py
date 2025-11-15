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


__Step 3 Attempt 4__: Extracting portCo names (href links):
If 3.3 fails to find any portCos, we will scrape the chosen html classes for href links containing the following subsets of words. We will rank the subsets by reliability:
    Rank:
    (A,B from 2.1): 
    A: {'investments/', 'portfolio/', 'companies/' } (case insensitive)
    B: {'company/', 'funds/'} (case insensitive)
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


def step3_attempt_4(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass
