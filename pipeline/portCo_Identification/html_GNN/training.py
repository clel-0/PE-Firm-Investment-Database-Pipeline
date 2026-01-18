

def train_GNN(soup_groupID_dict, true_portCo_names_dict):
    """
    soup_group_ID_dict: dict of {sample_ID: (soup, groupIDs)}
    true_portCo_names_dict: dict of {sample_ID: [true_portCo_names]}

    1) Train in a supervised manner to adjust the weights of the GNN to better predict portCo names.
    (Yet to explore semi-supervised methods, due to the complexity of simulating a html tree structure, for PE firm websites.)

        Initially, define all torch.nn.Parameter weights here, and then use an optimizer to train them based on loss between predicted portCo names and true portCo names.

        This will be done using torch.optim.Adam optimizer, and a suitable loss function (e.g., cross-entropy loss for classification), in a mini-batch training loop. Mini-batch size should similtaneously minimise overfitting while also not drowning out the intricacies of each individual sample.

        for leaves [l1, l2, ..., ln] with predicted scores [s1, s2, ..., sn] and true labels [t1, t2, ..., tn] (where ti = 1 if leaf li is a true portCo name, else 0), compute loss as:

            loss = cross_entropy_loss([s1, s2, ..., sn], [t1, t2, ..., tn])


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