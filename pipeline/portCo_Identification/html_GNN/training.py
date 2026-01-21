
"""
1) Train in a supervised manner to adjust the weights of the GNN to better predict portCo names.
    (Yet to explore semi-supervised methods, due to the complexity of simulating a html tree structure, for PE firm websites.)

        


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

def train_naming_GNN(training_dict, batch_size=4, learning_rate=0.001, lambda1=1, lambda2=0.1, lambda3=0.1):
    #set datetime
    datetime_str = time.strftime("%Y%m%d-%H%M%S")

    """
    training_dict: dict of {sample_ID: soup, true_portCo_name_nodes, true_type) }
    true_portCo_name_nodes: SORTED (by key) dict of nodeIDs: (node, {1 if portCo name else 0})
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
        tree_head = convert_html_to_tree(soup)

        #2) Convert nodes to vectors
        def traverse_and_vectorise(node):
            convert_node_to_vector(node, W_class, b_class, W_text, b_text, W_sig)
            for child in node['children']:
                traverse_and_vectorise(child)

        traverse_and_vectorise(tree_head)

        #3) GNN processing
        leafList = GNN_process_portCo(tree_head, *namingParams)

        #4) Compute group scores
        final_scores = scores(leafList, W_s, b_s) #these are the final scores and will be considered the output for training.

        confidence_scores = [torch.sigmoid(score) for score in final_scores.values()['confidence']]  #sigmoid to map to [0,1]
        type_scores = [score for score in final_scores.values()['type']]  #raw type scores
        #this way only relevant leafs are considered for overall type computation, while also allowing for differentiability
        overall_type = sum(torch.dot(type_scores, confidence_scores))/ sum(type_scores) if type_scores.sum().item() != 0 else 0.0

        return leafList, final_scores, overall_type




    def compute_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams):
        """
        Compute loss for a single sample.

        training_batch: sampleID: (soup, [true_portCo_name_nodeIDs], overall_type) tuples, length = batch_size
        """

        total_loss = 0.0
        for i, (soup, true_portCo_name_nodes, true_type) in training_batch.items():


            leafList, scores, overall_type = naming_GNN_forward(soup, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams)

            comparison_dict = defaultdict(lambda: {['predicted']: int, ['true']: int})  #key: nodeID, value: dict with 'predicted' and 'true' entries

            #this ensures there is no mismatch between predicted and true portCo name nodes, and that they are aligned by nodeID
            for k in scores.keys():
                comparison_dict[k]['predicted'] = scores[k]['confidence']
                if not training_batch[k]:
                    print(f"Error: mismatched node IDs between predicted and true portCo name nodes for sample {i}: Terminating training.")
                    return None

                comparison_dict[k]['true'] = training_batch[k][1]
            
            final_data = dict(sorted(comparison_dict.items()))  #sort by key to ensure alignment



            E = sum(f(s['confidence'],10000,0.8) for s in scores.values()) #maintain differentiability; approximate count of predicted portCo names
            T = sum(leaf[1] for leaf in true_portCo_name_nodes.values())  #true count of portCo names

            #level variance calculation
            level_sum = sum(leaf["level"]*f(s['confidence'],10000,0.8) for s,leaf in zip(scores.values(), leafList))
            Expected_L = level_sum / (E + 1e-9)  #avoid division by zero
            deviation_sum = sum(((leaf["level"] - Expected_L)**2)*f(s['confidence'],1000,0.8) for s,leaf in zip(scores.values(), leafList))
            V_l = deviation_sum / (E + 1e-9)  #variance



            #note: the scores themselves are still torch tensors, so only need to stack them for loss computation
            cross_entropy_loss = F.binary_cross_entropy_with_logits(torch.stack(s['predicted'] for s in final_data.values()), torch.stack(s['true'] for s in final_data.values()))

            loss = cross_entropy_loss + lambda1 * (overall_type - true_type)**2 + lambda2 * (E - T)**2 + lambda3 * V_l

            total_loss += loss

        if len(training_batch) == 0:
            print("Empty training batch, returning zero loss.")
            return torch.tensor(0.0, device=W_s.device)
        final_loss = total_loss / len(training_batch)

        return final_loss
        



    #Define all parameters here

    W_class = torch.nn.Parameter(torch.randn(50,384)*0.01)
    b_class = torch.nn.Parameter(torch.randn(50)*0.01)

    W_text = torch.nn.Parameter(torch.randn(100,384)*0.01)
    b_text = torch.nn.Parameter(torch.randn(100)*0.01)

    W_sig = torch.nn.Parameter(torch.randn(50,384)*0.01)
    

    W_s = torch.nn.Parameter(torch.randn(2,351)*0.01)
    b_s = torch.nn.Parameter(torch.randn(2,1)*0.01)

    #[W_i, b_i, W_qs, b_qs, W_qi, b_qi, W_k, b_k, W_c1, W_c2, W_i1, W_i2, w_c, w_i, W_ci, b_ci]
    namingParams = [
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_i
        torch.nn.Parameter(torch.randn(351)*0.01),      #b_i
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_qs
        torch.nn.Parameter(torch.randn(351)*0.01),      #b_qs
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_qi
        torch.nn.Parameter(torch.randn(351)*0.01),      #b_qi   
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_k
        torch.nn.Parameter(torch.randn(351)*0.01),      #b_k
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_c1
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_c2
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_i1
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_i2
        torch.nn.Parameter(torch.randn(351)*0.01),      #w_c
        torch.nn.Parameter(torch.randn(351)*0.01),      #w_i
        torch.nn.Parameter(torch.randn(351,351)*0.01),  #W_ci
        torch.nn.Parameter(torch.randn(351)*0.01)       #b_ci
    ]
    


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

        loss = compute_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_s, b_s, namingParams)
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




