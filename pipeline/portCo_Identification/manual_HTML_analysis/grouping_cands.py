from collections import defaultdict
import math
import pandas as pd


#might have to remove grouping from GNN because groups arent guarateed to be correct



#task: rewrite this function to prioritise near-identical path signatures that differ only in type (href v/s text), and by at most one segment.
def group_homogeneous_lists_df(df: pd.DataFrame,
                               path_col: str = "path_sig",
                               name_col: str = "name",
                               type_col: str = "type",
                               id_col: str = "card_id",
                               soup_col: str = "soup_object",
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
    soup_col : str
        Column containing the soup/card object so we can detect embedded hrefs in each card.
    min_group_size : int
        Only keep groups with at least this many distinct names.

    Returns
    -------
    dict[tuple[str, ...], dict]
        Key: masked path signature (one segment replaced by 'x').
        Value: metadata dict with keys: names, card_ids, type, cross_type_matching, all_cards_have_href.

    dict: path sig -> groupID
   
    (for assigning group IDs back to cards in GNN processing)
    """
    groups = defaultdict(
        lambda: {
            "sig": set(),
            "names": set(),
            "card_ids": set(),
            "type": None,
            "cross_type_matching": False,
            "all_cards_have_href": False,
        }
    )

    groupIDs = {}  # path sig -> groupID


    # Precompute which card_ids already have href candidates or href tags in the card soup
    href_card_ids = set(df.loc[df[type_col] == "href", id_col])
    if soup_col in df.columns:
        # Use the first soup_object we see per card_id to avoid repeated scans
        first_soup_for_card = {}
        for cardid, soup in df[[id_col, soup_col]].itertuples(index=False):
            if cardid in first_soup_for_card:
                continue
            first_soup_for_card[cardid] = soup

        for cardid, soup in first_soup_for_card.items():
            try:
                if soup and getattr(soup, "find", None) and soup.find("a", href=True):
                    href_card_ids.add(cardid)
            except Exception:
                # If soup parsing fails, just skip the DOM-based href detection for that card
                continue

    # Pull the relevant columns as raw values
    # (faster and avoids issues with attribute-style access)

    for sig, name, typ, cardid in df[[path_col, name_col, type_col, id_col]].itertuples(index=False):
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
            cross_type_matching = False 
            masked = list(sig)
            masked[k] = "x"          # wildcard for the variable segment
            
            masked_key = tuple(masked)
            key = (typ, *masked_key)
            groups[key]["names"].add(name)
            groups[key]["card_ids"].add(cardid)
            groups[key]["type"] = typ
            groups[key]["sig"].add(sig) #store the original sigs too for reference

    # Optionally filter groups to only those with enough members
    if min_group_size is not None and min_group_size > 1:
        groups = {
            k: v for k, v in groups.items()
            if len(v["names"]) >= min_group_size
        }

        # Flag groups whose cards already contain href candidates
        for g in groups.values():
            if g["type"] != "href" and g["card_ids"]:
                g["all_cards_have_href"] = g["card_ids"].issubset(href_card_ids)

        # Check if there are cross-type matching groups (same names+cards, different types)
        group_items = list(groups.items())
        for idx, (k1, group1) in enumerate(group_items):
            for k2, group2 in group_items[idx + 1:]:
                if k1 == k2 or group1["type"] == group2["type"]:
                    continue
                if group1["names"] == group2["names"] and group1["card_ids"] == group2["card_ids"]:
                    group1["cross_type_matching"] = True
                    group2["cross_type_matching"] = True
                    print(
                        f"Cross-type matching groups found with names and card_ids: "
                        f"{group1['names']} and {group2['names']}"
                    )
    
    
        for i,group in enumerate(groups.values()):
            if group:
                print(f"Homogeneous group found with names and card_ids: {group}")
                #assign list of groupIDs to each original sig in the group
                for sig in group["sig"]:
                    if sig not in groupIDs:
                        groupIDs[sig] = set() #making a set to avoid duplicates
                    groupIDs[sig].add(i)

    return groups, groupIDs


#NEW FUNCION: AIM: check if there is a parallel group of same length and same respective card_ids, but different type (href v/s text)
def check_card_ids(group1, group2):
    
    return group1["card_ids"] == group2["card_ids"]
