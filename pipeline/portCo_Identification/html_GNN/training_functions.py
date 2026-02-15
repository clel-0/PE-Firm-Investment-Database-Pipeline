
import torch
import torch.nn.functional as F
import math
import time
from pathlib import Path
from collections import defaultdict

from A_convert_html_to_tree import convert_html_to_tree
from B_convert_node_to_vector import convert_node_to_vector
from C_subpage_GNN_process import portfolio_page_finder_GNN
from D_naming_GNN_process import GNN_process_portCo, f
from E_name_grouping import scores

def train_naming_GNN(training_dict, naming_params_package, dev='cpu', batch_size=4, learning_rate=0.001, lambda1=1, lambda2=0.1, lambda3=0.1, dtype=torch.float32):
    
    torch.set_default_dtype(dtype)
    #set datetime
    datetime_str = time.strftime("%Y-%m-%d-%H-%M-%S")
    
    lambda1 = torch.tensor(lambda1, device=dev, dtype=dtype) #ensure on correct device
    lambda2 = torch.tensor(lambda2, device=dev, dtype=dtype)
    lambda3 = torch.tensor(lambda3, device=dev, dtype=dtype)

    """
    training_dict: dict of {sample_ID: (soup, true_scores, true_type)}
    true_scores: SORTED (by key) dict of nodeIDs: {1 if portCo name else 0}
    true_type: overall true type of text (1 for InnerText, 0 for UrlText)

    batch_size: int, number of samples per training batch

    ensure len(training_dict.keys())*0.75/batch_size is an integer for simplicity

    last 25% of data will be used for validation

    __Initial vector transformations (SBERT -> embedding):__
    W_class: weight matrix for class projection (50x384)
    b_class: bias vector for class projection (50 dim)

    W_text: weight matrix for text projection (100x384)
    b_text: bias vector for text projection (100 dim)

    W_sig: weight matrix for signature projection (50x384)

    __Scoring layer:__
    Ws: 2x351
    bs: 2x1 (column vector)

    __Naming GNN params:__
    [W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
    for Matrices: (351x351), for vectors: (351x1) column vectors


    Note: labelling will involve: being showed all the innerText and urlText of all leaves, and selecting which ones are portCo names. They will be identified by their node IDs within the soup tree.

    Initially, define all torch.nn.Parameter weights here, and then use an optimizer to train them based on loss between predicted portCo names and true portCo names.

        This will be done using torch.optim.Adam optimizer, and a suitable loss function (e.g., cross-entropy loss for classification), 
        in a mini-batch training loop. Mini-batch size should similtaneously minimise overfitting while also not drowning out the intricacies of each individual sample.

        _________________________________

        for leaves [l1, l2, ..., ln] with predicted scores [s1, s2, ..., sn] and true labels [t1, t2, ..., tn] (where ti = 1 if leaf li is a true portCo name, else 0), compute loss as:

            for sample i in batch: 
                let o_i = the predicted overall text type, and t_i = the true overall text type (1 for InnerText, 0 for UrlText)  

                let E_i = the number of estimated portCo names (i.e., leaves with score above 0.8)
                and T_i = the number of true portCo names (i.e., leaves with true label 1)

                let the level of the kth leaf be level_k_i (0 for root, 1 for children of root, etc)
            
                let the mean level of the predicted portCo names be L_i = mean(level_k_i for all k where s_k_i > 0.8)
                Let V_l_i = variance(level_k_i for all k where s_k_i > 0.8)
            
            Then, we can add a penalty term to the loss function to encourage the model to predict portCo names that are not only correct in number, but also consistent in their position within the HTML tree structure.

            __________________________________

            so, for sample i in batch:

            loss_i = cross_entropy_loss([s1, s2, ..., sn]_i, [t1, t2, ..., tn]_i) + lambda1 * (o_i - t_i)^2 + lambda2 * (E_i - T_i)^2 + lambda3 * V_l_i

            where lambda1 and lambda2 are hyperparameters to be tuned.

            __________________________________

            Then, the total loss over the batch is:

            total_loss = sum(loss_i for i in batch) / batch_size

            lambda1 should be small enough such that size ends up being important in the fine-tuning process (i.e. later stages of training)

            trained function: A & B -> D -> E (scores)
            i.e., output in trained function is the confidence scores for each leaf node, and the overall type score.

    """

    
    def naming_GNN_forward(soup, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams):
        """
        namingParams = [W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
        """
        #1) Convert HTML to tree
        tree_head, id_to_node = convert_html_to_tree(soup)
        if not tree_head:
            print("Empty HTML tree, returning None.")
            return None, None, None

        #2) Convert nodes to vectors
        def traverse_and_vectorise(node):
            convert_node_to_vector(node, W_class, b_class, W_text, b_text, W_sig, device=dev)
            for child in node['children']:
                traverse_and_vectorise(child)

        traverse_and_vectorise(tree_head)

        #3) GNN processing
        leafList = GNN_process_portCo(tree_head, *namingParams, dev=dev)

        if not leafList:
            print("No leaves found after GNN processing, returning None.")
            return None, None, None

        #4) Compute group scores
        final_scores = scores(leafList, W_s, b_s) #leafID: {'confidence': score, 'type': type_score}, with the scores being torch scalars

        confidence_scores = torch.stack([torch.sigmoid(score['confidence']) for score in final_scores.values()])  #sigmoid to map to [0,1]
        type_scores = torch.stack([score['type'] for score in final_scores.values()])  #raw type scores
        #each score is a torch scalar, so torch.stack creates a 1D tensor of shape (num_leaves,)

        #this way only relevant leafs are considered for overall type computation, while also allowing for differentiability
        overall_type = torch.dot(type_scores, confidence_scores)/ type_scores.sum() if type_scores.sum().item() != 0 else torch.tensor(0.0, device=dev)

        return final_scores, overall_type, id_to_node




    def naming_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams):
        """
        Compute loss for a single sample.
        
        training_batch: {sampleID: {soup, [true_scores], overall_type}} dict, length = batch_size
    
        where true_scores is a SORTED (by key) dict of nodeIDs: {1 if portCo name else 0}
        (1 and 0 are torch scalars for differentiability)
        overall_type: torch scalar (1 for InnerText, 0 for UrlText)
        """

        total_loss = torch.tensor(0.0, device=dev)

        
        for i, sample in training_batch.items():
            soup = sample['soup']
            true_scores = sample['correct_portCo_tagIDs'] #list of tagIDs that are true portCo names
            true_type = sample['overall_type']
            true_type = torch.tensor(1.0, device=dev) if true_type == "innerText" else torch.tensor(0.0, device=dev) #convert to torch scalar for differentiability

            #____create_comparison_dict____
            """
            naming_scores: dict of {leafID: {'confidence': score, 'type': type_score}}
             - score, type_score are torch scalars (before sigmoid)
            overall_type: torch scalar
            id_to_node: dict of {nodeID: node}
            """
            predicted_scores, predicted_overall_type, id_to_node = naming_GNN_forward(soup, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams) 
            if predicted_scores is None:
                print(f"Error in forward pass for sample {i}, terminating training.")
                return None
            
            comparison_dict = defaultdict(lambda: {'predicted': torch.tensor(0.0, device=dev, dtype=dtype), 'true': torch.tensor(0.0, device=dev, dtype=dtype)})  #key: nodeID, value: dict with 'predicted' and 'true' entries
            
            #traversing through predicted_scores ensures alignment
            true_scores = {k: torch.tensor(1.0, device=dev) if k in true_scores else torch.tensor(0.0, device=dev) for k in predicted_scores.keys()}  #convert list of true portCo tagIDs to dict of nodeID: {1 if portCo name else 0}, with torch scalars for differentiability. Only include nodes that are in predicted_scores to ensure alignment.

            id_keys = predicted_scores.keys()

            #this ensures there is no mismatch between predicted and true portCo name nodes, and that they are aligned by nodeID
            for k in id_keys:
                comparison_dict[k]['predicted'] = predicted_scores[k]['confidence']
                if k not in true_scores:
                    print(f"Error: mismatched node IDs between predicted and true portCo name nodes for sample {i}: Terminating training.")
                    return None

                comparison_dict[k]['true'] = true_scores[k] #note: ensure true_scores are torch scalars (0 or 1)
                
            final_data = dict(sorted(comparison_dict.items()))  #sort by key to ensure alignment



            #____compute E, T, V_l____

            E = torch.stack([f(s['predicted'],10000,0.8) for s in final_data.values()]).sum() #maintain differentiability; approximate count of predicted portCo names
            T = torch.stack([s['true'] for s in final_data.values()]).sum()  #true count of portCo names

            #level variance calculation
            #note: the 'level' attribute of each node is a torch scalar (0 for root, 1 for children of root, etc)
            level_sum = torch.stack([id_to_node[k]['level']*f(s['predicted'],10000,0.8) for k, s in final_data.items()]).sum()
            Expected_L = level_sum / (E + 1e-9)  #avoid division by zero
            deviation_sum = torch.stack([((id_to_node[k]['level'] - Expected_L)**2)*f(s['predicted'],1000,0.8) for k, s in final_data.items()]).sum()
            V_l = deviation_sum / (E + 1e-9)  #variance
    

            #____compute loss____

            #note: the scores themselves are still torch tensors, so only need to stack them for loss computation
            cross_entropy_loss = F.binary_cross_entropy_with_logits(torch.stack([s['predicted'] for s in final_data.values()]), torch.stack([s['true'] for s in final_data.values()]))
            #binary means that the true labels are 0 or 1 for each leaf node. 
            #the _with_logits means that the predicted scores are raw scores, and not passed through a sigmoid yet, so can be any real number.

            loss = cross_entropy_loss + lambda1 * (predicted_overall_type - true_type)**2 + lambda2 * (E - T)**2 + lambda3 * V_l

            total_loss += loss

        if len(training_batch) == 0:
            print("Empty training batch, returning zero loss.")
            return torch.tensor(0.0, device=dev, dtype=dtype)
        final_loss = total_loss / len(training_batch)

        return final_loss
        



    #unpack naming params
    #namingParams is [W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
    W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams = naming_params_package


    optimizer = torch.optim.Adam(
        [W_class, b_class, W_text, b_text, W_sig, W_s, b_s] + namingParams,
        lr=learning_rate
    )


    iterations = (len(training_dict.keys()) * 0.75) // batch_size

    for i in range (iterations):

        training_batch = {}

        for j in range(batch_size):
            training_batch[i * batch_size + j] = training_dict[i * batch_size + j]
        
        optimizer.zero_grad()   

        loss = naming_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams)
        if loss is None:
            print("Loss computation failed, terminating training.")
            return None
        loss.backward()
        optimizer.step()

        if i %100 == 0:
            print(f"Iteration {i}, Loss: {loss.item()}")

    #Save the trained model
    base = Path(__file__).resolve().parent.parent.parent # go up 3 levels to pipeline/
    save_dir = base / 'output' / 'naming_GNN_models' / f'naming_GNN_model_{datetime_str}.pt'
    save_dir.mkdir(parents=True, exist_ok=True)


    torch.save({
        'W_class': W_class,
        'b_class': b_class,
        'W_text': W_text,
        'b_text': b_text,
        'W_sig': W_sig,
        'W_s': W_s,
        'b_s': b_s,
        'namingParams': namingParams
    }, save_dir)

    print(f"Trained naming GNN model saved to {save_dir}")









