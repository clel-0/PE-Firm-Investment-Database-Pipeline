#create pandas df with (PE firm name, groupID_to_sig dict, websites, PortCo names) columns for training


import pandas as pd


def create_GNN_training_df(portco_results: list[dict], groupIDs: dict) -> pd.DataFrame:
    """
    Idea: Through the terminal input, allow the user to pick which group of candidates are true portCos for each PE firm.
    Then create a pandas dataframe with columns:
        'PE_Firm_Name': str,
        'groupID_to_sig': dict,
        'Website': str, 
        'Portfolio Website': str,
        'Correct GroupIDs': list[int]


    """