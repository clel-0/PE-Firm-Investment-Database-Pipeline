if __package__:
    from .A_convert_html_to_tree import convert_html_to_tree
    from .B_convert_node_to_vector import convert_tree_to_vectors
else:
    from A_convert_html_to_tree import convert_html_to_tree
    from B_convert_node_to_vector import convert_tree_to_vectors
import torch
import torch.nn.functional as F
from bs4 import BeautifulSoup as B
import time

def normalise_vector(v: torch.Tensor) -> torch.Tensor:
    """
    Normalise a vector to unit length.
    """
    return F.normalize(v, p=2, dim=0) #dim=0 means use the only dimension, p=2 means L2 norm


def portfolio_page_finder_GNN(soup: B, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final, dev='cpu') -> dict:
    """
    use a simpler drip-down process, where the head node just passes down one vec to its children, and the children update their vectors based on that vec. Now, a href-leaf in this case is defined as a node with a href attribute, and no descendants with href attributes. So in this case, the candidate nodes are the href-leaf nodes.

    
    W_final: weight matrix for final scoring (1x351)
    b_final: bias vector for final scoring (1 dim)

    W_down: weight matrix for downward message passing (351x351)
    b_down: bias vector for downward message passing (351 dim)



    """

    

    run_start = time.perf_counter()
    print("[SUBPAGE][FORWARD] Starting portfolio_page_finder_GNN forward pass.")

    tree_t0 = time.perf_counter()
    tree_head, _ = convert_html_to_tree(soup)  #no groupIDs needed for this task
    print(f"[SUBPAGE][FORWARD] HTML converted to tree in {time.perf_counter() - tree_t0:.3f}s.")
    if not tree_head:
        return {}

    vec_t0 = time.perf_counter()
    convert_tree_to_vectors(tree_head, W_class, b_class, W_text, b_text, W_sig, device=dev)
    print(f"[SUBPAGE][FORWARD] Nodes converted to vectors in {time.perf_counter() - vec_t0:.3f}s.")

    #GNN processing to find href-leaves
    headlist = [tree_head]
    hrefLeaves = []
    done = False

    print("[SUBPAGE][FORWARD] Starting GNN layer propagation...")

    i = 0
    while not done:
        layer_t0 = time.perf_counter()
        print(f"[SUBPAGE][LAYER {i}] processing {len(headlist)} nodes...")
        done = True
        new_headlist = []

        for head in headlist:

            if not head:
                continue
            
            # manual traversal to find href-leaves to allow for more transparency in the process
            has_href = bool(head['bs4_element'] and head['bs4_element'].get('href'))
            has_href_descendant = False
            if head['bs4_element'] is not None:
                for descendant in head['bs4_element'].descendants:
                    if descendant is head['bs4_element']:
                        continue
                    if getattr(descendant, 'get', None) and descendant.get('href'):
                        has_href_descendant = True
                        break
            if has_href and not has_href_descendant:
                #this is a href-leaf
                hrefLeaves.append(head)
                continue

            done = False #still more to process; if all were processed, while loop would have skipped due to continue above

            score_list = []

            for child in head['children']:
                new_headlist.append(child)
                v = child['vector']
                h_info = F.relu(W_info @ head['vector'] + b_info)
                v_key = F.relu(W_key @ v + b_key)

                score = (h_info.transpose(0,1) @ v_key) / torch.sqrt(torch.tensor([351.0], device=dev, dtype=torch.float32))  #scaling by sqrt of dimension
                score_list.append(score)

            if not score_list:
                continue
            
            score_array = torch.stack(score_list).flatten()
            score_softmax = torch.softmax(score_array, dim=0)

            for child, score in zip(head['children'], score_softmax):
                v = child['vector']
                v = normalise_vector(v + score * F.relu(W_down @ head['vector'] + b_down))
                child['vector'] = v

                
        headlist = new_headlist
        print(
            f"[SUBPAGE][LAYER {i}] done in {time.perf_counter() - layer_t0:.3f}s; "
            f"next_layer_nodes={len(headlist)}, href_leaves_so_far={len(hrefLeaves)}"
        )
        i += 1

    #After processing, compute final scores for href-leaves

    if not hrefLeaves:
        print("No href-leaf nodes found during GNN processing.")
        return {}

    scores = torch.stack([W_final @ leaf['vector'] + b_final for leaf in hrefLeaves]).flatten()

    id_to_score = {leaf['tagID']: score for leaf, score in zip(hrefLeaves, scores)} #have to leave score as a tensor for training, or else autograd will break
    #zip can be used on scores since pytorch tensors are iterable over their first dimension, where each element is a scalar tensor.
    print(
        f"[SUBPAGE][FORWARD] GNN processing completed. href_leaf_count={len(hrefLeaves)}; "
        f"score_count={len(id_to_score)}; total_forward_time={time.perf_counter() - run_start:.3f}s"
    )
    return id_to_score #note: since this will be trained, we cannot include max hrefleaf selection here, as that would be non-differentiable.

