

from A_convert_html_to_tree import convert_html_to_tree
from B_convert_node_to_vector import convert_node_to_vector
import torch
import torch.nn.functional as F
from bs4 import BeautifulSoup as B

def normalise_vector(v: torch.Tensor) -> torch.Tensor:
    """
    Normalise a vector to unit length.
    """
    return F.normalize(v, p=2, dim=-1)


def portfolio_page_finder_GNN(soup: B, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final):
    """
    use a simpler drip-down process, where the head node just passes down one vec to its children, and the children update their vectors based on that vec. Now, a href-leaf in this case is defined as a node with a href attribute, and no descendants with href attributes. So in this case, the candidate nodes are the href-leaf nodes.

    
    W_final: weight matrix for final scoring (1x351)
    b_final: bias vector for final scoring (1 dim)

    W_down: weight matrix for downward message passing (351x351)
    b_down: bias vector for downward message passing (351 dim)



    """

    tree_head = convert_html_to_tree(soup)  #no groupIDs needed for this task

    #Convert nodes to vectors
    def traverse_and_vectorise(node):
        convert_node_to_vector(node, W_class, b_class, W_text, b_text, W_sig)
        for child in node['children']:
            traverse_and_vectorise(child)

    traverse_and_vectorise(tree_head)


    #GNN processing to find href-leaves
    headlist = [tree_head]
    hrefLeaves = []
    done = False

    while not done:

        done = True

        for head in headlist:

            if not head:
                continue
            
            if not head['bs4_element'].find_all(href=True):
                #this is a href-leaf
                hrefLeaves.append(head)
                continue

            done = False #still more to process; if all were processed, while loop would have skipped due to continue above

            new_headlist = []

            score_list = []

            for child in head['children']:
                new_headlist.append(child)
                v = child['vector']
                h_info = F.relu(W_info @ head['vector'] + b_info)
                v_key = F.relu(W_key @ v + b_key)

                score = (h_info.transpose(0,1) @ v_key) / torch.sqrt(torch.tensor([351.0]))
                score_list.append(score)
            
            score_array = torch.stack(score_list).flatten()
            score_softmax = torch.softmax(score_array, dim=0)

            for child, score in zip(head['children'], score_softmax):
                v = child['vector']
                v = normalise_vector(v + score * F.relu(W_down @ head['vector'] + b_down))
                child['vector'] = v

                
            headlist = new_headlist
                

    #After processing, compute final scores for href-leaves

    scores = torch.stack([F.sigmoid(W_final @ leaf['vector'] + b_final) for leaf in hrefLeaves]).flatten()

    
    hrefleaf_to_score = {leaf: score for leaf, score in zip(hrefLeaves, scores)} #have to leave score as a tensor for training, or else autograd will break

    return hrefleaf_to_score #note: since this will be trained, we cannot include max hrefleaf selection here, as that would be non-differentiable.

