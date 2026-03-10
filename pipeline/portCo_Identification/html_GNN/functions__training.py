
import torch
import torch.nn.functional as F
import math
import time
from pathlib import Path
from collections import defaultdict
import os

if __package__:
    from .A_convert_html_to_tree import convert_html_to_tree
    from .B_convert_node_to_vector import convert_tree_to_vectors
    from .C_subpage_GNN_process import portfolio_page_finder_GNN
    from .D_naming_GNN_process import GNN_process_portCo, f
    from .E_name_grouping import scores
else:
    from A_convert_html_to_tree import convert_html_to_tree
    from B_convert_node_to_vector import convert_tree_to_vectors
    from C_subpage_GNN_process import portfolio_page_finder_GNN
    from D_naming_GNN_process import GNN_process_portCo, f
    from E_name_grouping import scores


def get_model_dirs() -> tuple[Path, Path]:
    base = Path(__file__).resolve().parents[3]
    subpage_dir = base / 'output' / 'subpage_GNN_models'
    naming_dir = base / 'output' / 'naming_GNN_models'
    os.makedirs(subpage_dir, exist_ok=True)
    os.makedirs(naming_dir, exist_ok=True)
    return subpage_dir, naming_dir



def sync_device_if_cuda(dev):
    if isinstance(dev, torch.device):
        is_cuda = dev.type == 'cuda'
    else:
        is_cuda = str(dev).startswith('cuda')

    if is_cuda and torch.cuda.is_available():
        torch.cuda.synchronize()


def timed_call(label: str, fn, dev):
    sync_device_if_cuda(dev)
    start = time.perf_counter()
    result = fn()
    sync_device_if_cuda(dev)
    elapsed = time.perf_counter() - start
    print(f"[TIMING] {label}: {elapsed:.3f}s")
    return result, elapsed











            
            