def train_portfolio_page_finder_GNN(training_dict, batch_size=4, learning_rate=0.001, T1=10, T2=1000):
    """
    training_dict: dict of {sample_ID: (soup, true_portfolio_page_node)}
    
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
    

    def batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final):
        total_loss = 0.0
        for i, (soup, node) in training_batch.items():

            hrefleaf_to_score = dict(sorted(portfolio_page_finder_GNN(soup, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final).items()))  #sort by key to ensure alignment


            level = node['level']
            id = node['tagID']
            #ensure true portfolio page node is among href-leaf nodes
            if id not in [leaf['tagID'] for leaf in hrefleaf_to_score.keys()]:
                print(f"Error: true portfolio page for sample {i} node not found among href-leaf nodes: Terminating training.")
                return None

            #compute true distribution
            true_dict = {}
            for leaf in hrefleaf_to_score.keys():
                L = (leaf['level'] - level)**2
                D = (leaf['tagID'] - id)**2
                boost = math.exp(-L/T1 - D/T2)  
                true_dict[leaf['tagID']] = boost
            normalisation = sum(hrefleaf_to_score.values())
            for k in true_dict.keys():
                true_dict[k] /= normalisation  #normalise to sum to 1
    
            true_dict = dict(sorted(true_dict.items()))  #sort by key to ensure alignment

            #compute scores
            predicted_scores = torch.stack([hrefleaf_to_score[leaf['tagID']] for leaf in hrefleaf_to_score.keys()])
            true_scores = torch.stack([torch.tensor(true_dict[leaf['tagID']]) for leaf in hrefleaf_to_score.keys()]) #convert to tensor


            loss = F.cross_entropy(predicted_scores.unsqueeze(0), true_scores.unsqueeze(0))

            total_loss += loss

        if len(training_batch) == 0:
            print("Empty training batch, returning zero loss.")
            return torch.tensor(0.0, device=W_final.device)
        final_loss = total_loss / len(training_batch)



        return final_loss
    


            
            