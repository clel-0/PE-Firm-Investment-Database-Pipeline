import numpy as np
from bs4 import BeautifulSoup as B
from bs4 import Tag
from sentence_transformers import SentenceTransformer
import torch
import torch.nn.functional as F


from step3_attempt3 import name_from_src
from step3_attempt4 import name_from_href
from step3_helperFunctions import inner_text_logic, _norm
from text_scoring import element_path_signature
#will be used to assign groupIDs to nodes

"""
1) Convert bs4 html to tree with tags as nodes, and one-way edges from parent to child.
2) For each node:
2.1) For each of the attributes (tagName, class, UrlText, UrlType, InnerText), compute the vector embedding of the attribute value string using sentence transformer model (351 dim vector).
2.2) Project the embeddings of each attribute into a: 100 dim (SBERT) vector for tagName, UrlText, InnerText, 50 dim SBERT vector for class, and 1 dim for UrlType.
2.3) Concatenate the projected embeddings into one 351 dim vector (100 + 100 + 100 + 50 + 50 = 351 dim).

__Process: 'Drip-down" Graph Neural Network to find portCo names.__
Assumptions:
- PortCo names can be found within the leaves of the html tree.
- Within the groups already preprocessed in Step 2, there exists a group that contains the portCo names.




3) GNN Architecture:
3.1) Add the add the head node to a list called the headList
3.2) Create the intial instruction vector for the head node:
    #aim: what is the long term instruction of the head node, in order to find portCo names within its child nodes?
    3.2.1.) h_i = ReLU(W_i*h_head + b_i)  (Wi: 351x351, bi: x351 are learnable parameters)
3.3) For each head node in headlist:
    (Let the standard vector of the head be h_s and the instruction vector of the head be h_i (x351), and the same vectors of a child node be c_s and c_i respectively (x351).)
    #aim: what is the head node looking for in its child nodes, to identify portCo names?
    3.3.1) Take h_i to the standard query space via activation: h_query_s <- ReLU(Wqs *h_i + Bqs)  (Wqs: 351x351, bqs: x351 are learnable parameters)
    3.3.2) Take h_i to the instructive query space via activation: h_query_i <- ReLU(Wqi *h_i + Bqi)  (Wqi: 351x351, bqi: x351 are learnable parameters)
    3.3.3) For each child node of the head node:
        #aim: what type of instruction should the child node have, in order to help the head node find portCo names?
        3.3.3.0) Set c_i = ReLU(W_ci * c_s + b_ci)  (W_ci: 351x351, b_ci: x351 are learnable parameters)
        3.3.3.1) Take c_s to the key and value space via activation:
            #aim: what information does the child node contain that may be relevant to the head node?
            c_key <- ReLU(Wk*c_s + bk)  (Wk: 351x351, bk: x351 are learnable parameters)
            #desirable aim: c_context adds the context of the child node to its standard vector, so that the head node can better interpret the message from the child node.
            c_context <- ReLU(Wc1*c_s + Wc2*h_s + wc)  (Wc1: 351x351, Wc2: 351x351, wc: x351 are learnable parameters)
            c_instr <- ReLU(Wi1*c_i + Wi2*h_i + wi)  (Wi1: 351x351, Wi2: 351x351, wi: x351 are learnable parameters)
        3.3.3.2) Compute attention scores:
            #desirable aim: given the context within the head node, how does the child node relate to what the head node is looking for in terms of content?
            score_s = softmax((h_query_s^T . c_key) / sqrt(351))  (scalar)
            #desirable aim: given the instruction within the head node, how does the child node relate to what the head node is looking for in terms of instructions?
            score_i = softmax((h_query_i^T . c_key) / sqrt(351))  (scalar)
    3.3.4) For each child node of the head node:
        3.3.4.1) Compute the aggregate information from the child nodes:
            #desirable aim: if the score is high, the child node contains relevant information for the head node, so pass on its message.
            #ideally, if the messages are strong over time, then the system emergently simulates a consensus to say that this child node contains portCo names, by creating a strong vector component in a certain subspace.
            c_s = Normalise(c_s + score_s * c_context) (x351)
            c_i = Normalise(c_i + score_i * c_instr) (x351)
        3.3.4.2) Add this child node to the headlist if it has children.
    3.3.5) If any of the child nodes have at least one child node, remove the head node from the headlist, add all its child nodes to the headlist, and repeat from step 4.3.
3.5) After all head nodes have been processed, the headList will contain only leaf nodes.
4) Collate all the leaf nodes into their groups based on groupID. (Creating hashmap for referencing: groupID to node)
5) For each group:
    5.1) Compute the mean vector of all the leaf nodes within that group: g_mean = mean(h_s of all leaf nodes in group) (x351)
    5.2) Pass the group mean vector through a feedforward network (one layer for now) to compute a length 2 vec, containing: the portCo confidence score, a binary classification of whether the innertext or the UrlText contains the portCo names.
        portCo_score_vec = Sigmoid(Wg * g_mean + bg)  (Wg: 2x351, bg: x2 are learnable parameters)
6) Choose the group with the highest portCo confidence score (portCo_score_vec[0]) as the group containing portCo names. If portCo_score_vec[1] > 0.5, extract from InnerText, else extract from UrlText.

"""


