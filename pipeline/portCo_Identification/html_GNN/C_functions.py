

from collections import defaultdict
import torch.nn.functional as F
import torch

def normalise_col_vecs(T: torch.Tensor) -> torch.Tensor:
    """
    Normalise col vecs of tensor T to unit length.
    """
    return F.normalize(T, p=2, dim=0) #dim=0 means normalise col vecs




def load_node_vecs(headlist, href_node_set, hrefLeaves, new_headlist) -> tuple[defaultdict, defaultdict, list, list, set]:

    new_leaves = set()

    child_vec_dict = defaultdict(list) #key: id of head node, value: list of child vectors (in same order as children list)
    child_node_dict = defaultdict(list) #key: id of head node, value: list of child nodes (in same order as children list)

    for head in headlist:
        if not head:
            continue

        h_id = head.get('tagID')
        if isinstance(head['children'], list) and isinstance(h_id, int):
            try:
                for child in head['children']:
                    v = child.get('vector')
                    if v is None:
                        raise ValueError(f"Child node with tagID {child.get('tagID')} is missing 'vector' attribute.")
                          
                    element = child.get('bs4_element')
                    if element is None:
                        raise ValueError(f"Child node with tagID {child.get('tagID')} is missing 'bs4_element' attribute.")
                    desc = element.find(href=True) if element else None
                    in_href_node_set = element in href_node_set

                    if desc or in_href_node_set:
                        child_vec_dict[h_id].append(v)
                        child_node_dict[h_id].append(child)
                        if desc and (child not in new_headlist): # only nodes with href descendants should be added to new_headlist
                            new_headlist.append(child)
                        if not desc and in_href_node_set: #if the child itself is in the href node set, but it has no descendant with href, then it is a href-leaf and should be added to the hrefLeaves list
                            hrefLeaves.append(child) 
                            new_leaves.add(child)
            
            except Exception as e:
                print(f"Error processing children of head node with tagID {h_id}: {e}")
                child_vec_dict[h_id] = [] #if any error occurs, set the whole list to empty to avoid misalignment issues
                child_node_dict[h_id] = [] #if any error occurs, set the whole list to empty to avoid misalignment issues

        else:
            print(f"Head node with tagID {h_id} has invalid 'children' or 'tagID' attributes.")
            child_vec_dict[h_id] = [] #if head node has invalid children or tagID, set its child vec list to empty to avoid misalignment issues
            child_node_dict[h_id] = [] #if head node has invalid children or tagID, set its child node list to empty to avoid misalignment issues
        
    return child_vec_dict, child_node_dict, hrefLeaves, new_headlist, new_leaves



def batch_h_info(h_tensor, W_info, b_info):

    #h_tensor creation removed; h_tensor is already created either outside loop or in previous iteration as child_tensor

    #note: for h in head_vecs, h is a column vector
    h_info = F.relu(W_info @ h_tensor + b_info)  #shape (351, num_heads)

    return h_info, h_tensor #save calc time by reusing h_tensor


def batch_v_key(headlist, child_vec_dict, W_key, b_key):

    child_tensors = []
    for head in headlist:
        head_id = head.get('tagID')
        if head_id is not None:
            child_vecs = child_vec_dict[head_id]
            if child_vecs:
                child_tensor = torch.stack(child_vecs, dim=1)  #shape (351, num_children)
                child_tensors.append(child_tensor)
        else:
            print("Error: Head Node missing 'tagID' attribute. Stopping batch_v_key processing to avoid misalignment issues.")
            return None, None #if any head node is missing tagID, we cannot reliably process the child vectors, so we return None to indicate an error and stop processing. This is a rare edge case, but we handle it just in case.     
                

    v_tensor = torch.cat(child_tensors, dim=1)  #shape (351, num_children)

    v_key = F.relu(W_key @ v_tensor + b_key)  #shape (351, num_children)

    return v_key, child_tensors #return child_tensors for later use in applying score updates


def score_children(h_info_batch, v_key_batch, num_children_per_head, headlist, dev):
    #h_info_batch shape: (351, num_heads)
    #v_key_batch shape: (351, num_children)
    #list of num_children_per_head has length num_heads, and sum of elements equals num_children
    #note: num_children_per_head has order alignment with h_info_batch

    scores_list = []

    idx = 0

    num_children_list = [num_children_per_head[head.get('tagID')] for head in headlist]

    for i,num in enumerate(num_children_list):
        if num == 0:
            scores_list.append(torch.tensor([], device=dev))
        else:
            h_info = h_info_batch[:, i].unsqueeze(1)  #shape (351, 1)
            v_key = v_key_batch[:, idx:idx+num]  #shape (351, num)
            scores = h_info.transpose(0,1) @ v_key / torch.sqrt(torch.tensor([351.0], device=dev, dtype=torch.float32))  #shape (1 row vector of num children)
            scores_list.append(scores.flatten())  #append as 1D tensor of num children
            idx += num

    softmaxed_scores = [torch.softmax(s, dim=0) for s in scores_list]  #list of tensors, each tensor is the softmaxed scores for the children of a head node

    return softmaxed_scores


def apply_score_updates(head_tensor, child_tensors, softmaxed_scores, W_down, b_down, dev):
    
    down_boost = F.relu(W_down @ head_tensor + b_down)  #shape (351, num_heads)

    updated_child_tensors = []
    for head_idx, child_tensor in enumerate(child_tensors):
        scores = softmaxed_scores[head_idx]  #shape (num_children,)

        scaled_boosts = down_boost[:,head_idx].unsqueeze(1) * scores.unsqueeze(0)  #shape (351, num_children)
        #note: .unsqueeze(n) turns the vector into a matrix by adding a dimension of size 1 at dim n (eg unsqueeze(0) adds a new row dim (row considered 0th dim)

        updated_child_tensor = normalise_col_vecs(child_tensor + scaled_boosts)  #shape (351, num_children)

        updated_child_tensors.append(updated_child_tensor)
    
    return updated_child_tensors
