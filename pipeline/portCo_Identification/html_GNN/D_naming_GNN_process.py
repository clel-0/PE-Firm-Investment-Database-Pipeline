
from C_subpage_GNN_process import normalise_vector
import torch
import torch.nn.functional as F
import math 


def GNN_process_portCo(tree_head, W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci):
    """
    __Process: 'Drip-down" Graph Neural Network to find portCo names.__
        Assumptions:
            - PortCo names can be found within the leaves of the html tree.
            - Each node has a 'vector' attribute (351 dim) already computed.
        
    """

    done = False
    atStart = True
    headList = [tree_head]
    leafList = []

    while not done:
        new_headList = []
        for head in headList: 

            
            if head['children'] == []:
                if atStart:
                    h_s = head['vector']  # standard vector
                    h_i = F.relu(W_i @ h_s + b_i)  # instruction vector
                    head['standard'] = h_s
                    head['instruction'] = h_i
                    atStart = False
                continue #leaf node, nothing to process


            if atStart:
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
                c_s = child['vector']
                c_i = F.relu(W_ci @ c_s + b_ci)

                c_key = F.relu(W_k @ c_s + b_k)
                c_context_list.append(F.relu(W_c1 @ c_s + W_c2 @ h_s + w_c))
                c_instr_list.append(F.relu(W_i1 @ c_i + W_i2 @ h_i + w_i))

                raw_score_s_list.append(torch.dot(h_query_s, c_key) / math.sqrt(h_query_s.numel()))
                raw_score_i_list.append(torch.dot(h_query_i, c_key) / math.sqrt(h_query_s.numel()))

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

        headList = new_headList



        done = True
        for head in headList:
            if head['children'] != []:
                done = False #still more to process
            else:
                leafList.append(head)  #collect leaf nodes. 
        
    return leafList 
