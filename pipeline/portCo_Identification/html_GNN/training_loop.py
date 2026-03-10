import os
import random
import requests
import torch
import json
import hashlib
from bs4 import BeautifulSoup
from pathlib import Path

from .portco_name_training_functions import train_naming_GNN
from .subpage_training_functions import train_portfolio_page_finder_GNN
from .functions__training_loop import *
from .functions__training import get_model_dirs

dtype = torch.float32

torch.set_default_dtype(dtype)

dev = resolve_training_device()



if __name__ == "__main__":

    set_reproducibility(seed=42)

    def _prompt_index(prompt: str, max_index: int) -> int:
        while True:
            raw = input(prompt).strip()
            try:
                idx = int(raw)
            except ValueError:
                print("Invalid input: please enter an integer index.")
                continue
            if 0 <= idx <= max_index:
                return idx
            print(f"Index out of range. Enter a value between 0 and {max_index}.")

    #prepare portfolio page finder training data
    files_list, files_str = get_data_files("portfolio_href_data")

    print(f"Available portfolio subpage data files:\n{files_str}\n")

    if not files_list:
        raise FileNotFoundError("No portfolio_href_data files found under output/training_data.")

    portfolio_path_idx = _prompt_index(f"Select portfolio subpage data file by index (0-{len(files_list)-1}): ", len(files_list)-1)

    portfolio_href_data_path = files_list[portfolio_path_idx]
    
    
    #prepare naming GNN training data
    files_list, files_str = get_data_files("naming_data")

    print(f"Available naming data files:\n{files_str}\n")

    if not files_list:
        raise FileNotFoundError("No naming_data files found under output/training_data.")

    naming_path_idx = _prompt_index(f"Select naming data file by index (0-{len(files_list)-1}): ", len(files_list)-1)

    naming_data_path = files_list[naming_path_idx]
    
    
    raw_page_finder_labels = load_json_with_fallback(portfolio_href_data_path)
    raw_naming_labels = load_json_with_fallback(naming_data_path)

    page_finder_data = format_portfolio_page_finder_data(raw_page_finder_labels)
    naming_data = format_naming_data(raw_naming_labels)
    
    subpage_dir, naming_dir = get_model_dirs()
    

     
    os.makedirs(subpage_dir, exist_ok=True)
    os.makedirs(naming_dir, exist_ok=True)

    """
    saved torch model structure for portfolio page finder GNN:

    {
        'W_class': W_class,
        'b_class': b_class,
        'W_text': W_text,
        'b_text': b_text,
        'W_sig': W_sig,
        'W_down': W_down,
        'b_down': b_down,
        'W_info': W_info,
        'b_info': b_info,
        'W_key': W_key,
        'b_key': b_key,
        'W_final': W_final,
        'b_final': b_final
    }
    Note: this is also the order they need to be passed in for the training loop functions.
    

    saved torch model structure for naming GNN:

    {
        'W_class': W_class,
        'b_class': b_class,
        'W_text': W_text,
        'b_text': b_text,
        'W_sig': W_sig,
        'W_s': W_s,
        'b_s': b_s,
        'namingParams': namingParams
    }

    Note: this is also the order they need to be passed in for the training loop functions.
        
    """

    subpage_models = collect_model_files(subpage_dir)
    if subpage_models:
        print(f"Existing portfolio page finder GNN model files found in {subpage_dir}:")
        for i, file in enumerate(subpage_models):
            print(f"{i}. {file.name}")
        load_subpage = input("Do you want to load an existing portfolio page finder GNN model? (y/n): ")
        if load_subpage.lower() == 'y':
            subpage_idx = _prompt_index(f"Enter the index of the portfolio page finder GNN model to load (0-{len(subpage_models)-1}): ", len(subpage_models)-1)
            subpage_model_path = subpage_models[subpage_idx]
            subpage_model_state = torch.load(subpage_model_path, map_location=dev)
            final_subpage_params = (
                subpage_model_state['W_class'],
                subpage_model_state['b_class'],
                subpage_model_state['W_text'],
                subpage_model_state['b_text'],
                subpage_model_state['W_sig'],
                subpage_model_state['W_down'],
                subpage_model_state['b_down'],
                subpage_model_state['W_info'],
                subpage_model_state['b_info'],
                subpage_model_state['W_key'],
                subpage_model_state['b_key'],
                subpage_model_state['W_final'],
                subpage_model_state['b_final']
            )
        else:
            print("Initializing new portfolio page finder GNN model with random parameters.")
            final_subpage_params = initialise_portfolio_page_finder_params()
    else:
        print("Initializing new portfolio page finder GNN model with random parameters.")
        final_subpage_params = initialise_portfolio_page_finder_params()

    naming_models = collect_model_files(naming_dir)
    if naming_models:
        print(f"Existing naming GNN model files found in {naming_dir}:")
        for i, file in enumerate(naming_models):
            print(f"{i}. {file.name}")
        load_naming = input("Do you want to load an existing naming GNN model? (y/n): ")
        if load_naming.lower() == 'y':
            naming_idx = _prompt_index(f"Enter the index of the naming GNN model to load (0-{len(naming_models)-1}): ", len(naming_models)-1)
            naming_model_path = naming_models[naming_idx]
            naming_model_state = torch.load(naming_model_path, map_location=dev)
            final_naming_params = (
                naming_model_state['W_class'],
                naming_model_state['b_class'],
                naming_model_state['W_text'],
                naming_model_state['b_text'],
                naming_model_state['W_sig'],
                naming_model_state['W_s'],
                naming_model_state['b_s'],
                naming_model_state['namingParams']
            )
        else:
            print("Initializing new naming GNN model with random parameters.")
            final_naming_params = initialise_naming_params()
    else:
        print("Initializing new naming GNN model with random parameters.")
        final_naming_params = initialise_naming_params()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using device:", dev)

    if torch.cuda.is_available():
        print("GPU name:", torch.cuda.get_device_name(0))


    # Run training loop
    subpage_result = train_portfolio_page_finder_GNN(page_finder_data, final_subpage_params, dev=dev)
    if subpage_result is None:
        raise RuntimeError("Portfolio page finder GNN training did not execute any valid optimization steps.")

    naming_result = train_naming_GNN(naming_data, final_naming_params, dev=dev)
    if naming_result is None:
        raise RuntimeError("Naming GNN training did not execute any valid optimization steps.")

    