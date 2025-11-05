"""
(Structure of Docstring: list of approaches, with rankings of implementations. Rankings are designed to be used in confidence scoring later on.)

A: 6pts
B: 5pts
C: 4pts
D: 3pts
E: 2pts
F: 1pt

__Step 1 Attempt 1__: Accessing portfolio subpage (direct):
From a given PE firm's website, access the portfolio subpage:
    Rank:
    A: firm["website"]+"/(portfolio|Portfolio|investments|Investments|companies|Companies|funds|Funds)".
    B: firm["website"]+"/(holdings|Holdings|businesses|Businesses)".
    
    
__Step 1 Attempt 2__: Accessing portfolio subpage (indirect):
Some PE firms are not only PE firms, but also have venture capital arms, or growth equity arms. As a result, there may exist no portfolio subpage on the main website.
In such cases, we will attempt to access the portfolio subpage from the PE firm's website, by entering the PE subpage of site, if available in
   Rank: 
    A: firm["website"]+"/(privateequity|pe|investments|portfolio)" or firm["website"].split(".")[1] + ("privateequity"|"pe"|"investments"|"portfolio") + {".com",".com.au"} (case insensitive).

    Then from the PE subpage, we will attempt to access the portfolio subpage using the same approach as in Step 1 Attempt 1.

    
__Step 1 Attempt 3__:
If that also fails, we will use the Google Custom Search API to search for the portfolio subpage, by searching for 
    Rank:
    A: site:{firm['website']} (portfolio|investments)

and accessing the top result.



If any of the above attempts succeed, we will proceed with 2.1 below.


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







_______________________

__Step 3 Attempt 1__: Extracting portCo names (JSON LD script, name field):
Within the chosen html classes from 2.1, we will search for any JSON LD script tags, and extract the 'name' field from those scripts as portCo names.
If multiple JSON LD scripts are found, we will extract the 'name' field from all of them.
If multiple portCos are found, we will return a list of dicts, where each dict corresponds to a portCo found.

Given Ranks A,B from 2.1, this method receives rank A.
Given Rank C from 2.1, this method receives rank B.
Otherwise, this method receives rank E, due to the fact that JSON LD scripts also hold other information, and are not specifically designed to hold portCo names.
_______________________

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
_______________________


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

Example for 3.3 (Allegro Capital):
<a class="block z-10 relative transition-all duration-200" data-id="66c5ad5e-6bc5-454f-8419-a58c4c14a64b" data-checked="false" 
href="/investments/be-campbell"><div class="z-10"><div class="relative lg:hidden"><div class="absolute z-[1] top-0 left-0 w-full 
h-px bg-black/20" style="width: 100%;"></div></div><div class="md:hidden z-10 relative"><div class="flex justify-between items-center
py-[17px]"><div class="flex items-center"><h5 class="font-semibold text-[16px] leading-[20px] lg:text-[20px] lg:leading-[26px] 
tracking-[-1.5%]">BE Campbell ...  </p><div class="flex justify-center items-center bg-background rounded-[6px] w-[45px] h-[35px]"><span 
class="text-[25px] leading-none row-arrow">→</span></div></div></div><div class="relative"><div class="absolute z-[1] bottom-0 left-0
w-full h-px bg-black/20" style="width: 0px;"></div></div></div></div></a>

From this example, we would extract 'be-campbell' as the portCo name. 


"""




from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests


def step1_attempt_1(pe_firm: dict, page) -> dict:
    """
    Returns dict with keys: 'step1_method': str, 'website_used': str|None, 'website_confidence': str|None, or None if fails.
    """
    try: 
        subpage_patterns = [
            (r"/(portfolio|Portfolio|investments|Investments|companies|Companies|funds|Funds)$", "A"),
            (r"/(holdings|Holdings|businesses|Businesses)$", "B"),
        ]
        for pattern, confidence in subpage_patterns:
            subpage = re.search(pattern, pe_firm['website'])
            if subpage:
                page.goto(pe_firm['website'] + "/" + subpage.group(1).lower(), timeout=60000)
                return {
                    'step1_method': 'Attempt 1',
                    'website_used': pe_firm['website'] + "/" + subpage.group(1).lower(),
                    'website_confidence': confidence
                }
        return None

    except Error as e:
        print(f"Error accessing portfolio subpage for PE firm website: {pe_firm['website']}. Error: {e}")
        return None

def step1_attempt_2(pe_firm: dict, page) -> dict:
    """
    Returns dict with keys: 'step1_method': str, 'website_used': str|None, 'website_confidence': str|None, or None if fails.
    """

def step1_attempt_3(pe_firm: dict, page) -> dict:
    """
    Returns dict with keys: 'step1_method': str, 'website_used': str|None, 'website_confidence': str|None, or None if fails.
    """




