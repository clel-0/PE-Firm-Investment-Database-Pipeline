import os
import random
import requests
import torch
import json
import hashlib
from bs4 import BeautifulSoup

from .training_functions import train_naming_GNN, train_portfolio_page_finder_GNN

dtype = torch.float32

torch.set_default_dtype(dtype)

def resolve_training_device():
    if not torch.cuda.is_available():
        print("[ENV] CUDA unavailable. Using CPU.")
        return torch.device("cpu")

    try:
        dev = torch.device("cuda")
        test = torch.randn(128, 128, device=dev)
        _ = test @ test
        torch.cuda.synchronize()
        print(f"[ENV] Using CUDA device: {torch.cuda.get_device_name(0)}")
        return dev
    except Exception as exc:
        print(f"[ENV] CUDA reported available but failed runtime check: {exc}")
        print("[ENV] Falling back to CPU. Fix CUDA/cuDNN installation to enable GPU training.")
        return torch.device("cpu")


dev = resolve_training_device()


def load_json_with_fallback(file_path: str):
    """Load JSON with explicit encodings to avoid Windows cp1252 decode failures."""
    encodings_to_try = ["utf-8", "utf-8-sig", "cp1252"]
    last_error = None

    for encoding in encodings_to_try:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                if encoding != "utf-8":
                    print(f"Loading {file_path} with fallback encoding '{encoding}'.")
                return json.load(f)
        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"Failed to decode JSON file {file_path} with encodings {encodings_to_try}."
    )


def compute_sha256(text: str | None) -> str:
    if text is None:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def initialise_naming_params():
    #Define all parameters here
    print("Prepping naming GNN parameters...")
    W_class = torch.nn.Parameter(torch.randn(50, 384, device=dev) * 0.01)
    b_class = torch.nn.Parameter(torch.randn(50, device=dev) * 0.01)

    W_text = torch.nn.Parameter(torch.randn(100, 384, device=dev) * 0.01)
    b_text = torch.nn.Parameter(torch.randn(100, device=dev) * 0.01)
    W_sig = torch.nn.Parameter(torch.randn(50, 384, device=dev) * 0.01)
    

    W_s = torch.nn.Parameter(torch.randn(2, 351, device=dev) * 0.01)
    b_s = torch.nn.Parameter(torch.randn(2, 1, device=dev) * 0.01)

    #[W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
    namingParams = [
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_i
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #b_i
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_qs
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #b_qs
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_qi
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #b_qi   
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_k
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #b_k
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_c1
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_c2
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_i1
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_i2
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #w_c
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01),      #w_i
        torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01),  #W_ci
        torch.nn.Parameter(torch.randn(351, device=dev) * 0.01)       #b_ci
    ]

    return namingParams, W_class, b_class, W_text, b_text, W_sig, W_s, b_s


def initialise_portfolio_page_finder_params():
    print("Prepping portfolio page finder GNN parameters...")
    W_class = torch.nn.Parameter(torch.randn(50, 384, device=dev) * 0.01)
    b_class = torch.nn.Parameter(torch.randn(50, device=dev) * 0.01)
    W_text = torch.nn.Parameter(torch.randn(100, 384, device=dev) * 0.01)
    b_text = torch.nn.Parameter(torch.randn(100, device=dev) * 0.01)
    W_sig = torch.nn.Parameter(torch.randn(50, 384, device=dev) * 0.01)
    W_down = torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01)
    b_down = torch.nn.Parameter(torch.randn(351, device=dev) * 0.01)
    W_info = torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01)
    b_info = torch.nn.Parameter(torch.randn(351, device=dev) * 0.01)
    W_key = torch.nn.Parameter(torch.randn(351, 351, device=dev) * 0.01)
    b_key = torch.nn.Parameter(torch.randn(351, device=dev) * 0.01)
    W_final = torch.nn.Parameter(torch.randn(1, 351, device=dev) * 0.01)
    b_final = torch.nn.Parameter(torch.randn(1, device=dev) * 0.01)

    return W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final


def training_loop(page_finder_data, naming_data, naming_params_package, page_finder_params_package):
    # Train naming GNN
    print("Starting training for naming GNN...")
    naming_result = train_naming_GNN(naming_data, naming_params_package, batch_size=4, learning_rate=0.001, lambda1=1, lambda2=0.1, lambda3=0.1, dev=dev, dtype=dtype)
    if naming_result is None:
        raise RuntimeError("Naming GNN training did not execute any valid optimization steps.")
    print("Finished training for naming GNN.")

    # Train portfolio page finder GNN
    print("Starting training for portfolio page finder GNN...")
    subpage_result = train_portfolio_page_finder_GNN(page_finder_data, page_finder_params_package, batch_size=4, learning_rate=0.001, T1=10, T2=1000, dev=dev, dtype=dtype)
    if subpage_result is None:
        raise RuntimeError("Portfolio page finder GNN training did not execute any valid optimization steps.")
    print("Finished training for portfolio page finder GNN.")


