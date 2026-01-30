#create pandas df with (PE firm name, groupID_to_sig dict, websites, PortCo names) columns for training


import pandas as pd


def create_GNN_training_df(training_data: list[dict]) -> pd.DataFrame:
    """
    Input:
    Each element in the list:
    {
    'PE_firm_name': str,
    'website': str
    }

    Idea: 
    1) For each PE firm website, create a dict: {tagID: href link} for each href leaf node in the HTML tree.
    2) display the dict to the user, and ask them to choose which tagID corresponds to the correct href link to the PortCo listing page.
    3) Then, for that portCo listing page, create a dict: {tagID: {'innerText': iT, 'urlText': uT}}
    4) display the dict to the user, and ask them to choose which tagIDs corresponds to the correct PortCo names, as well as which type of PortCo name it is (from iT or uT).

    Implementation:
    - For each PE firm website in training_data:
        - create the HTML tree using A_convert_html_to_tree.py
        - extract the href leaf nodes, and create the {tagID: href link} dict
        - display to user, and get user input for correct tagID for PortCo listing page
        - fetch the PortCo listing page HTML, create the HTML tree
        - extract the leaf nodes, and create the {tagID: {'innerText': iT, 'urlText': uT}} dict
        - display to user, and get user input for correct tagIDs for PortCo names
    
    - Note: training.py wants 2 dfs: 
        1) Naming: {sample_ID: (soup, true_portCo_name_nodes, true_type)}
        2) Subpage classification: {sample_ID: (soup, true_subpage_tagID)}
    
    Display Method:
    
        

    """