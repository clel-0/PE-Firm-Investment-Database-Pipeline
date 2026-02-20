if __package__:
    from .C_subpage_GNN_process import normalise_vector
else:
    from C_subpage_GNN_process import normalise_vector
import torch
import torch.nn.functional as F
import math 
import time


def s(x):
    return torch.sigmoid(x)


def f(x, a, cutoff = 0.5):
    a = torch.tensor(a, device=x.device, dtype=x.dtype)
    cutoff = torch.tensor(cutoff, device=x.device, dtype=x.dtype)
    return (1 - s(a)) * x + s(a) * torch.sigmoid(a * (x - cutoff))


#may need upflow from leaves to hrefs later, if the model underperforms
def GNN_process_portCo(tree_head, W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci, dev='cpu'):
    """
    __Process: 'Drip-down" Graph Neural Network to find portCo names.__
        Assumptions:
            - PortCo names can be found within structural leaves and non-leaf nodes with InnerText.
            - Each node has a 'vector' attribute (351 dim) already computed.
        
    """

    
    run_start = time.perf_counter()
    print("[NAMING][FORWARD] Starting GNN_process_portCo.")

    if not tree_head:
        print("[NAMING][FORWARD] Empty tree; returning no candidates.")
        return []

    done = False
    atStart = True
    headList = [tree_head]
    leafList = []
    seen_leaf_ids = set()
    
    boost_score_now = []
    boost_score_later = []

    def is_candidate_node(node):
        """Candidate nodes are structural leaves OR non-leaf nodes with InnerText."""
        return (node.get('children') == []) or bool(node.get('InnerText'))

    layer_idx = 0
    while not done:
        layer_t0 = time.perf_counter()
        print(f"[NAMING][LAYER {layer_idx}] processing {len(headList)} nodes...")
        new_headList = []

        boost_score_now = boost_score_later
        boost_score_later = []
        #idea: list of boosts will be summed and applied to gc nodes, based on cosine similarity of the sig vectors from where the boost originated
        # this allows for 'alerting' nodes to be aware of high-scoring grandchildren nodes in other branches, and adjust their own scores accordingly
        
        
        for head in headList: 

            leaf_id = head.get('tagID')
            if is_candidate_node(head) and leaf_id not in seen_leaf_ids:
                leafList.append(head)
                seen_leaf_ids.add(leaf_id)

            if head['children'] == []:
                if atStart:
                    head['level'] = torch.tensor(0, device=dev, dtype=torch.float32)
                    h_s = head['vector']  # standard vector
                    h_i = F.relu(W_i @ h_s + b_i)  # instruction vector
                    head['standard'] = h_s
                    head['instruction'] = h_i
                    atStart = False
                new_headList.append(head)
                continue #leaf node, nothing to process


            if atStart:
                head['level'] = torch.tensor(0, device=dev, dtype=torch.float32)
                h_s = head['vector']  # standard vector
                h_i = F.relu(W_i @ h_s + b_i)  # instruction vector
                atStart = False
            else:
                h_s = head['standard']
                h_i = head['instruction']


            #compute queries
            h_query_s = F.relu(W_qs @ h_i + b_qs)
            h_query_i = F.relu(W_qi @ h_i + b_qi)

            #parallel lists for child nodes
            raw_score_s_list = []
            raw_score_i_list = []
            c_context_list = []
            c_instr_list = []
       
            
            #construct the lists first
            for child in head['children']:
                child['level'] = head['level'] + torch.tensor(1, device=dev, dtype=torch.float32)
                c_s = child['vector']
                c_sig = child['sig_vector']
                c_i = F.relu(W_ci @ c_s + b_ci)

                c_key = F.relu(W_k @ c_s + b_k)
                c_context_list.append(F.relu(W_c1 @ c_s + W_c2 @ h_s + w_c))
                c_instr_list.append(F.relu(W_i1 @ c_i + W_i2 @ h_i + w_i))

                boost = torch.tensor(0.0, device=dev, dtype=torch.float32) #ensure boost is on correct device

                for (score, sig_vec) in boost_score_now:
                    boost += score * F.cosine_similarity(c_sig.flatten(), sig_vec.flatten(), dim=0)

                raw_score_s_list.append(f(torch.dot(h_query_s, c_key) / math.sqrt(h_query_s.numel()), boost))
                raw_score_i_list.append(f(torch.dot(h_query_i, c_key) / math.sqrt(h_query_i.numel()), boost)) 

                
                            

            #compute softmax scores
            raw_score_s_array = torch.stack(raw_score_s_list).flatten() #using stack to convert list of tensors to single tensor
            raw_score_i_array = torch.stack(raw_score_i_list).flatten()
            w_s = torch.sigmoid(raw_score_s_array)
            w_i = torch.sigmoid(raw_score_i_array)
            score_s_array = w_s / (w_s.sum() + 1e-9)
            score_i_array = w_i / (w_i.sum() + 1e-9)
            #update child nodes
            for child,context,instr,score_s,score_i in zip(head['children'],c_context_list,c_instr_list,score_s_array, score_i_array):
                c_s = child['vector']
                c_i = F.relu(W_ci @ c_s + b_ci)

                c_s = normalise_vector(c_s + score_s * context)
                c_i = normalise_vector(c_i + score_i * instr)

                child['standard'] = c_s
                child['instruction'] = c_i

                new_headList.append(child) #at the end, only leaf nodes will remain in headList

                # check if any grandchildren are leaves; if so, AND the child has a high score, 'inform' all other nodes 
                # to be alert to their grandchildren possibly being portCo names. This will be done by passing the gc scores through a non-linear fct based on boost_score_now
                # namely, as boost_score_now -> 1, f -> 1_(x>=0.8), and as boost_score_now -> 0, f -> identity. This way, if there are many high-scoring grandchildren nodes, all other nodes will be alerted to the possibility of their grandchildren being portCo names.
                # furthermore, boosting will be weighted by cosine similarity between gc sig vecs.
                
                for gc in child['children']:
                    if gc['children'] == []:
                        boost_score_later.append((score_s, gc['sig_vector']))  #store both score and sig_vector for later use in leaf scoring

        done = all(head.get('children') == [] for head in new_headList)

        headList = new_headList
        print(
            f"[NAMING][LAYER {layer_idx}] done in {time.perf_counter() - layer_t0:.3f}s; "
            f"next_layer_nodes={len(headList)}, candidate_leaves_so_far={len(leafList)}"
        )
        layer_idx += 1

    print(f"[NAMING][FORWARD] Completed in {time.perf_counter() - run_start:.3f}s; total_candidates={len(leafList)}")

    return leafList 