model = SentenceTransformer('all-MiniLM-L6-v2')



#important step: clean up how previous nodes are stored, even in previous steps, to ensure that the bs4 nodes are stored properly.

#1) 
def convert_html_to_tree(soup: B, groupIDs: dict) -> dict:
    """
    Convert bs4 html to tree with tags as nodes, and one-way edges from parent to child.
    For each node, compute the 351 dim vector embedding as per the description above.
    Returns the tree structure, and the hashmap of tagID to node vector.

    Namely:

    Returns the head of the tree, where the node structure is as follows:
    {
        'children': list of child nodes (same structure),
        'tagID': int,
        'groupIDs': list,
        'tagName': str,
        'class': str,
        'UrlText': str,
        'UrlType': {-1,0,1}, (src => 1, href => 0, none => -1)
        'InnerText': str
    }

    (vector will be added later, as vectorisation is dependent on the above attributes)

    """
  
 
    def build_node(bs4_element) -> dict:
        
        class_raw = bs4_element.get('class', [])
        class_raw = _norm(" ".join(class_raw)) if class_raw else ""

        inner_text_raw = bs4_element.get_text(separator=' ', strip=True) if bs4_element.get_text() else ""   
        inner_text = inner_text_logic(inner_text_raw)

        if bs4_element.get('href'):
            url_text = name_from_href(bs4_element.get('href'))
            url_type = 0
        elif bs4_element.get('src'):
            url_text = name_from_src(bs4_element.get('src'))
            url_type = 1
        else:
            url_text = ""
            url_type = -1 #represents no url

        #groupID 
        sig = element_path_signature(bs4_element)
        sig = tuple(sig)

        sig_groups = groupIDs.get(sig, [])


        node = {
            'children': [],
            'groupIDs': sig_groups,
            'tagName': bs4_element.name if bs4_element.name else "",
            'class': class_raw,
            'UrlText': url_text,
            'UrlType': url_type,
            'InnerText': inner_text
        }

        
        

        return node    
    

    soup_heads = []
    soup_heads.append(soup.html) # starting from the html tag

    headcheck = True #this will be used to save the head node later

    tree_head = None

    #while loop that builds the tree: BFS traversal
    while soup_heads != []:
        current_bs4 = soup_heads.pop(0)
        current_tree_node = build_node(current_bs4)

        #sets the head node  
        if headcheck:
            tree_head = current_tree_node
            headcheck = False

        children = [
            c for c in current_bs4.children
            if isinstance(c, Tag)
        ]
        
        #builds the child nodes and appends them to the current tree node
        for child in children:
            if isinstance(child, B.Tag):
                child_node = build_node(child)
                current_tree_node['children'].append(child_node)
                soup_heads.append(child)
        

    return tree_head
    





