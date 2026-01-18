import numpy as np
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer


model = SentenceTransformer('all-MiniLM-L6-v2')

#2)
def convert_node_to_vector(node, W_class, b_class, W_text, b_text) -> torch.Tensor:
    """
    For a given node from convert_html_to_tree, compute the 351 dim vector embedding as per the description below

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
