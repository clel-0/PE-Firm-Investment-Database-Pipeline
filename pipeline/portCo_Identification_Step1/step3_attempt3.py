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



__Step 3 Attempt 3__: Extracting portCo names ('src' values):
From the 'src' values obtained in 2.1, we will extract the portCo names.
Now, the 'src' value seems to be an upload hyperlink that contains the name of the portCo right after or a couple of back slashes after the substring '/uploads'.
As a result, we will extract the substring of the 'src' values that:
    Rank:
    (for A,B from 2.1):
    A: is the first non-numerical component after '/uploads' (only alphabetic), and bounded to the right by either a hyphen, underscore, or file extension (., jpg, png, svg, etc).
    (Only reason this is Attempt 3 is because it is brittle, but given the high reliability of 2.1 A,B classes, if it is found then it has high confidence).
    (otherwise for C-E from 2.1, E, due to the fact that 'src' values may contain many non-portCo images):


Additionally, we will check the portCo name with a Google API, by searhing 'Who invested in {src_value}', and recording the top result's snippet text. If the snippet text contains the name of the PE firm, we will label that portCo as invested by the PE firm.

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


def step3_attempt_3(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    #to be implemented
    pass
