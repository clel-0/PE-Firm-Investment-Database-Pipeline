from collections import defaultdict
import math
import pandas as pd

def group_homogeneous_lists_df(df: pd.DataFrame,
                               path_col: str = "path_sig",
                               name_col: str = "name",
                               min_group_size: int = 2):
    """
    Group names whose path signatures are 'almost identical':
    - Same length
    - Differ in at most one segment

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns `path_col` and `name_col`.
    path_col : str
        Column containing path signatures (iterables of segments, ideally tuples).
    name_col : str
        Column containing the names (strings).
    min_group_size : int
        Only keep groups with at least this many distinct names.

    Returns
    -------
    dict[tuple[str, ...], set[str]]
        Key: masked path signature (one segment replaced by 'x').
        Value: set of names that share this pattern.
    """
    groups = defaultdict(set)

    # Pull the relevant columns as raw values
    # (faster and avoids issues with attribute-style access)
    for sig, name in df[[path_col, name_col]].itertuples(index=False):
        # Basic sanity checks
        if sig is None or (isinstance(sig, float) and math.isnan(sig)):
            continue
        if name is None or (isinstance(name, float) and math.isnan(name)):
            continue

        # Ensure the signature is a tuple (hashable, stable)
        sig = tuple(sig)
        L = len(sig)
        if L == 0:
            continue

        # For each position, create a masked key
        for k in range(L):
            masked = list(sig)
            masked[k] = "x"          # wildcard for the variable segment
            parent = list(sig)[-2] if L >= 2 else "ROOT"  # parent segment
            masked_key = tuple(masked)
            groups[(parent,*masked_key)].add(name)

    # Optionally filter groups to only those with enough members
    if min_group_size is not None and min_group_size > 1:
        groups = {
            k: v for k, v in groups.items()
            if len(v) >= min_group_size
        }

    return groups
