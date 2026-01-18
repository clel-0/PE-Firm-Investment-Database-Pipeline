import torch
import torch.nn.functional as F


            




#5)
"""
At the moment, the grouping section is closed, because of the limited data available for training.
Namely, the grouping process will increase parameters to be learned, and with limited data, this will lead to overfitting.
For now, we will simply score each leaf node individually, and then select portCo names based on a confidence threshold.
However, this may lead in more false positives, since there is no grouping to reinforce the scores, i.e. leaves will not communicate with each other to boost scores of similar leaves.
This will be revisited when more data is available, or if this version performs poorly.

"""
def scores(leaflist, W_s, b_s):
    if not leaflist:
        print("No leaf nodes provided for scoring.")
        return []
        
    confidence_scores = []
    type_scores = []

    for leaf in leaflist:
        v = leaf['vector']  # vector (351,1)

        portCo_score_vec = 1 / (1 + torch.exp(-(W_s @ v + b_s)))  # Sigmoid activation. Ws: 2x351, bs: x2 are learnable parameters
        
        confidence_scores.append(portCo_score_vec[0].item())  # confidence score
        type_scores.append(portCo_score_vec[1].item())  # type score

    return confidence_scores, type_scores
















"""



BELOW IS NOT USED ANYMORE: REPLACED BY EMERGENT GROUPING USING CLUSTERING OF LEAVES





"""





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




#6) note: due to max being non-differentiable, this step is done outside the training loop. This is fine, since no learning params are involved here.
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












from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2') #dim: 384


def confidence_scores(leafList, W_conf, b_conf):
    """
    For each leaf node in leafList, compute confidence score of being a portCo name.

    W_conf: weight matrix for confidence score projection (1x64)
    b_conf: bias scalar for confidence score projection (1 dim)

    """
    for leaf in leafList:
        h_s = leaf['standard']  # standard vector (64,1)
        conf_score = 1 / (1 + torch.exp(-(W_conf @ h_s + b_conf)))  # Sigmoid activation
        leaf['conf_score'] = conf_score.item()  # Store as scalar




def cluster_leafnodes(leafList, W_layer, b_layer, W_sig, b_sig, cluster_threshold=0.1):
    """
    Plan:
    This will be essentially weighted clustering of leaf nodes into groups, 
    based on vectors that stem from their path signatures. 
    The weights will be based on the confidence scores of the leaf nodes being portCo names.

    process:
    - pass leaf embedding through layer
    - for each leaf, compute distance to all other leaves. If distance < threshold, assign to same cluster.
    - compute cluster centroids as weighted average of leaf vectors in cluster, weights being confidence scores.
    - for each cluster, reposition leaf vectors to the weighted cluster centroid, namely for a vec with confidence score s, new_vec = old_vec + s * (centroid - old_vec)
    - then, pass the new leaf vectors through next layer, and so on.

    My theory: each layer will look for a certain type of pattern in the path signatures. Now, since the layers are continuous, pushing the leaf vectors towards the cluster centroids will help to reinforce the patterns that the layer is looking for, making it easier for the next layer to pick up on higher-level patterns. 
    Eventually, after several layers, the leaf vectors should converge towards a few distinct clusters that represent the most salient path signature patterns for portCo names. Note that low confidence leaves do not float towards centroids as much, so they will tend to remain more scattered, while high confidence leaves will cluster more tightly.
    Ideally, since the 

    W_layer: weight rank 3 tensor (num_layers x cluster_vec_dim = 64 x 64)
    b_layer: bias rank 2 tensor (num_layers x cluster_vec_dim = 64)

    W_sig: weight matrix for signature vector projection (64x384)
    b_sig: bias vector for signature vector projection (64 dim)

    """

    num_layers = W_layer.shape[0]

  
    for leaf in leafList: 
        sig_string = ''.join(leaf['sig'])  #convert path signature tuple to string
        sig_vector = torch.from_numpy(model.encode(sig_string, convert_to_numpy=True)).float().reshape(-1,1)  #column vector of shape (384,1)
        #project signature vector
        b_sig_col = b_sig.reshape(-1,1)  #convert bias to column

        sig_proj = F.sigmoid(W_sig @ sig_vector + b_sig_col)  #projected signature vector of shape (128,1)

        leaf["sig_vector"] = sig_proj  #store projected signature vector in leaf node


    for layer in range(num_layers):
        W_layer_l = W_layer[layer]  #shape (64,64)
        b_layer_l = b_layer[layer].reshape(-1,1)  #shape (64,1)

        