import os
import random
import requests
import torch
import json
import hashlib
from bs4 import BeautifulSoup

from .portco_name_training_functions import train_naming_GNN
from .subpage_training_functions import train_portfolio_page_finder_GNN

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

    return W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams


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




def collect_model_files(directory: Path) -> list[Path]:
    files = []
    seen = set()
   
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


