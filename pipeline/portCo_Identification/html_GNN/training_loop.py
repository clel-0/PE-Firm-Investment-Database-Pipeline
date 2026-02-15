from urllib import response
import os
import requests
import torch
import json
from collections import defaultdict
from bs4 import BeautifulSoup

from .training_functions import train_naming_GNN, train_portfolio_page_finder_GNN

dtype = torch.float32

torch.set_default_dtype(dtype)

dev = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

def initialise_naming_params():
    #Define all parameters here

    W_class = torch.nn.Parameter(torch.randn(50,384)*0.01, device=dev)
    b_class = torch.nn.Parameter(torch.randn(50)*0.01, device=dev)

    W_text = torch.nn.Parameter(torch.randn(100,384)*0.01, device=dev)
    b_text = torch.nn.Parameter(torch.randn(100)*0.01, device=dev)
    W_sig = torch.nn.Parameter(torch.randn(50,384)*0.01, device=dev)
    

    W_s = torch.nn.Parameter(torch.randn(2,351)*0.01, device=dev)
    b_s = torch.nn.Parameter(torch.randn(2,1)*0.01, device=dev)

    #[W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
    namingParams = [
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_i
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #b_i
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_qs
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #b_qs
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_qi
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #b_qi   
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_k
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #b_k
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_c1
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_c2
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_i1
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_i2
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #w_c
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev),      #w_i
        torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev),  #W_ci
        torch.nn.Parameter(torch.randn(351)*0.01, device=dev)       #b_ci
    ]

    return namingParams, W_class, b_class, W_text, b_text, W_sig, W_s, b_s


def initialise_portfolio_page_finder_params():
    W_class = torch.nn.Parameter(torch.randn(50,384)*0.01, device=dev)
    b_class = torch.nn.Parameter(torch.randn(50)*0.01, device=dev)
    W_text = torch.nn.Parameter(torch.randn(100,384)*0.01, device=dev)
    b_text = torch.nn.Parameter(torch.randn(100)*0.01, device=dev)
    W_sig = torch.nn.Parameter(torch.randn(50,384)*0.01, device=dev)    
    W_down = torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev)
    b_down = torch.nn.Parameter(torch.randn(351)*0.01, device=dev)
    W_info = torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev)
    b_info = torch.nn.Parameter(torch.randn(351)*0.01, device=dev)
    W_key = torch.nn.Parameter(torch.randn(351,351)*0.01, device=dev)
    b_key = torch.nn.Parameter(torch.randn(351)*0.01, device=dev)
    W_final = torch.nn.Parameter(torch.randn(1,351)*0.01, device=dev)
    b_final = torch.nn.Parameter(torch.randn(1)*0.01, device=dev)

    return W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final


def training_loop(page_finder_data, naming_data, naming_params_package, page_finder_params_package):
    # Train naming GNN
    print("Starting training for naming GNN...")
    train_naming_GNN(naming_data, naming_params_package, batch_size=4, learning_rate=0.001, lambda1=1, lambda2=0.1, lambda3=0.1, dev=dev, dtype=dtype)
    print("Finished training for naming GNN.")

    # Train portfolio page finder GNN
    print("Starting training for portfolio page finder GNN...")
    train_portfolio_page_finder_GNN(page_finder_data, page_finder_params_package, batch_size=4, learning_rate=0.001, T1=10, T2=1000, dev=dev, dtype=dtype)
    print("Finished training for portfolio page finder GNN.")


def format_naming_data(raw_data):
    """
    {portfolio_website_url: {portco_tagIDs: [], overall_type: "innerText"/"urlText"}} -> {sample_ID: {"soup": , "correct_portCo_tagIDs": [], "overall_type": "innerText"/"urlText"}}
    """
    formatted_data = {}
    for url, label_info in raw_data.items():
        sample_id = url  # Using the URL as the sample ID
        portfolio_page_url = url
        portco_tagIDs = label_info["portco_tagIDs"]
        overall_type = label_info["overall_type"]

        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raises error for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')

        formatted_data[sample_id] = {
            "soup": soup,
            "correct_portCo_tagIDs": portco_tagIDs,
            "overall_type": overall_type,
            "portfolio_url": portfolio_page_url
        }

    return formatted_data

def format_portfolio_page_finder_data(raw_data):
    """
    {homepage_url: portfolio_page_url} -> {sample_ID: {"soup": , "portfolio_page_url": }}
    """
    formatted_data = {}
    for homepage_url, portfolio_page_url in raw_data.items():
        sample_id = homepage_url  # Using the homepage URL as the sample ID

        response = requests.get(homepage_url, timeout=10)
        response.raise_for_status()  # Raises error for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')

        formatted_data[sample_id] = {
            "soup": soup,
            "portfolio_page_url": portfolio_page_url
        }

    return formatted_data