def format_naming_data(raw_data):
    """
    {portfolio_website_url: {portco_tagIDs: [], overall_type: "innerText"/"urlText"}} -> {sample_ID: {"soup": , "correct_portCo_tagIDs": [], "overall_type": "innerText"/"urlText"}}
    """
    formatted_data = {}
    for sample_key, label_info in raw_data.items():
        if not isinstance(label_info, dict):
            print(f"Skipping sample {sample_key}: invalid label payload type {type(label_info).__name__}")
            continue

        sample_id = label_info.get("sample_id", sample_key)
        portfolio_page_url = label_info.get("portfolio_url", sample_key)
        raw_tag_ids = label_info.get("portco_tagIDs", [])
        portco_tagIDs = []
        rejected_tag_ids = []
        for tag_id in raw_tag_ids:
            try:
                portco_tagIDs.append(int(tag_id))
            except (TypeError, ValueError):
                rejected_tag_ids.append(tag_id)

        if rejected_tag_ids:
            print(f"Skipping invalid tagIDs for {sample_id}: {rejected_tag_ids}")

        #this replaces the need to remove empty tagID lists in app.py. Note: empty tagID lists are not valid for training since they would not provide any positive signal for the model to learn from, and likely represent cases where the labeler was unsure or made an error in labeling, so it's better to skip them entirely.
        if not portco_tagIDs:
            print(f"Skipping sample {sample_id}: no valid portco_tagIDs after type normalization.")
            continue

        overall_type = label_info.get("overall_type", "innerText")

        portfolio_html = label_info.get("portfolio_html")
        if not portfolio_html:
            print(f"Skipping sample {sample_id}: missing portfolio_html snapshot (required for stable tagID supervision).")
            continue

        expected_sha256 = label_info.get("portfolio_html_sha256")
        if expected_sha256:
            actual_sha256 = compute_sha256(portfolio_html)
            if actual_sha256 != expected_sha256:
                print(
                    f"Skipping sample {sample_id}: portfolio_html SHA-256 mismatch "
                    f"(expected {expected_sha256}, got {actual_sha256})."
                )
                continue

        soup = BeautifulSoup(portfolio_html, 'html.parser')

        formatted_data[sample_id] = {
            "soup": soup,
            "correct_portCo_tagIDs": portco_tagIDs,
            "overall_type": overall_type,
            "portfolio_url": portfolio_page_url
        }

    return formatted_data

def format_portfolio_page_finder_data(raw_data):
    """
    {homepage_url: portfolio_href_tagID} -> {sample_ID: {"soup": , "true_portfolio_page_tagID": int}}
    """
    formatted_data = {}
    for homepage_url, portfolio_href_tagID in raw_data.items():
        sample_id = homepage_url  # Using the homepage URL as the sample ID

        try:
            response = requests.get(homepage_url, timeout=10)
            response.raise_for_status()  # Raises error for bad status codes
            soup = BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as exc:
            print(f"Skipping homepage {homepage_url}: failed to fetch page ({exc})")
            continue

        try:
            portfolio_href_tagID = int(portfolio_href_tagID)
        except (TypeError, ValueError):
            print(f"Skipping homepage {homepage_url}: invalid portfolio href tag ID {portfolio_href_tagID}")
            continue

        formatted_data[sample_id] = {
            "soup": soup,
            "true_portfolio_page_tagID": portfolio_href_tagID
        }

    return formatted_data



#uses mtime-based sorting directly using .stat().st_mtime to get most recent files, instead of relying on filename convention. Returns list of file paths and string representation of files for printing.
from pathlib import Path
def get_data_files(type: str) -> list:
    output_dir = Path(__file__).resolve().parents[3] / "output" / "training_data"
    if not output_dir.exists():
        print("Seems to be no files in the training_data directory yet.")
        return [], "No files found in training_data directory."

    candidates = sorted(
        output_dir.glob(f"{type}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    ) #sorts files by datetime using filename convention of {type}_%Y-%m-%d-%H-%M-%S.json
    
    if len(candidates) >20: #if there are more than 20 files, keep only the 20 most recent to avoid overwhelming the user with too many options
        candidates = candidates[:20]

    files_str = "\n".join([f"{i}. {p}" for i,p in enumerate(candidates)]) if candidates else "No files found in training_data directory."

    return [str(p) for p in candidates], files_str


def get_model_dirs() -> tuple[Path, Path]:
    base = Path(__file__).resolve().parents[3]
    subpage_dir = base / 'output' / 'subpage_GNN_models'
    naming_dir = base / 'output' / 'naming_GNN_models'
    return subpage_dir, naming_dir


def get_legacy_model_dirs() -> tuple[Path, Path]:
    pipeline_base = Path(__file__).resolve().parents[2]
    subpage_dir = pipeline_base / 'output' / 'subpage_GNN_models'
    naming_dir = pipeline_base / 'output' / 'naming_GNN_models'
    return subpage_dir, naming_dir


def collect_model_files(primary_dir: Path, legacy_dir: Path) -> list[Path]:
    files = []
    seen = set()
    for directory in [primary_dir, legacy_dir]:
        if directory.is_dir():
            for file_path in sorted(directory.iterdir(), key=lambda p: p.name):
                if file_path.is_file() and file_path.suffix == ".pt":
                    resolved = str(file_path.resolve())
                    if resolved not in seen:
                        files.append(file_path)
                        seen.add(resolved)
    return files


def set_reproducibility(seed: int = 42):
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False



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
    legacy_subpage_dir, legacy_naming_dir = get_legacy_model_dirs()

     
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

    subpage_models = collect_model_files(subpage_dir, legacy_subpage_dir)
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

    naming_models = collect_model_files(naming_dir, legacy_naming_dir)
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

    