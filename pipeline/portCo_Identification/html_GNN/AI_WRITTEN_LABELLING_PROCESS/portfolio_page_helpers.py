from playwright.sync_api import sync_playwright, Error
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup as B
from ..A_convert_html_to_tree import convert_html_to_tree


def _fetch_html(url:str, timeout:int=10) -> bytes | None:
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 403:
            raise requests.HTTPError("403 Forbidden",response=response)
        response.raise_for_status()
        return response.content
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="load", timeout=timeout*1000)
                html = page.content()
                browser.close()
                return html.encode('utf-8')
        raise #re-raise other HTTP errors



def fetch_portfolio_page(pe_firm_name: str, website_url: str, allow_auto_fetch: bool) -> tuple[B | None, str, bool, str]:
    """
    Fetch portfolio page URL and return BeautifulSoup object and updated website URL.
    
    Returns (soup, updated_website_url, auto_fetched, portfolio_url_used) or (None, website_url, auto_fetched, "") if failed.
    """
    #suspend printing for auto-fetching
    def _soup_finder(PF_url:str, success_print:str, failure_print:str, auto_fetch:bool=False):
        try:
            html = _fetch_html(PF_url, timeout=10)
            soup = B(html, 'html.parser')
            if not auto_fetch:
                print(success_print)
                print(f"✓ Fetched {len(str(soup))} characters")
            if isinstance(soup, B):
                if not auto_fetch:
                    print(f"✓ Parsed HTML with BeautifulSoup")
            return soup, website_url
        except Exception as e:
            print(f"{failure_print}: {e}")
            return None, website_url

    
    #try to auto find portfolio page using f"{website_url}/portfolio"
    if allow_auto_fetch:
        base = website_url.rstrip('/') + '/'
        candidate_portfolio_urls = [urljoin(base, 'portfolio'), urljoin(base, 'investments'), urljoin(base, 'portfolio/')]
        for i,candidate_portfolio_url in enumerate(candidate_portfolio_urls):
            soup, website_url = _soup_finder(candidate_portfolio_url, f"✓ Auto-fetched portfolio page for {pe_firm_name} on attempt {i+1}", f"✗ Auto-fetching portfolio page on attempt {i+1} failed for {pe_firm_name}", auto_fetch=True)
            if soup:
                return soup, website_url, True, candidate_portfolio_url

    print(f"\n{pe_firm_name}")
    print("-" * 60)
    
    print(f"Homepage: {website_url}")
    
    # Ask if this is the PE page
    while True:
        is_pe_page = input("Is the homepage the PE page? [y/n]: ").strip().lower()
        if is_pe_page == 'n':
            pe_page_url = input("Enter the actual PE page URL (copy & paste): ").strip()
            website_url = pe_page_url
            break
        elif is_pe_page == 'y':
            break
        else:
            print("Please enter 'y' or 'n'.")
    
    portfolio_url = input(f"Enter portfolio page URL (copy & paste): ").strip()
    
    if not portfolio_url:
        print("Skipped.")
        return None, website_url, False, ""
    
    soup, website_url = _soup_finder(portfolio_url, "✓ Fetched portfolio page", "✗ Error fetching portfolio page", auto_fetch=False)
    return soup, website_url, False, portfolio_url




def extract_all_leaves(tree_head: dict) -> dict:
    i = 0
    """Extract all leaf nodes (nodes with no children). Returns {tagID: node}"""
    leaves = {}
    
    def traverse(node):
        if not node['children']:
            leaves[node['tagID']] = node
            nonlocal i
            i += 1
        for child in node['children']:
            traverse(child)
    
    traverse(tree_head)
    return leaves, i

