if __package__:
    from .C_subpage_GNN_process import normalise_col_vecs
    from .D_functions import is_candidate_node, initial_headlist_vec, query_batching, child_vec_batching, context_instr_batching, batch_boost, raw_score_calc, new_vec_calcs
else:
    from C_subpage_GNN_process import normalise_col_vecs
    from .D_functions import *
import torch
import torch.nn.functional as F
import math 
import time


def s(x):
    return torch.sigmoid(x)


def f(x, a, cutoff = 0.5):
    cutoff = torch.tensor(cutoff, device=x.device, dtype=x.dtype)
    return (1 - s(a)) * x + s(a) * torch.sigmoid(a * (x - cutoff))

#NEW LEAF DEFINITION: ANY NODES WITH NO CHILDREN, OR ANY NODES WITH INNER TEXT (EVEN IF THEY HAVE CHILDREN, AS THEY MAY BE PORTCO NAMES WITH SUBSIDIARY STRUCTURE BELOW THEM)

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
    
    #boost structure: {c_idx:[[scores],[sig_vecs]]}
    boost_score_now = []
    boost_score_later = []


    layer_idx = 0
    while not done:
        layer_t0 = time.perf_counter()
        print(f"[NAMING][LAYER {layer_idx}] processing {len(headList)} nodes...")
        new_headList = []

        boost_score_now = boost_score_later
        boost_score_later = []
        #idea: list of boosts will be summed and applied to gc nodes, based on cosine similarity of the sig vectors from where the boost originated
        # this allows for 'alerting' nodes to be aware of high-scoring grandchildren nodes in other branches, and adjust their own scores accordingly
        

        
        if atStart:
            h_standard_tensor, h_instruction_tensor = initial_headlist_vec(headList, W_i, b_i, dev)

        h_query_s_tensor, h_query_i_tensor = query_batching(h_standard_tensor, h_instruction_tensor, W_qs, b_qs, W_qi, b_qi)

        c_standard_tensor, c_instruction_tensor, c_key_tensor, num_children_per_head_node = child_vec_batching(headList,W_ci, b_ci, W_k, b_k, dev)

        c_context_list, c_instr_list = context_instr_batching(headList, h_standard_tensor, h_instruction_tensor, c_standard_tensor, c_instruction_tensor, num_children_per_head_node, W_c1, W_c2, w_c, W_i1, W_i2, w_i)


        ### THE BELOW BOOSTING MECHANISM OPERATES ON THE OBSERVATION THAT THE CORRECT GROUP OF LEAF NODES TEND TO BE ON THE SAME LEVEL, SO IF A HIGH-SCORING NODE IS FOUND, OTHER NODES ON THE SAME LEVEL ARE ALERTED OF THE POSSIBILITY OF THEIR CHILDREN BEING PORTCO NAMES ###
        # check if any grandchildren are leaves; if so, AND the child has a high score, 'inform' all other nodes 
        # to be alert to their grandchildren possibly being portCo names. This will be done by passing the gc scores through a non-linear fct based on boost_score_now
        # namely, as boost_score_now -> 1, f -> 1_(x>=0.8), and as boost_score_now -> 0, f -> identity. This way, if there are many high-scoring grandchildren nodes, all other nodes will be alerted to the possibility of their grandchildren being portCo names.
        # furthermore, boosting will be weighted by cosine similarity between gc sig vecs.
        boost_list = batch_boost(boost_score_now, num_children_per_head_node, headList,dev)

        raw_score_s_vec, raw_score_i_vec = raw_score_calc(h_query_s_tensor, h_query_i_tensor, c_key_tensor, num_children_per_head_node, boost_list)
        
        new_C_s, new_C_i, score_s_array = new_vec_calcs(raw_score_s_vec, raw_score_i_vec, torch.cat(c_context_list, dim=1), torch.cat(c_instr_list, dim=1), c_standard_tensor, c_instruction_tensor)

        h_standard_tensor = new_C_s
        h_instruction_tensor = new_C_i


        c_idx = 0  
        new_headList = []
        for head in headList:
            for child, score in zip(head['children'], score_s_array):
                boost_score_later[c_idx] = [[],[]]
                for gc in child['children']:
                    if gc['children'] == [] or bool(gc.get('InnerText')): 
                        boost_score_later[c_idx][0].append(score)  #store both score and sig_vector for later use in leaf scoring
                        boost_score_later[c_idx][1].append(gc['sig_vector'])
                c_idx += 1

                if is_candidate_node(child) and child.get('tagID') not in seen_leaf_ids:
                    leafList.append(child)
                    seen_leaf_ids.add(child.get('tagID'))
                else: 
                    new_headList.append(child)
        
       
         

        done = all(head.get('children') == [] for head in new_headList)

        headList = new_headList
        print(
            f"[NAMING][LAYER {layer_idx}] done in {time.perf_counter() - layer_t0:.3f}s; "
            f"next_layer_nodes={len(headList)}, candidate_leaves_so_far={len(leafList)}"
        )
        layer_idx += 1

    print(f"[NAMING][FORWARD] Completed in {time.perf_counter() - run_start:.3f}s; total_candidates={len(leafList)}")

    return leafList 

































        # for head in headList: 

        #     leaf_id = head.get('tagID')
        #     if is_candidate_node(head) and leaf_id not in seen_leaf_ids:
        #         leafList.append(head)
        #         seen_leaf_ids.add(leaf_id)

        #     if head['children'] == []:
        #         if atStart:
        #             head['level'] = torch.tensor(0, device=dev, dtype=torch.float32)
        #             h_s = head['vector']  # standard vector
        #             h_i = F.relu(W_i @ h_s + b_i)  # instruction vector
        #             head['standard'] = h_s
        #             head['instruction'] = h_i
        #             atStart = False
        #         new_headList.append(head)
        #         continue #leaf node, nothing to process


        #     if atStart:
        #         head['level'] = torch.tensor(0, device=dev, dtype=torch.float32)
        #         h_s = head['vector']  # standard vector
        #         h_i = F.relu(W_i @ h_s + b_i)  # instruction vector
        #         atStart = False
        #     else:
        #         h_s = head['standard']
        #         h_i = head['instruction']


        #     #compute queries
        #     h_query_s = F.relu(W_qs @ h_i + b_qs)
        #     h_query_i = F.relu(W_qi @ h_i + b_qi)

        #     #parallel lists for child nodes
        #     raw_score_s_list = []
        #     raw_score_i_list = []
        #     c_context_list = []
        #     c_instr_list = []
       
            
        #     #construct the lists first
        #     for child in head['children']:
        #         child['level'] = head['level'] + torch.tensor(1, device=dev, dtype=torch.float32)
        #         c_s = child['vector']
        #         c_sig = child['sig_vector']
        #         c_i = F.relu(W_ci @ c_s + b_ci)

        #         c_key = F.relu(W_k @ c_s + b_k)
        #         c_context_list.append(F.relu(W_c1 @ c_s + W_c2 @ h_s + w_c))
        #         c_instr_list.append(F.relu(W_i1 @ c_i + W_i2 @ h_i + w_i))

        #         boost = torch.tensor(0.0, device=dev, dtype=torch.float32) #ensure boost is on correct device

        #         for (score, sig_vec) in boost_score_now:
        #             boost += score * F.cosine_similarity(c_sig.flatten(), sig_vec.flatten(), dim=0)

        #         raw_score_s_list.append(f(torch.dot(h_query_s, c_key) / math.sqrt(h_query_s.numel()), boost))
        #         raw_score_i_list.append(f(torch.dot(h_query_i, c_key) / math.sqrt(h_query_i.numel()), boost)) 

                
                            

        #     #compute softmax scores
        #     raw_score_s_array = torch.stack(raw_score_s_list).flatten() #using stack to convert list of tensors to single tensor
        #     raw_score_i_array = torch.stack(raw_score_i_list).flatten()
        #     w_s = torch.sigmoid(raw_score_s_array)
        #     w_i = torch.sigmoid(raw_score_i_array)
        #     score_s_array = w_s / (w_s.sum() + 1e-9)
        #     score_i_array = w_i / (w_i.sum() + 1e-9)
        #     #update child nodes
            
        #     for child,context,instr,score_s,score_i in zip(head['children'],c_context_list,c_instr_list,score_s_array, score_i_array):
        #         c_s = child['vector']
        #         c_i = F.relu(W_ci @ c_s + b_ci)

        #         c_s = normalise_col_vecs(c_s + score_s * context)
        #         c_i = normalise_col_vecs(c_i + score_i * instr)

        #         child['standard'] = c_s
        #         child['instruction'] = c_i

        #         new_headList.append(child) #at the end, only leaf nodes will remain in headList

                
                
       