#2)
def convert_node_to_vector(node, W_class, b_class, W_text, b_text) -> torch.Tensor:
    """
    For a given node from convert_html_to_tree, compute the 351 dim vector embedding as per the description above:

    [tagName (100 dim), class (50 dim), UrlText (100 dim), UrlType (1 dim), InnerText (100 dim)] -> concatenated to 351 dim vector

    W_class: weight matrix for class projection (50x384)
    b_class: bias vector for class projection (50 dim)

    W_text: weight matrix for text projection (100x384)
    b_text: bias vector for text projection (100 dim)

    """
    tagName_emb = model.encode(node['tagName'] if node['tagName'] else "", convert_to_numpy=True)
    UrlText_emb = model.encode(node['UrlText'] if node['UrlText'] else "", convert_to_numpy=True)
    InnerText_emb = model.encode(node['InnerText'] if node['InnerText'] else "", convert_to_numpy=True)
    class_emb_raw = model.encode(node['class'] if node['class'] else "", convert_to_numpy=True)

    b_text = b_text.reshape(-1, 1)  # Convert bias to column vector
    #projecting text embeddings
    def embed_and_project(emb):
        emb = emb.reshape(-1, 1)  # Convert to column vector: in .reshape(-1,1): -1 means to infer the correct number of rows, and 1 means 1 column, resulting in a column vector, regardless of original shape.
        emb = W_text @ emb + b_text
        return emb 

    tagName_emb, UrlText_emb, InnerText_emb = embed_and_project(tagName_emb), embed_and_project(UrlText_emb), embed_and_project(InnerText_emb)

    #UrlType embedding
    if node['UrlType'] == -1:
        UrlType_emb = np.array([-1.0]).reshape(-1,1)
    elif node['UrlType'] == 0:
        UrlType_emb = np.array([0.0]).reshape(-1,1)
    else:
        UrlType_emb = np.array([1.0]).reshape(-1,1)

    #projecting class embedding
    class_emb_raw = class_emb_raw.reshape(-1, 1)  # Convert to column vector
    b_class = b_class.reshape(-1, 1)  # Convert bias to column
    class_emb = W_class @ class_emb_raw + b_class


    #concatenate all embeddings
    vector = np.concatenate([
        tagName_emb.flatten(), 
        class_emb.flatten(),
        UrlText_emb.flatten(),
        InnerText_emb.flatten(),
        UrlType_emb.flatten()
    ]).reshape(-1,1)  # final_vector is now a column vector of shape (351, 1)

    node['vector'] = vector  # Store the vector in the node for later reference

    final_vector = torch.from_numpy(vector).float()

    return final_vector



def normalise_vector(v: torch.Tensor) -> torch.Tensor:
    """
    Normalise a vector to unit length.
    """
    return F.normalize(v, p=2, dim=-1)




#3)
def GNN_process(tree_head, W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci):

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

                raw_score_s_list.append((h_query_s.transpose @ c_key) / torch.sqrt(351))
                raw_score_i_list.append((h_query_i.transpose @ c_key) / torch.sqrt(351))

            #compute softmax scores
            raw_score_s_array = torch.Tensor(raw_score_s_list).flatten()
            raw_score_i_array = torch.Tensor(raw_score_i_list).flatten()
            score_s_array = torch.softmax(raw_score_s_array, dim=0)
            score_i_array = torch.softmax(raw_score_i_array, dim=0)

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



#4)
#note: each leaf may belong to multiple groups
def collate_leafnodes_by_group(headList):
    group_to_leafnodes = {}
    for leaf in headList:
        group_ids = leaf['groupIDs']
        for group_id in group_ids:
            if group_id not in group_to_leafnodes:
                group_to_leafnodes[group_id] = []
            group_to_leafnodes[group_id].append(leaf)
            
    return group_to_leafnodes


#5)
def group_scores(group_to_leafnodes, W_g, b_g):
    if not group_to_leafnodes:
        print("No groups found in leaf nodes.")
        return {}
    group_scores = {}
    for group_id, leaf_nodes in group_to_leafnodes.items():
        h_s_list = [leaf['standard'] for leaf in leaf_nodes]
        stacked = torch.hstack(h_s_list)

        g_mean = torch.mean(stacked, axis=1, keepdims=True)  # mean vector g_mean (x351)

        portCo_score_vec = 1 / (1 + torch.exp(-(W_g @ g_mean + b_g)))  # Sigmoid activation. Wg: 2x351, bg: x2 are learnable parameters

        group_scores[group_id] = portCo_score_vec.flatten()  # Store as 1D array

    return group_scores

