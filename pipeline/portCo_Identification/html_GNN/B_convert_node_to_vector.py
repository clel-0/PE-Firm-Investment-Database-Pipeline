import torch
import torch.nn.functional as F
import time
try:
    from sentence_transformers import SentenceTransformer
    _sentence_transformers_import_error = None
except Exception as exc:
    SentenceTransformer = None
    _sentence_transformers_import_error = exc


_model = None
_call_counter = 0
_embedding_cache = {}


def _get_model():
    global _model
    if _model is None:
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers is not available. Install dependencies before running vector conversion."
            ) from _sentence_transformers_import_error
        print("[VECTORISE] Loading SentenceTransformer model: all-MiniLM-L6-v2")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        print("[VECTORISE] SentenceTransformer model loaded.")
    return _model


def _encode_texts_with_cache(texts, model, device='cpu'):
    if not texts:
        return torch.empty((0, 384), device=device, dtype=torch.float32)

    unique_texts = list(dict.fromkeys(texts))
    missing_texts = [text for text in unique_texts if text not in _embedding_cache]

    if missing_texts:
        encoded_missing = model.encode(
            missing_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=64
        )
        for text, emb in zip(missing_texts, encoded_missing):
            _embedding_cache[text] = torch.tensor(emb, device='cpu', dtype=torch.float32)

    batch_cpu = torch.stack([_embedding_cache[text] for text in texts], dim=0)
    return batch_cpu.to(device=device, dtype=torch.float32)


def _convert_nodes_to_vectors_batch(nodes, W_class, b_class, W_text, b_text, W_sig, device='cpu'):
    if not nodes:
        return

    model = _get_model()

    tag_name_texts = [str(node['tagName']) if node['tagName'] else "" for node in nodes]
    url_texts = [str(node['UrlText']) if node['UrlText'] else "" for node in nodes]
    inner_texts = [str(node['InnerText']) if node['InnerText'] else "" for node in nodes]
    class_texts = [str(node['class']) if node['class'] else "" for node in nodes]
    signature_texts = [" > ".join(str(part) for part in node.get('sig', ())) for node in nodes]

    encode_t0 = time.perf_counter()
    tag_emb = _encode_texts_with_cache(tag_name_texts, model, device=device)
    url_emb = _encode_texts_with_cache(url_texts, model, device=device)
    inner_emb = _encode_texts_with_cache(inner_texts, model, device=device)
    class_emb_raw = _encode_texts_with_cache(class_texts, model, device=device)
    sig_emb = _encode_texts_with_cache(signature_texts, model, device=device)
    encode_elapsed = time.perf_counter() - encode_t0

    project_t0 = time.perf_counter()
    b_text_row = b_text.reshape(1, -1)
    b_class_row = b_class.reshape(1, -1)

    tag_proj = tag_emb @ W_text.transpose(0, 1) + b_text_row
    url_proj = url_emb @ W_text.transpose(0, 1) + b_text_row
    inner_proj = inner_emb @ W_text.transpose(0, 1) + b_text_row
    class_proj = class_emb_raw @ W_class.transpose(0, 1) + b_class_row
    sig_proj = sig_emb @ W_sig.transpose(0, 1)

    url_type_vals = []
    for node in nodes:
        if node['UrlType'] == -1:
            url_type_vals.append(-1.0)
        elif node['UrlType'] == 0:
            url_type_vals.append(0.0)
        else:
            url_type_vals.append(1.0)
    url_type_emb = torch.tensor(url_type_vals, device=device, dtype=torch.float32).reshape(-1, 1)

    #in torch.cat, dim=1 means 'add more columns'. Therefore, stacked side by side to create the final 351-dim row vector for each node. 
    vectors = torch.cat([tag_proj, class_proj, url_proj, inner_proj, url_type_emb], dim=1)
    project_elapsed = time.perf_counter() - project_t0

    #rows are iterated through as each row represents final node vec. Since _proj tensors were made from the 'nodes' list, order preserved.
    for idx, node in enumerate(nodes):
        node['vector'] = vectors[idx].reshape(-1, 1)
        node['sig_vector'] = sig_proj[idx].reshape(-1, 1)

    print(
        f"[VECTORISE][BATCH] nodes={len(nodes)}, cache_size={len(_embedding_cache)}, "
        f"encode_time={encode_elapsed:.3f}s, project_time={project_elapsed:.3f}s, "
        f"total={encode_elapsed + project_elapsed:.3f}s"
    )


def convert_tree_to_vectors(tree_head, W_class, b_class, W_text, b_text, W_sig, device='cpu'):
    if not tree_head:
        return

    nodes = []
    stack = [tree_head]
    while stack:
        node = stack.pop()
        nodes.append(node)
        children = node.get('children', [])
        if children:
            stack.extend(reversed(children))

    _convert_nodes_to_vectors_batch(nodes, W_class, b_class, W_text, b_text, W_sig, device=device)

#2)
def convert_node_to_vector(node, W_class, b_class, W_text, b_text, W_sig, device='cpu') -> torch.Tensor:
    """
    For a given node from convert_html_to_tree, compute the 351 dim vector embedding as per the description below

    [tagName (100 dim), class (50 dim), UrlText (100 dim), UrlType (1 dim), InnerText (100 dim)] -> concatenated to 351 dim vector

    W_class: weight matrix for class projection (50x384)
    b_class: bias vector for class projection (50 dim)

    W_text: weight matrix for text projection (100x384)
    b_text: bias vector for text projection (100 dim)

    W_sig: weight matrix for signature projection (50x384)

    """
    global _call_counter
    _call_counter += 1
    call_t0 = time.perf_counter()

    _convert_nodes_to_vectors_batch([node], W_class, b_class, W_text, b_text, W_sig, device=device)

    total_elapsed = time.perf_counter() - call_t0
    print(f"[VECTORISE] call={_call_counter}, tagID={node.get('tagID')}, device={device}, total_time={total_elapsed:.3f}s")
    return node['vector']
