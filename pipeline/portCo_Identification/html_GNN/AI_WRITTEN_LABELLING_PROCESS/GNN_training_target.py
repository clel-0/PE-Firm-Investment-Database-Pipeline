"""
Core functions for PortCo labeling system.

Workflow:
1. User provides portfolio subpage URL for each PE firm
2. System extracts all candidate nodes (structural leaves + non-leaf nodes with InnerText)
3. User labels which candidate nodes are PortCo names

output:

json file with structure:
{main_website_url: tagID of HTML node containing portfolio href in homepage}

note: in the naming GNN target label dict, the portfolio page URL is the key 

"""

import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup as B
from pathlib import Path
from ..A_convert_html_to_tree import convert_html_to_tree
from .portfolio_page_helpers import _fetch_html, fetch_portfolio_page, extract_all_leaves
#note: _fetch_html returns bytes | None


def find_portfolio_href_in_homepage(homepage_url: str, portfolio_url: str) -> tuple[B | None, int | None]:
    """
    Fetch homepage, convert to tree, and find which href-leaf points to portfolio page.
    Returns (homepage_soup, tagID_of_portfolio_href) or (None, None) if not found.
    """
    try:
        html = _fetch_html(homepage_url, timeout=10)
        homepage_soup = B(html, 'html.parser')
        
        # Convert homepage to tree
        tree_head, id_to_node = convert_html_to_tree(homepage_soup)
        
        # Find href leaves (nodes with href but no descendants with href)
        def find_href_leaves(node):
            leaves = []
            if node.get('bs4_element') and node['bs4_element'].get('href'):
                if not node['bs4_element'].find_all(href=True, recursive=True):
                    leaves.append(node)
            for child in node['children']:
                leaves.extend(find_href_leaves(child))
            return leaves
        
        href_leaves = find_href_leaves(tree_head)
        
        # Match portfolio URL with href leaves
        for leaf in href_leaves:
            href = leaf['bs4_element'].get('href', '')
            # Normalize URLs for comparison
            full_href = urlparse(urljoin(homepage_url, href))
            full_portfolio = urlparse(portfolio_url)
            if full_href.netloc == full_portfolio.netloc and full_href.path == full_portfolio.path:
                return homepage_soup, leaf['tagID']
            
            # Try path-only comparison (for relative hrefs like '/investments' or 'investments')
            if href:
                href_path = href.split('?', 1)[0].rstrip('/')
                portfolio_path = full_portfolio.path.rstrip('/')
                if href_path.startswith('/'):
                    href_path = href_path
                else:
                    href_path = f"/{href_path}"
                if href_path == portfolio_path:
                    return homepage_soup, leaf['tagID']
        

        #in the case portfolio page is not a subpage, but a separate domain (e.g. microsite)
        for leaf in href_leaves:
            href = leaf['bs4_element'].get('href', '')
            # Normalize both URLs (strip trailing slashes, lowercase)
            normalized_href = urlparse(href.rstrip('/')).geturl().lower()
            href_with_slash = urlparse(href.rstrip('/') + '/').geturl().lower()
            normalized_portfolio = urlparse(portfolio_url.rstrip('/')).geturl().lower()
            if normalized_href == normalized_portfolio or href_with_slash == normalized_portfolio:
                return homepage_soup, leaf['tagID']

        return homepage_soup, None
    except Exception as e:
        print(f"✗ Error fetching homepage: {e}")
        return None, None