#6) 
def select_group(group_score, group_to_leafnodes):
    best_group_id = max(group_score, key=lambda gid: group_score[gid][0])  # group with highest portCo confidence score
    best_group_score = group_score[best_group_id]
    
    extract_from_innertext = best_group_score[1] > 0.5

    selected_leaf_nodes = group_to_leafnodes[best_group_id]

    if extract_from_innertext:
        print("Extracting portCo names from InnerText.")
    else:
        print("Extracting portCo names from UrlText.")
    
    portCo_names = []
    for leaf in selected_leaf_nodes:
        if extract_from_innertext:
            portCo_names.append(leaf['InnerText'])
        else:
            portCo_names.append(leaf['UrlText'])

    print(f"Selected group ID: {best_group_id} with confidence score: {best_group_score[0]}")

    return portCo_names





def overall_GNN(soup: B, groupIDs: dict, W_class, b_class, W_text, b_text, W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci, W_g, b_g) -> list:
    """
    Overall GNN process to extract portCo names from HTML soup.
    """
    #1) Convert HTML to tree
    tree_head = convert_html_to_tree(soup, groupIDs)

    #2) Convert nodes to vectors
    def traverse_and_vectorise(node):
        convert_node_to_vector(node, W_class, b_class, W_text, b_text)
        for child in node['children']:
            traverse_and_vectorise(child)

    traverse_and_vectorise(tree_head)

    #3) GNN processing
    leafList = GNN_process(tree_head, W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci)

    #4) Collate leaf nodes by group
    group_to_leafnodes = collate_leafnodes_by_group(leafList)

    #5) Compute group scores
    group_score = group_scores(group_to_leafnodes, W_g, b_g)

    if not group_score:
        print("No group scores computed, returning empty portCo names list.")
        return []
    
    #6) Select best group and extract portCo names
    portCo_names = select_group(group_score, group_to_leafnodes)

    return portCo_names



def train_GNN(soup_groupID_dict, true_portCo_names_dict):
    """
    soup_group_ID_dict: dict of {sample_ID: (soup, groupIDs)}
    true_portCo_names_dict: dict of {sample_ID: [true_portCo_names]}

    1) Train in a supervised manner to adjust the weights of the GNN to better predict portCo names.
    (Yet to explore semi-supervised methods, due to the complexity of simulating a html tree structure, for PE firm websites.)

        Initially, define all torch.nn.Parameter weights here, and then use an optimizer to train them based on loss between predicted portCo names and true portCo names.

        This will be done using torch.optim.Adam optimizer, and a suitable loss function (e.g., cross-entropy loss for classification), in a mini-batch training loop. Mini-batch size should similtaneously minimise overfitting while also not drowning out the intricacies of each individual sample.

        Note that cross entropy should also take into account what percentage of the group the GNN correctly predicted. Furthermore, the difference between the length of the predicted portCo names list and the true portCo names list can be used as a penalty signal. This is because, due to the scarcity of the data, we need every bit of signal we can get from each sample. 

    2) Reinforcement training: Use running window for loss function, and use user feedback to adjust the weights of the GNN to better predict portCo names.
    (Note that this is the same as the first step, however what needs to be implemented is interactivity with the user)

    What to do now:
    Step 1) learn about cross-entropy loss functions in pytorch, and how to implement them.
    Step 2) Write the first part of the training loop, with forward pass and loss computation.
    Step 3) Collate the data: gather all the portfolio websites and manually pair them with true portCo names. 
    Step 4) Run and debug the training loop, until the loop validly runs.
    Step 5) Create a discrete spread of each hyperparameter, being aware of which ones correlate with others (may need grid spread for those)
    Step 6) Run hyperparameter tuning using optuna or similar library, to find the best hyperparameters for the GNN.

    (GIVEN THAT THE FIRST PART WORKS)

    Step 7) Create reinforcement learning training loop, using reward signals based on percentage of correct portCo names predicted. The code should be similar to the first part, however interactivity with the user will be needed to provide feedback on the predictions.  



    """
    