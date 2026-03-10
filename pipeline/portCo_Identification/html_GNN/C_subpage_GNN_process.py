if __package__:
    from .A_convert_html_to_tree import convert_html_to_tree
    from .B_convert_node_to_vector import convert_tree_to_vectors
    from .C_functions import *
else:
    from A_convert_html_to_tree import convert_html_to_tree
    from B_convert_node_to_vector import convert_tree_to_vectors
    from C_functions import *
import torch
import torch.nn.functional as F
from bs4 import BeautifulSoup as B
import time
from collections import defaultdict





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

    href_nodes_set = set(soup.find_all(href=True))

    #prepare head tensor
    #SOLUTION_1
    h_tensor = torch.stack([tree_head.get('vector')], dim=1)  #shape (351, num_heads) stack process on 1 vec

    print("[SUBPAGE][FORWARD] Starting GNN layer propagation...")

    i = 0
    while not done:
        layer_t0 = time.perf_counter()
        print(f"[SUBPAGE][LAYER {i}] processing {len(headlist)} nodes...")
        done = True
        new_headlist = []

        #load in vectors to allow for batch tensor operations, which should speed up the process significantly compared to pure python iteration. Still doing the same drip-down process, but in batches.

        child_vec_dict, child_node_dict, hrefLeaves, new_headlist, new_leaves = load_node_vecs(headlist, href_nodes_set, hrefLeaves, new_headlist)

        h_info_batch, h_tensor = batch_h_info(h_tensor, W_info, b_info)

        v_key_batch, child_tensors = batch_v_key(headlist, child_vec_dict, W_key, b_key)

        if v_key_batch is None:
            print("Error in batch_v_key processing. Stopping GNN layer propagation to avoid misalignment issues.")
            return {}

        num_children_per_head = {}
        nodes_before_head = {}
        old_head_tag_ID = None
        
        for head in headlist:
            tag_id = head.get('tagID')
            len_children = len(child_node_dict[tag_id])
            num_children_per_head[tag_id] = len_children
            if old_head_tag_ID is None:
                nodes_before_head[tag_id] = 0
            nodes_before_head[tag_id] = nodes_before_head.get(old_head_tag_ID, 0) + num_children_per_head.get(old_head_tag_ID, 0)
            old_head_tag_ID = tag_id



        softmaxed_scores = score_children(h_info_batch, v_key_batch, num_children_per_head, headlist, dev)

        updated_child_tensors = apply_score_updates(h_tensor, child_tensors, softmaxed_scores, W_down, b_down, dev)

        stacked_updated_tensors = torch.cat(updated_child_tensors, dim=1)  #shape (351, num_children)        


        ##BIG ISSUE: NO LEAF WILL BE IN NEW_HEADLIST, SO THE BELOW FOR LOOP WONT WORK
        # SOLUTION: WE NEED TO CONSTRUCT A MAP TO IDENTIFY WHICH CHILD NODES WERE PROCESSED AND FURTHERMORE WHERE THEY ARE IN STACKED_UPDATED_TENSORS    
        for head in headlist:
            nodes_before = nodes_before_head.get(head.get('tagID'), 0)
            for idx, child in enumerate(child_node_dict[head.get('tagID')]):
                if child in new_leaves:
                    child['vector'] = stacked_updated_tensors[:, nodes_before + idx]  #update the vector of the child node with the corresponding updated tensor, only if needed i.e. only for nodes that will be href leaves.

        h_tensor = stacked_updated_tensors
  
        headlist = new_headlist

        if new_headlist:
            done = False #new heads with href descendants were added, so we are not done yet
        
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

