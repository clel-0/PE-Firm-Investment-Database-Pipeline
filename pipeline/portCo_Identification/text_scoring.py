
JUNK_STRINGS = {
    "portfolio", "for investors", "contact", "contact us", "",
    "text hover", "for", "about us", "logo", "read more", "team",
    "investments", "news", "placeholder", "strategies", "sustainability",
    "terms of use", "privacy policy", "growth", "private equity",
    "our people", "our board", "our senior team", "our team",
    "advisory", "news press", "view profile", " ", "plugins", "basic", "assets", "app", "themes", "images"
    }
import re
import pandas as pd

from grouping_cands import group_homogeneous_lists_df
from step3_helperFunctions import _norm

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
# Google Custom Search API credentials
API_KEY = os.getenv("API_KEY")
CX = os.getenv("CX")

def params(q):
    return {
        "key": API_KEY,
        "cx": CX,
        "q": q,
        "siteSearchFilter": "i",
        "num": 10
    }



def normalise_text(s: str, PE_name) -> str:
    """Basic normalisation used across the pipeline."""
    if not isinstance(s, str):
        return ""
    s = s.replace("%20", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub("case study", "", s, flags=re.IGNORECASE)
    s = re.sub("logo", "", s, flags=re.IGNORECASE)
    s = re.sub(PE_name, "", s, flags=re.IGNORECASE)
    # remove parts of PE name individually
    PE_name_parts = PE_name.split()
    for part in PE_name_parts:
        s = re.sub(part, "", s, flags=re.IGNORECASE)

    #removing PE name acronyms
    if len(PE_name_parts)>2:
        acro = "".join([word[0] for word in PE_name_parts if word])
        s = re.sub(acro, "", s, flags=re.IGNORECASE)
    
    def count_digits_loop(input_string):
        count = 0
        for char in input_string:
            if char.isdigit():
                count += 1
        return count
    s_list = s.split()
    s = " ".join([word for word in s_list if count_digits_loop(word) <=5])  #remove words with more than 5 digits

     # Final trim

    return s.strip()


def is_email_like(s: str) -> bool:
    """Remove simple email-like single-token strings."""
    if not s:
        return False
    if "@" not in s:
        return False
    return len(s.split()) == 1

#creates a list of strings representing the DOM path signature of an element
#namely: [tag1.class11.class12, tag2.class21.class22, ..., tagn.classn1.classn2]
def element_path_signature(el, max_depth: int = 8):
    """
    Build a DOM 'path signature' from an element upwards.

    Each level is represented as "tag.class1.class2...".
    We walk up parents until <html> / document or max_depth.
    Returned as a tuple from outermost to innermost (root-ish first).
    """
    if el is None:
        return ()

    parts = []
    cur = el
    depth = 0

    try:
        while cur is not None and getattr(cur, "name", None) not in ("[document]", "html"):
            tag = cur.name or ""
            classes = cur.get("class") or []
            class_str = ".".join(sorted(c for c in classes if isinstance(c, str)))
            if class_str:
                parts.append(f"{tag}.{class_str}")
            else:
                parts.append(tag)
            cur = cur.parent
            depth += 1
            #removing max depth limit for now, because the grouping is too lenient otherwise
    except Exception:
        # If anything goes wrong with weird nodes, just return what we have
        pass

    # Reverse so that the higher-level ancestor appears first
    return tuple(reversed(parts))


#removes the innermost level from a path signature to derive a 'list key'
def derive_list_key(path_sig):
    """
    Derive a 'list key' that groups elements likely belonging to the same homogeneous list.

    Strategy:
      - use the ancestor path excluding the innermost node (path_sig[:-1])
    """
    if not path_sig:
        return None

    ancestor_sig = path_sig[:-1]  # drop the innermost level (item-specific)
    if not ancestor_sig:
        ancestor_sig = path_sig  # fallback: use full signature if too shallow


    return ancestor_sig

#Returns True if the normalised PE firm name appears in the snippets at least min_hits times
def pe_name_in_snippets(portco_name: str, pe_name_norm: str, snippets: list[str], min_hits: int = 2) -> bool:
    """
    Simple check: does the normalised PE firm name and the portCo name appear in the same snippet? 
    """
    hit_count = 0
    for snippet in snippets:
        snippet_norm = _norm(snippet).lower()
        pe_norm = pe_name_norm.lower()
        if pe_norm in snippet_norm and portco_name.lower() in snippet_norm:
            hit_count += 1
            if hit_count >= min_hits:
                return True
        
    return False
    


def google_confirm_name(name: str, pe_name_norm: str, google_search_fn, used_up: bool) -> bool:
    """
    Wrapper around your existing google_search function.

    Expects: google_search_fn(query) -> list[dict] with at least a 'snippet' field.
    """
    query = f"private equity firm {pe_name_norm} invested in company {name}"
    try:
        used_up, results = google_search_fn(params(query), pe_name_norm, used_up, return_items=True)
    except Exception as e:
        print("Error during Google search for name confirmation:", e)
        return True, False
    if used_up:
        print("Skipping Google confirmation because API quota appears used up.")
        return True, False
    if not results:
        print("No results returned from Google search.")
        return used_up, False
    snippets = [r.get("snippet", "") for r in results if r.get("snippet")]
    if not snippets:
        print("No snippets returned from Google search.")
        return used_up, False

    return used_up, pe_name_in_snippets(name, pe_name_norm, snippets, min_hits=1)


def select_portcos_for_firm(df: pd.DataFrame, pe_full_name: str, google_search_fn, used_up) -> pd.DataFrame:
    """
    Select likely portfolio companies for a single PE firm from a candidate DataFrame.

    Input DF columns:
        - card_id
        - text
        - raw_text
        - type         (e.g. 'href', 'src', 'a_inner_text', 'img_alt_text', 'image_src', etc.)
        - rank         (A, B, C, D, E, F, I, etc.)
        - soup_object  (BeautifulSoup node from which the candidate came)

    Rank 'I' is treated like any other rank. The only special case:
      - href + rank 'A' → quick exit if we have any.

    Returns a DataFrame with columns:
        - clean_text
        - type
        - card_id
        - list_key    (for structural grouping)
        - rank
        - google_confirmed
    """

    if not API_KEY or not CX:
        raise ValueError("Google API Key and CX must be set in environment variables.")
    else:
        print(f"Google API Key {API_KEY} and CX {CX} loaded successfully.")

    if df.empty:
        return used_up, df

    df = df.copy()

    # --- 1. Cleaning & basic filtering ---

    df["clean_text"] = df["text"].fillna("").apply(
        lambda t: normalise_text(t, pe_full_name)
    )
    #due to double ups from inner text and href/src from same card, deduplicate here   
    df["dupKey"] = df["clean_text"].str.lower().str.replace(r"\s+", "", regex=True)
    df = df.drop_duplicates(subset=["dupKey"])
    df = df.drop(columns=["dupKey"])

    df["clean_lower"] = df["clean_text"].str.lower()

    # Drop obvious junk exact matches
    df = df[~df["clean_lower"].isin(JUNK_STRINGS)]

    # Drop email-like rows
    df = df[~df["clean_text"].apply(is_email_like)]

    #remove whitespace

    # Drop rows with too few alphabetic chars
    alpha_len = df["clean_text"].str.replace(r"[^A-Za-z]", "", regex=True).str.len()
    df = df[alpha_len >= 2]

    if df.empty:
        return used_up, df

    # --- 2. Quick win: href + rank 'A' ---

    href_A = df[(df["type"] == "href") & (df["rank"] == "A")]
    href_A_names = href_A["clean_text"].dropna().unique()

    # If we have at least one strong href A candidate, trust them directly for this firm.
    if len(href_A_names) >= 1:
        out = href_A.drop_duplicates(subset=["clean_text"]).copy()
        # Build structural keys for inspection / later debugging
        out["path_sig"] = out["soup_object"].apply(element_path_signature)
        out["list_key"] = out.apply(
            lambda row: derive_list_key(row["path_sig"]), axis=1
        )
        out["google_confirmed"] = False  # not checked in this fast path
        return used_up, out[["clean_text", "type", "card_id", "list_key", "rank", "google_confirmed"]]

    # --- 3. Build path signatures and list keys for all candidates ---

    df["path_sig"] = df["soup_object"].apply(element_path_signature)
    #df["list_key"] = df.apply(
    #    lambda row: derive_list_key(row["path_sig"]), axis=1
    #)

    # --- Group by structural patterns to find homogeneous lists ---

    groups = group_homogeneous_lists_df(
        df,
        path_col="path_sig",
        name_col="clean_text",
        type_col="type",
        id_col="card_id",
        min_group_size=3
    )

    for group in groups.values():
        if group:
            print(f"Homogeneous group found with names: {group['names']}")


    # --- 4. Google-based confirmation for candidates: changed to searching groups. Only check first 3 in group to confirm.  ---

    final_portcos = pd.DataFrame()
    href_rich_groups = [g for g in groups.values() if g.get("all_cards_have_href")]

    # If exactly one group has corresponding hrefs, accept it immediately.
    if len(href_rich_groups) == 1:
        only_group = href_rich_groups[0]
        print("Only one group has corresponding hrefs; accepting it without Google confirmation.")
        final_portcos = df[df["clean_text"].isin(only_group["names"])].copy()
        return used_up, final_portcos

    # If multiple groups have hrefs, only consider those for Google confirmation; otherwise, consider all groups.
    candidate_groups = href_rich_groups if href_rich_groups else list(groups.values())

    for i, group in enumerate(candidate_groups):
        group_names = list(group["names"])
        candidates = False
        if group["cross_type_matching"]:
            print(f"Group {i} has cross-type matching; skipping Google confirmation.")
            candidates = True
        else:
            for name in group_names[:3]:  # check up to first 3 candidates in the group
                #idea: if any of the first 3 candidates in the group is google confirmed, we accept the whole group, as they are structurally similar
                print(f"Google confirming candidate name '{name}' in group {i}...")
                used_up, confirmed = google_confirm_name(name, _norm(pe_full_name), google_search_fn, used_up)
                if confirmed:
                    candidates = True
        
        if candidates:
            print(f"Group {group} confirmed by Google search.")
            final_portcos = df[df["clean_text"].isin(group_names)].copy()
            
            break  # stop at first confirmed group
        else:
            print(f"Group {group} NOT confirmed by Google search.")


 

    

    

    return used_up, final_portcos