def train_portfolio_page_finder_GNN(training_dict, portfolio_params_package, dev='cpu', batch_size=4, learning_rate=0.001, T1=10, T2=1000, dtype=torch.float32):
    """
    training_dict: dict of {sample_ID: {soup, true_portfolio_page_node}}
    
    batch_size: int, number of samples per training batch

    ensure len(training_dict.keys())*0.75/batch_size is an integer for simplicity

    last 25% of data will be used for validation

    Note: labelling will involve, being showed all the href-leaf nodes (i.e., nodes with href attribute and no descendants with href attributes), and selecting which one is the portfolio page link. They will be identified by their node IDs within the soup tree.

    Initially, define all torch.nn.Parameter weights here, and then use an optimizer to train them based on loss between predicted portfolio page and true portfolio page.

        This will be done using torch.optim.Adam optimizer, and a suitable loss function (e.g., cross-entropy loss for classification), 
        in a mini-batch training loop. Mini-batch size should similtaneously minimise overfitting while also not drowning out the intricacies of each individual sample.

        consider leaves [l1, l2, ..., ln] with predicted scores [s1, s2, ..., sn] 
        
        (note: this is required because cross-entropy loss between original scores doesnt provide much signal for backpropagation, as only one leaf is correct, and all others are equally wrong)

        for sample i in batch:
            let Li_k = the square difference in level between the kth leaf and the true portfolio page leaf (i.e., (level_k - level_true_portfolio_page)^2)
            id_k = nodeID of kth leaf
            let D(id_k) = the square difference in nodeID between the kth leaf and the true portfolio page leaf (i.e., (id_k - id_true_portfolio_page)^2)
            let boost_k = exp(-Li_k/T1 - D(id_k)/T2), where T1, T2 are hyperparams  #this way, leaves closer in level to the true portfolio page get higher boosts
            
        Therefore, define the true labels for sample i as:
            t_k = boost_k / sum(boost_j for j in all leaves)  #normalise to sum to 1        
        
            compute loss as:

            loss = cross_entropy_loss([s1, s2, ..., sn], [t1, t2, ..., tn])

    """
    #soup, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final
    
    datetime_str = time.strftime("%Y-%m-%d-%H-%M-%S")
    torch.set_default_dtype(dtype)

    def page_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final):
        """
        training_batch: sampleID: {soup, true_portfolio_page_node} tuples, length = batch_size 
        """
        total_loss = torch.tensor(0.0, device=dev, dtype=dtype)
        for i, sample in training_batch.items():
            soup = sample['soup']
            true_node = sample['true_portfolio_page_node'] 
            
            """
            id_to_score: dict of {leafID: score}
            id_to_node: dict of {leafID: node}
            IDs are python scalars, and scores are torch scalars (before softmax)
            """
            id_to_score, id_to_node = portfolio_page_finder_GNN(soup, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final)
            
            id_to_score = dict(sorted(id_to_score.items()))  #sort by key to ensure alignment
            id_to_node = dict(sorted(id_to_node.items()))  #sort by key to ensure alignment

            level = true_node['level'].item()
            id = true_node['tagID']
            #ensure true portfolio page node is among href-leaf nodes
            if id not in id_to_node:
                print(f"Error: true portfolio page for sample {i} node not found among href-leaf nodes: Terminating training.")
                return None

            #true_dict: dict of {leafID: true_score}
            true_dict = {}
            for leaf in id_to_node.values():
                L = (leaf['level'].item() - level)**2
                D = (leaf['tagID'] - id)**2
                boost = math.exp(-L/T1 - D/T2)  
                true_dict[leaf['tagID']] = boost
            normalisation = sum(true_dict.values())
            for k in true_dict.keys():
                true_dict[k] /= normalisation  #normalise to sum to 1; necessary for cross-entropy loss
    
            true_dict = dict(sorted(true_dict.items()))  #sort by key to ensure alignment



            #compute scores
            predicted_scores = torch.stack(list(id_to_score.values()))  #convert torch scalars to tensor
            true_scores = torch.stack([torch.tensor(v, device=dev, dtype=dtype) for v in true_dict.values()]) #convert python scalars to tensor (tensor conversion is ok here, as true scores are not involved in backpropagation until loss computation)


            loss = F.cross_entropy(predicted_scores.unsqueeze(0), true_scores.unsqueeze(0)) # changes shape from (n,) to (1,n) for cross_entropy input. Adding this batch dimension is necessary for cross_entropy to work.
            #regular cross entropy loss is used here, as true scores do not just consist of 1s and 0s, but a spread of values.
            #softmax is applied internally in cross_entropy function to predicted scores, so no need to apply it here.

            total_loss += loss

        if len(training_batch) == 0:
            print("Empty training batch, returning zero loss.")
            return torch.tensor(0.0, device=dev, dtype=dtype)
        final_loss = total_loss / len(training_batch)

        return final_loss
    


    #Define all parameters here
    W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final = portfolio_params_package 

    optimizer = torch.optim.Adam(
        [W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final],
        lr=learning_rate
    )

    iterations = (len(training_dict.keys()) * 0.75) // batch_size

    for i in range (iterations):

        training_batch = {}

        for j in range(batch_size):
            training_batch[i * batch_size + j] = training_dict[i * batch_size + j]
        
        optimizer.zero_grad()

        loss = page_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final)
        if loss is None:
            print("Loss computation failed, terminating training.")
            return None
        loss.backward()
        optimizer.step()

        if i %100 == 0:
            print(f"Iteration {i}, Loss: {loss.item()}")

    #Save the trained model
    base = Path(__file__).resolve().parent.parent.parent # go up 3 levels to pipeline/
    save_dir = base / 'output' / 'subpage_GNN_models' / f'subpage_GNN_model_{datetime_str}.pt'
    save_dir.mkdir(parents=True, exist_ok=True)

    torch.save({
        'W_class': W_class,
        'b_class': b_class,
        'W_text': W_text,
        'b_text': b_text,
        'W_sig': W_sig,
        'W_down': W_down,
        'b_down': b_down,
        'W_info': W_info,
        'b_info': b_info,
        'W_key': W_key,
        'b_key': b_key,
        'W_final': W_final,
        'b_final': b_final
    }, save_dir)

    print(f"Trained portfolio page finder GNN model saved to {save_dir}")

            
            