def step2_attempt_1(portfolio_website: dict, page) -> list[dict]:
    """
    
    Returns dict that contains:
        'classes_found': list[dict], 'class_confidence': int
        where each dict in 'classes_found' has keys:
            'class_rank': int, 'class_path': str

    """

def step3_attempt_1(portfolio_website: dict, page, portco_classes: list[str]) -> list[dict]:
    """
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int
    """

def step3_attempt_2(portfolio_website: dict, page, portco_classes: list[str]) -> list[dict]:
    """
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int
    """



def step3_attempt_3(portfolio_website: dict, page, portco_classes: list[str]) -> list[dict]:
    """
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int
    """

def step3_attempt_4(portfolio_website: dict, page, portco_classes: list[str]) -> list[dict]:
    """
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int
    """

def PortCo_Extraction(pe_firms: list[dict]) -> list[dict]:
    """
    Goes through attempts for each step, returning a list of dicts, where the dict will contain a list of dicts for the portCos for each PE firm.
    Within each element of the overall list, the dict will have keys:
        'firm_name': str, 'step1_method': int, 'website_used': str, 'website_confidence': int, 'portcos': list[dict] (for attempts 1,2 of step 1, 'website_used' will be the portfolio subpage used, for attempt 3 of step 1, it will be the googled website (also possibly portfolio subpage), 'step1_method' is the int of the attempt number).
    
    Each element of the 'portcos' list will be a dict with keys:
        'portco_name': str, 'step3_method_used': int, 'class_confidence_used': int, 'extraction_confidence': int (for attempts 1,2 of step 3, 'extraction_method' will be the int of the attempt number).

    """
    for pe_firm in pe_firms:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.goto(pe_firm['website'], timeout=60000)
            except Error as e:
                print(f"Error accessing PE firm website: {pe_firm['website']}. Error: {e}")
                continue  # Skip to next PE firm if website access fails

        portfolio_website = step1_attempt_1(pe_firm,page)
        if not portfolio_website:
            print("Step 1 Attempt 1 failed to find any portfolio subpage.")
            print("Now proceeding to Step 1 Attempt 2...")
            portfolio_website = step1_attempt_2(pe_firm,page)
        if not portfolio_website:
            print("Step 1 Attempt 2 failed to find any portfolio subpage.")
            print("Now proceeding to Step 1 Attempt 3...")
            portfolio_website = step1_attempt_3(pe_firm,page)
        if not portfolio_website:
            print("Step 1 Attempt 3 failed to find any portfolio subpage.")
            print("All Step 1 attempts failed. Exiting PortCo Extraction.")
            print("NOTE: Due to the high flexibility of Step 1 Attempt 3 (Google Search just grabs the top result), it is likely that an error occurred within the implementation.")
            return None
                

        if portfolio_website:
            portco_class = step2_attempt_1(portfolio_website,page)
            if not portco_class:
                print(f"Step 2 Attempt 1 failed to find any portCo Classes, on the portfolio subpage: {portfolio_website['website_used']}")
                print("NOTE: Due to the high flexibility of Step 2 Attempt 1 (searching for any class name if all else fails), it is likely that an error occurred within the implementation if no portCo classes were found.")
            else:
                print(f"Step 2 Attempt 1 succeeded in finding portCo Classes, on the portfolio subpage: {portfolio_website['website_used']}")
                print("Now proceeding to Step 3 Attempt 1...")
                portcos = step3_attempt_1(portfolio_website, page, [c['class_path'] for c in portco_class['classes_found']])
                if not portcos:
                    print("Step 3 Attempt 1 failed to find any portCos from the portCo Classes found.")
                    portcos = step3_attempt_2(portfolio_website, page, [c['class_path'] for c in portco_class['classes_found']])
                    if not portcos:
                        print("Step 3 Attempt 2 also failed to find any portCos from the portCo Classes found.")
                        portcos = step3_attempt_3(portfolio_website, page, [c['class_path'] for c in portco_class['classes_found']])
                        if not portcos:
                            print("Step 3 Attempt 3 also failed to find any portCos from the portCo Classes found.")
                            portcos = step3_attempt_4(portfolio_website, page, [c['class_path'] for c in portco_class['classes_found']])
                            if not portcos:
                                print("All Step 3 attempts failed. Exiting PortCo Extraction.")
                                print("NOTE: Due to the high flexibility of Step 3 Attempt 4 (searching for any href link if all else fails), it is likely that an error occurred within the implementation if no portCos were found.")
                                return None
        







#writing this first to get overall structure:
if __name__ == "__main__":
    df = pd.read_csv("output/PE_Firms.csv")
    pe_firms = df.to_dict(orient="records")