#uses mtime-based sorting directly using .stat().st_mtime to get most recent files, instead of relying on filename convention. Returns list of file paths and string representation of files for printing.
from pathlib import Path
def get_data_files(type: str) -> list:
    output_dir = Path(__file__).resolve().parents[4] / "output" / "training_data"
    if not output_dir.exists():
        print("Seems to be no files in the training_data directory yet. Returning default filename.")

    candidates = sorted(
        output_dir.glob(f"{type}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    ) #sorts files by datetime using filename convention of {type}_%Y-%m-%d-%H-%M-%S.json
    
    if len(candidates) >20: #if there are more than 20 files, keep only the 20 most recent to avoid overwhelming the user with too many options
        candidates = candidates[:20]

    files_str = "\n".join([f"{i}. {p}" for i,p in enumerate(candidates)]) if candidates else "No files found in training_data directory."

    return [str(p) for p in candidates] if candidates else [f"{type}.json"], files_str



if __name__ == "__main__":

    #prepare portfolio page finder training data
    files_list, files_str = get_data_files("portfolio_href_data")

    print(f"Available portfolio subpage data files:\n{files_str}\n")

    portfolio_path_idx = int(input(f"Select portfolio subpage data file by index (0-{len(files_list)-1}): "))

    portfolio_href_data_path = files_list[portfolio_path_idx]
    
    
    #prepare naming GNN training data
    files_list, files_str = get_data_files("naming_data")

    print(f"Available naming data files:\n{files_str}\n")

    naming_path_idx = int(input(f"Select naming data file by index (0-{len(files_list)-1}): "))

    naming_data_path = files_list[naming_path_idx]
    
    
    with open(portfolio_href_data_path, "r") as f:
        raw_page_finder_labels = json.load(f)

    with open(naming_data_path, "r") as f:
        raw_naming_labels = json.load(f)

    page_finder_data = format_portfolio_page_finder_data(raw_page_finder_labels)
    naming_data = format_naming_data(raw_naming_labels)
    
    base = Path(__file__).resolve().parent.parent.parent # go up 3 levels to pipeline/
    subpage_dir = base / 'output' / 'subpage_GNN_models'
    naming_dir = base / 'output' / 'naming_GNN_models'

     
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

dev = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

if subpage_dir.is_dir() and any(subpage_dir.iterdir()):
    print(f"Existing portfolio page finder GNN model files found in {subpage_dir}:")
    for i, file in enumerate(subpage_dir.iterdir()):
        print(f"{i}. {file.name}")
    load_subpage = input("Do you want to load an existing portfolio page finder GNN model? (y/n): ")
    if load_subpage.lower() == 'y':
        subpage_idx = int(input(f"Enter the index of the portfolio page finder GNN model to load (0-{len(list(subpage_dir.iterdir()))-1}): "))
        subpage_model_path = list(subpage_dir.iterdir())[subpage_idx]
        subpage_model_state = torch.load(subpage_model_path, map_location=dev)
        final_subpage_params = {
            'W_class': subpage_model_state['W_class'],
            'b_class': subpage_model_state['b_class'],
            'W_text': subpage_model_state['W_text'],
            'b_text': subpage_model_state['b_text'],
            'W_sig': subpage_model_state['W_sig'],
            'W_down': subpage_model_state['W_down'],
            'b_down': subpage_model_state['b_down'],
            'W_info': subpage_model_state['W_info'],
            'b_info': subpage_model_state['b_info'],
            'W_key': subpage_model_state['W_key'],
            'b_key': subpage_model_state['b_key'],
            'W_final': subpage_model_state['W_final'],
            'b_final': subpage_model_state['b_final']
        }
    if load_subpage.lower() != 'y':
        print("Initializing new portfolio page finder GNN model with random parameters.")
        final_subpage_params = initialise_portfolio_page_finder_params()
    else:
        print("Initializing new portfolio page finder GNN model with random parameters.")
        final_subpage_params = initialise_portfolio_page_finder_params()


if naming_dir.is_dir() and any(naming_dir.iterdir()):
    print(f"Existing naming GNN model files found in {naming_dir}:")
    for i, file in enumerate(naming_dir.iterdir()):
        print(f"{i}. {file.name}")
    load_naming = input("Do you want to load an existing naming GNN model? (y/n): ")
    if load_naming.lower() == 'y':
        naming_idx = int(input(f"Enter the index of the naming GNN model to load (0-{len(list(naming_dir.iterdir()))-1}): "))
        naming_model_path = list(naming_dir.iterdir())[naming_idx]
        naming_model_state = torch.load(naming_model_path, map_location=dev)
        final_naming_params = {
            'W_class': naming_model_state['W_class'],
            'b_class': naming_model_state['b_class'],
            'W_text': naming_model_state['W_text'],
            'b_text': naming_model_state['b_text'],
            'W_sig': naming_model_state['W_sig'],
            'W_s': naming_model_state['W_s'],
            'b_s': naming_model_state['b_s'],
            'namingParams': naming_model_state['namingParams']
        }
    if load_naming.lower() != 'y':
        print("Initializing new naming GNN model with random parameters.")
        final_naming_params = initialise_naming_params()

else:
    print("Initializing new naming GNN model with random parameters.")
    final_naming_params = initialise_naming_params()


# Run training loop

train_portfolio_page_finder_GNN(page_finder_data, final_subpage_params, dev=dev)
train_naming_GNN(naming_data, final_naming_params, dev=dev)

    