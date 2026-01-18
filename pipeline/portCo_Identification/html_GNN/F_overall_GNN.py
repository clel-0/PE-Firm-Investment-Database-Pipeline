from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup as B
import torch
import torch.nn.functional as F

from A_convert_html_to_tree import convert_html_to_tree
from B_convert_node_to_vector import convert_node_to_vector
from C_subpage_GNN_process import portfolio_page_finder_GNN
from D_naming_GNN_process import GNN_process_portCo
from E_name_grouping import scores


def overall_GNN(is_PF_subpage: bool, website: str, soup: B, W_class, b_class, W_text, b_text, namesParams, subpageParams) -> list:
    """
    Overall GNN process to extract portCo names from HTML soup.

    is_PF_subpage: bool, whether the soup is from a portfolio finder subpage. If True, use portfolio page finder GNN instead.

    namesParams: [W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci, W_s, b_s]

    subpageParams: [W_down, b_down, W_up, b_up, W_info, b_info, W_key, b_key, W_final, b_final]

    """
    if not is_PF_subpage:
        #note: in this case, groupIDs is empty, so we need to create it

        hrefleaf_to_score = portfolio_page_finder_GNN(soup, *subpageParams)
        if not hrefleaf_to_score:
            print("No href-leaf nodes found, returning empty portCo names list.")
            return []
        #select best href-leaf
        best_leaf = max(hrefleaf_to_score, key=lambda leaf: hrefleaf_to_score[leaf])

        #extract subpage URL from best_leaf
        subpage_url = urljoin(website, best_leaf['bs4_element'].get('href'))

        #fetch subpage soup
        try:
            response = requests.get(subpage_url, timeout=10)
            response.raise_for_status()
            subpage_soup = B(response.text, 'html.parser')
        except Exception as e:
            print(f"Failed to fetch subpage {subpage_url}: {e}")
            return []
        

                

    #1) Convert HTML to tree
    tree_head = convert_html_to_tree(subpage_soup)

    #2) Convert nodes to vectors
    def traverse_and_vectorise(node):
        convert_node_to_vector(node, W_class, b_class, W_text, b_text)
        for child in node['children']:
            traverse_and_vectorise(child)

    traverse_and_vectorise(tree_head)

    #3) GNN processing
    leafList = GNN_process_portCo(tree_head, *namesParams[:-2])  #all params except last two (W_g, b_g)

    #4) Collate leaf nodes by group

    W_s, b_s = namesParams[-2], namesParams[-1]

    #5) Compute group scores
    confidence_scores, type_scores = scores(leafList, W_s, b_s) #these are the final scores and will be considered the output for training.

    if not confidence_scores:
        print("No scores computed, returning empty portCo names list.")
        return []
    
    


    #6) Select best group and extract portCo names
    portCo_names = []

    mean_type = sum(type_scores) / len(type_scores)

    type = "InnerText" if mean_type > 0.5 else "UrlText"

    for s,leaf in zip(confidence_scores, leafList):
        if s > 0.8:
            portCo_names.append(leaf[type])
    

    return portCo_names