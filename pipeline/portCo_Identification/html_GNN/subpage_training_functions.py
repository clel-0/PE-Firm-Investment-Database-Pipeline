from .functions__training import *


import time
import torch
import torch.nn.functional as F




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
        training_batch: sampleID: {soup, true_portfolio_page_tagID} tuples, length = batch_size 
        """
        ### NOTE: Levels are already computed and annotated during B_convert_node_to_vector step, so can be accessed directly as node['level'] for each node in id_to_node.
        def _annotate_levels(node, level=0):
            node['level'] = torch.tensor(float(level), device=dev, dtype=dtype)
            for child in node.get('children', []):
                _annotate_levels(child, level + 1)

        total_loss = torch.tensor(0.0, device=dev, dtype=dtype)
        used_samples = 0
        for i, sample in training_batch.items():
            soup = sample['soup']
            true_tag_id = sample.get('true_portfolio_page_tagID')
            if true_tag_id is None:
                true_node = sample.get('true_portfolio_page_node')
                if isinstance(true_node, dict):
                    true_tag_id = true_node.get('tagID')

            try:
                true_tag_id = int(true_tag_id)
            except (TypeError, ValueError):
                print(f"Error: invalid true portfolio page tagID for sample {i}: {true_tag_id}")
                continue
            
            """
            id_to_score: dict of {leafID: score}
            id_to_node: dict of {leafID: node}
            IDs are python scalars, and scores are torch scalars (before softmax)
            """
            model_out = portfolio_page_finder_GNN(soup, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final, dev=dev)
            if isinstance(model_out, tuple) and len(model_out) == 2:
                id_to_score, id_to_node = model_out
            else:
                id_to_score = model_out
                tree_head, id_to_node = convert_html_to_tree(soup)
                if not tree_head:
                    print(f"Error: empty tree produced for sample {i} in fallback node reconstruction.")
                    continue
                _annotate_levels(tree_head)
                id_to_node = {k: v for k, v in id_to_node.items() if k in id_to_score}
            
            if not id_to_score or not id_to_node:
                print(f"Warning: empty candidate maps for sample {i}; skipping sample.")
                continue

            shared_keys = sorted(set(id_to_score.keys()) & set(id_to_node.keys()))
            if not shared_keys:
                print(f"Warning: no shared keys between score map and node map for sample {i}; skipping sample.")
                continue

            id_to_score = {k: id_to_score[k] for k in shared_keys}
            id_to_node = {k: id_to_node[k] for k in shared_keys}

            #note: level can just stay as a python scalar from the beginning, as it ends up being converted back into a python scalar as seen below.
            #note that the calculations of L below would also need to be altered (no .item() needed).
            if true_tag_id not in id_to_node:
                print(f"Warning: true portfolio page for sample {i} node not found among href-leaf nodes; skipping sample.")
                continue

            true_node = id_to_node[true_tag_id]
            level = true_node['level'].item() if hasattr(true_node['level'], 'item') else float(true_node['level'])
            id = true_node['tagID']
            #ensure true portfolio page node is among href-leaf nodes
            if id not in id_to_node:
                print(f"Warning: true portfolio page for sample {i} node not found among href-leaf nodes; skipping sample.")
                continue

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

            ordered_keys = sorted(set(id_to_score.keys()) & set(true_dict.keys()))
            if not ordered_keys:
                print(f"Warning: no aligned keys for predicted and target scores in sample {i}; skipping sample.")
                continue



            #compute scores
            predicted_scores = torch.stack([id_to_score[k] for k in ordered_keys])  #convert torch scalars to tensor
            true_scores = torch.stack([torch.tensor(true_dict[k], device=dev, dtype=dtype) for k in ordered_keys]) #convert python scalars to tensor (tensor conversion is ok here, as true scores are not involved in backpropagation until loss computation)


            loss = F.cross_entropy(predicted_scores.unsqueeze(0), true_scores.unsqueeze(0)) # changes shape from (n,) to (1,n) for cross_entropy input. Adding this batch dimension is necessary for cross_entropy to work.
            #regular cross entropy loss is used here, as true scores do not just consist of 1s and 0s, but a spread of values.
            #softmax is applied internally in cross_entropy function to predicted scores, so no need to apply it here.

            total_loss += loss
            used_samples += 1

        if len(training_batch) == 0:
            print("Empty training batch, returning zero loss.")
            return torch.tensor(0.0, device=dev, dtype=dtype)
        if used_samples == 0:
            print("No valid samples in portfolio-page training batch after alignment checks.")
            return None
        final_loss = total_loss / used_samples

        return final_loss
    
    ################################################################################################################################################################################################

    #Define all parameters here
    W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final = portfolio_params_package 

    optimizer = torch.optim.Adam(
        [W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final],
        lr=learning_rate
    )

    sample_items = sorted(list(training_dict.items()), key=lambda kv: str(kv[0]))
    train_size = int(len(sample_items) * 0.75)
    train_items = sample_items[:train_size]
    iterations = math.ceil(len(train_items) / batch_size) if batch_size > 0 else 0

    if iterations == 0:
        print("No portfolio-page training iterations available (dataset too small for current batch size).")
        return None

    successful_steps = 0

    print("="*20)
    print("PORTFOLIO PAGE FINDER GNN TRAINING STARTED")
    print("="*20)
    print(f"[ENV] dev={dev}, torch.cuda.is_available()={torch.cuda.is_available()}, default_dtype={torch.get_default_dtype()}")
    print(f"Total training samples: {len(train_items)}, Batch size: {batch_size}, Total iterations: {iterations}")

    for i in range (iterations):

        start = i * batch_size
        end = min(start + batch_size, len(train_items))
        batch_items = train_items[start:end]
        training_batch = {sample_id: sample for sample_id, sample in batch_items}
        
        print(f"[SUBPAGE][BATCH {i}] Start. samples_in_batch={len(training_batch)}")

        _, zero_grad_time = timed_call(f"subpage batch {i} zero_grad", lambda: optimizer.zero_grad(), dev)

        loss, loss_build_time = timed_call(
            f"subpage batch {i} loss_build",
            lambda: page_batch_loss(training_batch, W_class, b_class, W_text, b_text, W_sig, W_down, b_down, W_info, b_info, W_key, b_key, W_final, b_final),
            dev
        )
        if loss is None:
            print(f"Skipping portfolio-page batch {i}: no valid samples after tagID validation.")
            continue

        print(f"loss for portfolio-page batch {i}: {loss.item()}")

        _, backward_time = timed_call(f"subpage batch {i} backward", lambda: loss.backward(), dev)
        _, step_time = timed_call(f"subpage batch {i} optimizer_step", lambda: optimizer.step(), dev)

        successful_steps += 1

        print(
            f"[SUBPAGE][BATCH {i}] complete. "
            f"zero_grad={zero_grad_time:.3f}s, loss_build={loss_build_time:.3f}s, "
            f"backward={backward_time:.3f}s, step={step_time:.3f}s"
        )
        

    if successful_steps == 0:
        print("No portfolio-page optimizer steps were executed; aborting model save.")
        return None

    #Save the trained model
    subpage_dir, _ = get_model_dirs()
    save_dir = subpage_dir / f'subpage_GNN_model_{datetime_str}.pt'
    save_dir.parent.mkdir(parents=True, exist_ok=True)

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
    return True
