if __package__:
    from .C_subpage_GNN_process import normalise_col_vecs
else:
    from C_subpage_GNN_process import normalise_col_vecs
import torch
import torch.nn.functional as F
import math 
import time


def s(x):
    return torch.sigmoid(x)


def b(x, a, cutoff = 0.5):
    cutoff = torch.tensor(cutoff, device=x.device, dtype=x.dtype)
    return (1 - s(a)) * x + s(a) * torch.sigmoid(a * (x - cutoff))


def is_candidate_node(node):
        """Candidate nodes are structural leaves OR non-leaf nodes with InnerText."""
        return (node.get('children') == []) or bool(node.get('InnerText'))


#This should only be done for the first layer
def initial_headlist_vec(headlist, W_i, b_i, dev):
    """
    Initialises headlist tensors

    returns h_standard_tensor, h_instruction_tensor
    """
    
    h_standard_list = []
    h_instruction_list = []


    if len(headlist) != 1:
        print("[NAMING][ERROR] headlist_vec should only be called on the first layer with a single head node.")
        return None, None
    
    for head in headlist:
        head['level'] = torch.tensor(0, device=dev, dtype=torch.float32)
        h_s = head['vector'] 
        h_standard_list.append(h_s)

        
    h_standard_tensor = torch.stack(h_standard_list, dim=1) #side by side 

    h_instruction_tensor = F.relu(W_i @ h_standard_tensor + b_i.unsqueeze(1)) 

    return h_standard_tensor, h_instruction_tensor


def query_batching(h_standard_tensor, h_instruction_tensor, W_qs, b_qs, W_qi, b_qi):
    """
    batch computes query vecs for layer

    returns: h_query_s_tensor, h_query_i_tensor
    """

    h_query_s_tensor = F.relu(W_qs @ h_standard_tensor + b_qs.unsqueeze(1))
    h_query_i_tensor = F.relu(W_qi @ h_instruction_tensor + b_qi.unsqueeze(1))

    return h_query_s_tensor, h_query_i_tensor



def child_vec_batching(headlist, W_ci, b_ci, W_k, b_k, dev):
    """
    creates c vec tensors for all children of headlist nodes. 
    Also creates parallel lists of num_children_per_head_node and child sig vecs for later use in boost scoring

    returns: c_standard_tensor, c_sig_tensor, c_instruction_tensor, c_key_tensor, num_children_per_head_node
    """
    c_standard_list = []
    num_children_per_head_node = []
    
    for head in headlist:
        for child in head['children']:
            child['level'] = head['level'] + torch.tensor(1, device=dev, dtype=torch.float32)
            c_standard_list.append(child['vector'])
            num_children_per_head_node.append(len(head['children']))
    
    c_standard_tensor = torch.stack(c_standard_list)
    

    c_instruction_tensor = F.relu(W_ci @ c_standard_tensor + b_ci.unsqueeze(1))
    c_key_tensor = F.relu(W_k @ c_standard_tensor + b_k.unsqueeze(1))

    return c_standard_tensor, c_instruction_tensor, c_key_tensor, num_children_per_head_node



def context_instr_batching(headlist, h_standard_tensor, h_instruction_tensor, c_standard_tensor, c_instruction_tensor, num_children_per_head_node, W_c1, W_c2, w_c, W_i1, W_i2, w_i):
    """
    Creates context and instruction tensors for all children of headlist nodes.

    context: will be added to standard vec to provide context of current layer
    instr: will be added to instruction vec to enrich instruction with info from current layer
    (idea of these two is that the GNN will be able to profile each node by their path from the root node, rather than a sole node in isolation)

    These will be scaled by their scores, only allowing the standard vec to enter the desired 
    subset of vecs if their scores are consistently high.

    """
    c_context_list = []
    c_instr_list = []

    cumulative_c = 0
    for i in range(len(headlist)):
        num_c = num_children_per_head_node[i]

        c_standard_slice = c_standard_tensor[:,cumulative_c:cumulative_c+num_c]
        c_instruction_slice = c_instruction_tensor[:,cumulative_c:cumulative_c+num_c]

        c_context_list.append(F.relu(W_c1 @ c_standard_slice + W_c2 @ h_standard_tensor[:,i] + w_c.unsqueeze(1)))
        c_instr_list.append(F.relu(W_i1 @ c_instruction_slice + W_i2 @ h_instruction_tensor[:,i] + w_i.unsqueeze(1)))

        cumulative_c += num_c

    return c_context_list, c_instr_list 