def prepare_labeling_data(training_csv: str, output_json: str) -> None:
    """
    Main workflow:
    1. Load PE firms from CSV
    2. Ask user for portfolio page URL for each firm
    3. Extract candidate nodes from each portfolio page
    4. Find portfolio href in homepage for GNN training
    5. Save to JSON for Streamlit app
    """
    import pandas as pd
    
    # Load PE firms
    df = pd.read_csv(training_csv)

    name_col = 'FullName' if 'FullName' in df.columns else 'PE_firm_name'
    website_col = 'Website' if 'Website' in df.columns else 'website'
    if name_col not in df.columns or website_col not in df.columns:
        raise KeyError(
            "Expected CSV columns for firm name and website. Supported pairs: "
            "('FullName','Website') or ('PE_firm_name','website')."
        )

    print(f"\nLoaded {len(df)} PE firms from {training_csv}")
    print("=" * 60)
    print("Enter portfolio page URLs (copy & paste from browser)")
    print("=" * 60)
    
    labeling_data = {}
    portfolio_href_data = {}  # Maps homepage URL to portfolio href tagID
    
    for idx, row in df.iterrows():
        pe_firm_name = row[name_col]
        website_url = row[website_col]
        sample_id = f"{pe_firm_name}_{idx}"
        
        first_attempt_done = False
        go_again = True
        allow_auto_fetch = True

        while go_again:

            if not first_attempt_done:
                print(f"Attempting auto-fetch for {pe_firm_name}...")

            soup, updated_website_url, auto_fetched, portfolio_url_used = fetch_portfolio_page(pe_firm_name, website_url, allow_auto_fetch=allow_auto_fetch)
            allow_auto_fetch = False  # only allow auto-fetch once
            
            if not portfolio_url_used:
                go_again = False
                continue  #user opted to skip

            # Update df if website changed
            if updated_website_url != website_url:
                df.loc[idx, website_col] = updated_website_url
                website_url = updated_website_url
            
            if soup is None:
                go_again = False
                continue

            # Convert to tree and extract candidate nodes
            try:
                tree_head, _ = convert_html_to_tree(soup)
                if not auto_fetched:
                    print(f" - Converted HTML to tree")
                leaves, leaf_count = extract_all_leaves(tree_head)
                if not auto_fetched:
                    print(f" - Extracted {leaf_count} candidate nodes from tree (should be equal to {len(leaves)})")
                # Create labeling dict
                leaf_dict = {}
                for tag_id, node in leaves.items():
                    leaf_dict[str(tag_id)] = {
                        'innerText': node['InnerText'],
                        'urlText': node['UrlText'],
                        'tagName': node['tagName']
                    }
                
                
                
                if not auto_fetched:
                    print(f"✓ Extracted {len(leaves)} candidate nodes")
                
                # Find portfolio href in homepage for second GNN training
                if not auto_fetched:
                    portfolio_url = input("Enter the portfolio page URL again (for verification): ").strip()
                else:
                    portfolio_url = portfolio_url_used
                if portfolio_url:
                    _, portfolio_href_tagid = find_portfolio_href_in_homepage(website_url, portfolio_url)
                    if portfolio_href_tagid is not None:
                        portfolio_href_data[website_url] = portfolio_href_tagid
                        if auto_fetched:
                            print(f"✓ Auto-fetched portfolio page {portfolio_url} for {pe_firm_name} and found href at tagID: {portfolio_href_tagid}")
                        else:
                            print(f"✓ Found portfolio href at tagID: {portfolio_href_tagid}")

                        print(f"CONFIRMATION: portfolio URL used: {portfolio_url_used} for {pe_firm_name}")
                        labeling_data[sample_id] = {
                            'leaves': leaf_dict,
                            'total_leaves': leaf_count,
                            'portfolio_url': portfolio_url_used,
                            'portfolio_html': str(soup)
                        }
                        go_again = False
                        
                    else:
                        if not auto_fetched:
                            print(f"✗ Could not find matching portfolio href in homepage")
                        else:
                            print(f"✗ Auto-fetch succeeded for {pe_firm_name} but couldn't find portfolio href in homepage")
                        if not first_attempt_done:
                            first_attempt_done = True
                        else:
                            go_again = False

                        
            except Exception as e:
                if not auto_fetched:
                    print(f"✗ Error processing: {e}")
                else:
                    print("✗ Auto-fetch failed - exception during processing")
                if not first_attempt_done:
                    first_attempt_done = True
                else:
                    go_again = False
    
    # Filter out unwanted candidate nodes; keep this consistent with naming GNN candidate semantics
    for sample_id in labeling_data:
        leaves = labeling_data[sample_id]['leaves']
        labeling_data[sample_id]['leaves'] = {
            tag_id: leaf for tag_id, leaf in leaves.items()
            if not (leaf['innerText'] == 'placeholder' or 
                    (leaf.get('innerText') is None and leaf['urlText'] == ''))
        }
        labeling_data[sample_id]['total_leaves'] = len(labeling_data[sample_id]['leaves'])
    
    # Save to JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(labeling_data, f, indent=2, ensure_ascii=False)
    
    # Save portfolio href data
    output_path = Path(output_json)
    repo_root = Path(__file__).resolve().parents[4]
    training_data_dir = repo_root / "output" / "training_data"
    training_data_dir.mkdir(parents=True, exist_ok=True)
    suffix = output_path.stem.replace("labeling_data_", "")
    portfolio_href_json = training_data_dir / f"portfolio_href_data_{suffix}.json"
    with open(portfolio_href_json, 'w', encoding='utf-8') as f:
        json.dump(portfolio_href_data, f, indent=2, ensure_ascii=False)
    
    # Save updated PE_firms.csv
    df.to_csv(training_csv, index=False)
    
    print(f"\n{'='*60}")
    print(f"✓ Saved {len(labeling_data)} samples to {output_json}")
    print(f"✓ Saved {len(portfolio_href_data)} portfolio hrefs to {portfolio_href_json}")
    print(f"Ready to label in Streamlit: streamlit run pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/app.py")
    print(f"{'='*60}")


if __name__ == "__main__":
    import time
    import sys
    from pathlib import Path
    import os
    
    curr_time = time.strftime("%Y%m%d-%H%M%S")

    # Get path relative to repo root
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(repo_root / "output" / "PE_firms.csv")
    json_path = str(repo_root / "output" / "labeling_data" / f"labeling_data_{curr_time}.json")
    
    os.makedirs(Path(json_path).parent, exist_ok=True)

    
    prepare_labeling_data(csv_path, json_path)
    