#since boost score is sum product, we can use matrix operations to batch calculate all dot products
def batch_boost(boost_score_now, num_children_per_head_node, headlist,dev):
    """
    batch computes boosts of all leaf nodes in the layer.

    The boost of a given leaf node is high when other leaf nodes which have high sig vec cosine similarities
    with the given node have parents with high scores.

    The raw score of the leaf node is passed through a function that approaches a discrete step-up function, the higher the boost is.

    returns list of boosts for all the leaves in that layer.

    """

    leaf_sig_list = []
    score_list = []

    #list of tensors, each tensor holds the sig vecs of gc nodes for a particular head node
    cumulative_c = 0
    
    for i in range(len(num_children_per_head_node)):
        leaf_sig_list.append(F.normalize(torch.stack(sig.flatten() for sig in boost_score_now[i][1]), dim=1)) #vecs are stacked on top of each other 

    leaf_sig_tensor = torch.cat(leaf_sig_list, dim=0) #transpose would look like: [c_of_head_1 | ... | c_of_head_n] (dim=0 => add rows) 

    # dot product substitution of cosine: cos(a,b) = (a.b)/(||a||||b||)
    cosine_tensor = leaf_sig_tensor @ leaf_sig_tensor.T #entry (i,j) is the cosine similarity between leaf vec i and leaf vec j
    
    for i in range(len(num_children_per_head_node)):
        score_list = score_list + boost_score_now[i][0] #scorelist: [c_of_head_1 | ... | c_of_head_n]
        score_vec = torch.stack(score_list) #shape (num_total_children,) order aligned with leaf_sig_tensor

    #vec containing all boost scores for each child node.
    #Thus, since each col in cosine_tensor lists all the cosine sims for a given c node, score_vec dot cosine_col_i gives the total boost for child node i.
    boosts_vec = score_vec @ cosine_tensor

    boost_list = []
    leaf_count = 0
    for head in headlist:
        for child in head['children']:
            if is_candidate_node(child):
                boost_list.append(boosts_vec[leaf_count])
            else:
                boost_list.append(torch.tensor(0.0, device=dev, dtype=torch.float32)) #non-candidate nodes get 0 boost
            leaf_count += 1

    return boost_list

def raw_score_calc(h_query_s_tensor, h_query_i_tensor, c_key_tensor, num_children_per_head_node, boost_vec):
    """
    uses classic attention score calc as the initial score, then passes through f with the boost_vec to get the final raw score for each child node.

    returns: raw_score_s_tensor, raw_score_i_tensor
    """

    c_count = 0 
    for i in range(len(num_children_per_head_node)):

        num_c = num_children_per_head_node[i]
        h_query_s_slice = h_query_s_tensor[:,i].unsqueeze(1) #shape (351, 1)
        h_query_i_slice = h_query_i_tensor[:,i].unsqueeze(1)

        c_key_slice = c_key_tensor[:,c_count:c_count+num_c] #shape (351, num_c)

        initial_score_s = (h_query_s_slice.T @ c_key_slice).flatten() / math.sqrt(h_query_s_tensor.size(0)) #shape (num_c,)
        initial_score_i = (h_query_i_slice.T @ c_key_slice).flatten() / math.sqrt(h_query_i_tensor.size(0))

        raw_score_s = []
        raw_score_i = []

        boost_slice = boost_vec[c_count:c_count+num_c]

        for j in range(num_c):
            raw_score_s.append(b(initial_score_s[j], boost_slice[j]))
            raw_score_i.append(b(initial_score_i[j], boost_slice[j]))

        c_count += num_c

    raw_score_s_vec = torch.stack(raw_score_s) #vec 
    raw_score_i_vec = torch.stack(raw_score_i) #vec

    return raw_score_s_vec, raw_score_i_vec


def new_vec_calcs(raw_score_s_vec, raw_score_i_vec, c_context_tensor, c_instr_tensor, c_standard_tensor, c_instruction_tensor):    
    """
    updates all standard and instructions vectors in a given layer with context and instr info respectively, scaled by scores.

    returns: new_C_s, new_C_i
    """
    w_s = torch.sigmoid(raw_score_s_vec)
    w_i = torch.sigmoid(raw_score_i_vec)
    score_s_array = w_s / (w_s.sum() + 1e-9)
    score_i_array = w_i / (w_i.sum() + 1e-9)

    
    new_C_s = normalise_col_vecs(c_standard_tensor + c_context_tensor * score_s_array.unsqueeze(0)) #use * operator to broadcast scores across context tensor cols.
    new_C_i = normalise_col_vecs(c_instruction_tensor + c_instr_tensor * score_i_array.unsqueeze(0)) #note: .unsqueeze(0) adds row dim (1,n), allowing scores to broadcast across cols in (c_num,n)

    return new_C_s, new_C_i, score_s_array


