

import os
from playwright.sync_api import sync_playwright, Error
import playwright
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import re
import requests
from urllib.parse import urljoin
import lxml
from bs4 import BeautifulSoup   
from urllib.parse import urlparse
from helper_functions import *


"""

__Step 3: Extracting portCo names (various methods)__:
    Note: since multiple portCos can be found, we will return a list of dicts, where each dict corresponds to a portCo found.
    Note: since step2 can return multiple classes, we will try each class in order of rank until we find portCos. Therefore, different portCos may be found using different rankings of classes.
    Note: 'class_used' will be a html path to the class used to find that portCo, using a CSS selector path.

    For that given website, each class will be tried in order of rank until portCos are found, or classes exhausted.
    Due to different formatting of the same portCo, note that this process may produce duplicate portCo names, which will be filtered out later.

    Returns list of dicts, where each dict has keys:
        'potential_portco_names': str, 'step3_method_used': int, 'class_used': str, 'class_confidence_used': int, 'extraction_confidence': int


"""


def _norm(s): 
        """
        this normalizes strings by stripping whitespace and collapsing multiple spaces into one space
        it repleaces one or more whitespace characters with a single space, and then trims leading/trailing spaces
        """
        return re.sub(r"\s+"," ", s or "").strip()

def _domain(u):
    try:
        """
        netloc refers to the network location part of the URL, which includes domain and port
        urlparse splists the URL into components; scheme://netloc/path?query#fragment
        therefore, urlparse(u).netloc gives us the domain (and port if present)
        eg: urlparse("https://www.example.com/path").netloc -> "www.example.com"
        then, we lowercase it and strip "www." prefix if present
        return the cleaned domain, or empty string on error
        """
        netloc = urlparse(u).netloc.lower()
        if netloc.startswith("www."): netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def step3_attempt_1(portfolio_website: dict, portco_classes: list[str]) -> list[dict]:
    """
    Extract portCo names from JSON LD scripts within the chosen html classes from step 2, as well as throughout the entire page.

    Algorithm is explained in the extract_portcos_from_jsonld docstring below, with the algorithms of 
    helper functions explained in their docstrings.

    Namely, website is requested, html content is extracted and passed through extract_portcos_from_jsonld to extract portCo names from JSON LD scripts.

    """
    
    #ChatGPT Attempt 1 implementation: refine and rewrite
    TYPE_WHITELIST = {"Organization","Corporation","LocalBusiness","Brand","Company"}
    TYPE_BLACKLIST = {"WebPage","WebSite","BreadcrumbList","Article","NewsArticle","Person","FAQPage","HowTo","BlogPosting"}
    from urllib.parse import urlparse

    
    def _logo_url(val):
        """
        Given the val is a dict, return the 'url' or '@id' field if present, else return empty string
        """
        
        if isinstance(val, dict):
            return val.get("url") or val.get("@id") or ""
        return val or ""

    def _iter_jsonld_nodes(soup):
        """
        ALGORITHM:
        1) collates all scripts within the soup of the PE firm html with type JSON LD. 
        2) Then, loading each script as a json object is attempted. 
        3) Given this works, for each json object we then look for the graph tag, 
          and if the graph tag points to a list, we add all the elements of that list to a new
          'candidates' list. 
        4) Additionally, if the graph tag doesn't exist or it does but doesnt point to a list, 
          we add the top-level dict.
        5) Then, for each candidate of a given JSON-LD script, if the candidate is of type 
          ItemList and its itemListElement value is a list, iterate over each element of itemListElement.
          If an element is a dict and has an item key whose value is itself a dict, yield that item dict as n, 
          along with the JSON-LD script it came from (s) and the source tag "itemlist".
        6) If an itemListElement dict either does not have an item key or its item value is not a dict, then 
           create a synthetic dict synth based on the list item itself: set @type from the list item's @type 
           if present (or "ListItem" otherwise), and copy over name and url from the list item if they exist. 
           Yield synth in the same way, with the same script element s and source tag "itemlist".
        7) Then, if the type isnt itemlist, assume the candidate is a single portCo, so then yield the candidate (n), 
          the JSON LD it came from (s), and derivation type "jsonld". 


        Yield (node, script_el, source_tag) where node is a dict entity.
        NOTE: Yield is a special type of return that allows the function to be an iterator, producing a sequence of values over time.
        in this case, it yields each JSON-LD node found in the HTML soup, remembering the script element it came from and the source tag type 
        (jsonld or itemlist).
        In essence, yield is essentially a return function, but it remembers its state so that within the next call, it takes the arguments one ahead of the last yielded one.
        """
        for s in soup.find_all("script", attrs={"type":"application/ld+json"}):
            try:
                data = json.loads(s.string or s.text or "")
            except Exception:
                continue
            # normalize to iterable of nodes
            candidates = []
            if isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    candidates.extend([n for n in data["@graph"] if isinstance(n, dict)])
                else:
                    candidates.append(data)
            elif isinstance(data, list):
                candidates.extend([n for n in data if isinstance(n, dict)])
            else:
                continue

            #n is a dict corresponding to a JSON LD node within the script
            for n in candidates:
                # expand ItemList into its elements as separate nodes
                #note that @type may be a string or a list of strings, so we handle both cases
                t = n.get("@type")
                types = {t} if isinstance(t, str) else set(t or [])
                if "ItemList" in types and isinstance(n.get("itemListElement"), list):
                    for it in n["itemListElement"]:
                        if isinstance(it, dict):
                            # two common shapes
                            if "item" in it and isinstance(it["item"], dict):
                                print(f"Found ItemList element with item key: {it['item']}")
                                yield it["item"], s, "itemlist"
                            else:
                                # synthesize an org-like node if keys present
                                synth = {"@type": it.get("@type") or "ListItem"}
                                if "name" in it: synth["name"] = it["name"]
                                if "url" in it: synth["url"] = it["url"]
                                print(f"Synthesizing ItemList element as: {synth}, and yielding")
                                yield synth, s, "itemlist"
                    continue
                print(f"Yielding JSON-LD node: {n}")
                yield n, s, "jsonld"

    #NOTE: this isnt used, as the _is_company_like function is already integrated within the main loop of step3_attempt_1
    def _is_company_like(n):
        """
        Returns true if the set of words in the @type field of the JSON LD node intersect with the TYPE_WHITELIST, 
        and false if they intersect with the TYPE_BLACKLIST.
        """
        t = n.get("@type")
        
        types = {t} if isinstance(t, str) else set(t or [])
        #in this case, the and/or logic checks if the types of the JSON LD node intersect with the blacklist or whitelist, i.e. if both contain any common elements
        if types & TYPE_BLACKLIST:
            return False
        if types & TYPE_WHITELIST:
            return True
        # unknown type but has org-ish structure → weak accept (handled by scoring)
        if bool(n.get("name") and (n.get("url") or n.get("logo") or n.get("sameAs"))):
            print(f"Unknown JSON-LD type encountered: {types}, but may have org-like structure.")
            return True
        return False

    def _extract_entity(n):
        """
        Extract normalized entity fields from a JSON-LD node.

        ALGORITHM:

        1) Normalizes the "name" field with _norm(), e.g. stripping leading/trailing
        whitespace and collapsing multiple spaces.

        2) Extracts the "url" field directly from the node, defaulting to an empty
        string if it is missing or falsy.

        3) Extracts the "logo" URL using _logo_url(n.get("logo")), which handles
        both string and dict logo values (e.g. checking "url" or "@id" inside a logo dict).

        4) Extracts the "sameAs" field, ensuring the result is a list:
        if "sameAs" is a single string, it is wrapped in a list; if it is missing or falsy,
        an empty list is used.

        5) Handles the "@type" field so that "jsonld_type" is a single string:
        if "@type" is a list, prefer the first type present in TYPE_WHITELIST; otherwise
        use the first element of the list, or empty string if no type is available.

        6) Computes helper fields:
        * "_url_domain": domain of the "url" (via _domain()).
        * "_logo_domain": domain of the "logo" (via _domain()), or, if that is unavailable,
            falls back to the domain of the first "sameAs" URL (if any).

        7) Returns a dict with keys:
        "name", "url", "logo", "sameAs", "jsonld_type", "_url_domain", "_logo_domain".
        """
        name = _norm(n.get("name"))
        url  = n.get("url") or ""
        logo = _logo_url(n.get("logo"))
        same = n.get("sameAs") or []
        if isinstance(same, str): same = [same]
        jtype = n.get("@type")
        if isinstance(jtype, list): 
            # prefer an org-like type if present
            jtype = next((t for t in jtype if t in TYPE_WHITELIST), jtype[0] if jtype else None)
        return {
            "name": name,
            "url": url,
            "logo": logo,
            "sameAs": same,
            "jsonld_type": jtype or "",
            "_url_domain": _domain(url),
            "_logo_domain": _domain(logo) or (_domain(same[0]) if same else ""),
        }

    #this will also be used in step 3 attempt 2.py and step 3 attempt 3.py
    def _collect_cards(soup, card_class_tokens):
        """
        takes a BeautifulSoup object (soup) derived from the html of the PE firm site, and a list of class tokens (card_class_tokens) found from step 2, as the input parameters.
        ALGORITHM:
        1) lowercase all the class tokens provided in card_class_tokens and stores them in a set called tokens. 
        2) initialize an empty list called cards to store the matched card elements.
        3) for each element (tag) in the soup that has a class attribute:
            a) get the list of class names within that element (cls).
            b) if any of the classnames found in step 2 (tokens) are present in the class names of the element (cls), then:
                i) extract signals from the element:
                    - find the first anchor tag within the element and get its href attribute (href).
                    - find the first img tag within the element and get its src attribute (img).
                    - extract the domain from the href and img URLs using the _domain helper function (link_dom, img_dom).
                    - attempt to extract a name hint from common title-like nodes within the element (name_hint):
                        * check for elements with aria-label, img alt attributes, h1-h4 tags, and common class names like title or name.
                        * if found, normalize the text content using _norm() and store it in name_hint, then break the loop. 
                        (Note: this name_hint is weak in confidence as it may not always correspond to the portCo name,
                        namely we are just traversing through the alts and headings).

                ii) append a tuple of (element, joined class string, signals dict) to the cards list.
        4) Return list of (el, class_string, signals_dict) for candidate cards.
        
        """

        tokens = set()
        for cls_str in card_class_tokens:
            # split the big "summary-item summary-item-record-type-image ..." into pieces
            for t in cls_str.split():
                tokens.add(t.lower())
        cards = []
        #looking through all elements with a class attribute
        #the find_all method of BeautifulSoup is used to find all HTML elements that have a class attribute in this case, as its first argument collates all tags, and the second argument specifies the tag must have a class attribute.
        for el in soup.find_all(True, class_=True):
            cls = [c for c in el.get("class") if isinstance(c, str)]
            if any(tok in (c.lower() for c in cls) for tok in tokens):
                # signals: anchor & image domains + visible title-ish text
                href = (el.find("a", href=True) or {}).get("href") if el.find("a", href=True) else ""
                img  = (el.find("img", src=True) or {}).get("src") if el.find("img", src=True) else ""
                link_dom = _domain(href)
                img_dom  = _domain(img)
                # quick name hint from typical title nodes or alt
                name_hint = None
                for sel in ["[aria-label]","img[alt]","h1","h2","h3","h4",".title",".name","strong"]:
                    node = el.select_one(sel)
                    if node:
                        name_hint = _norm(node.get("aria-label") or getattr(node, "get_text", lambda *_: "")(" ") or node.get("alt"))
                        if name_hint: break
                #these will be used as reasoning for matching later on (in extract_portcos_from_jsonld)
                cards.append((el, cls, {"link_domain":link_dom, "img_domain":img_dom, "name_hint":name_hint}))
        return cards

    def _name_matches(a, b):
        """
        Checks if to strings match regardless of formatting differences, through normalization and lowercasing.
        Additionally, accepts strong substring matches where one string is contained within the other and is at least 3 characters long.
        """
        if not a or not b: return False
        aa, bb = _norm(a).lower(), _norm(b).lower()
        if aa == bb: return True
        # Accept strong substring containing whole words
        print(f"Checking name match between '{aa}' and '{bb}', they are not exactly equal.")
        return (aa in bb and len(aa) >= 3) or (bb in aa and len(bb) >= 3)

    def _score(entity, card_signals, inside_bonus):
        """
        Computes confidence score for JSON-LD entity
        """

        score = 0.0
        # type
        if entity["jsonld_type"] in TYPE_WHITELIST: score += 1.0
        # url/logo domain matches
        if entity["_url_domain"] and entity["_url_domain"] == card_signals.get("link_domain"): score += 0.9
        if entity["_logo_domain"] and entity["_logo_domain"] in {card_signals.get("link_domain"), card_signals.get("img_domain")}: score += 0.6
        # name agreement
        if _name_matches(entity["name"], card_signals.get("name_hint")): score += 0.7
        # proximity bonus
        score += inside_bonus  # 0.3 inside card, 0.2 near, 0 otherwise (we only compute inside here)
        return score

    def extract_portcos_from_jsonld(html, page_url, card_class_tokens, pe_firm_name, pe_firm_domain):
        """
        ALGORITHM:
        1) Parse the HTML into a BeautifulSoup object, using the lxml parser.
        2) Collect candidate card elements from the soup that match the provided class tokens, using the _collect_cards helper function, 
        which returns a list of tuples (element, class_string, signals_dict). Note that element is a BeautifulSoup tag object, 
        class_string is the joined string of class names, and signals_dict contains extracted signals like link domain, image domain, and name hint.
        3) Instantiate an empty list called entities to store the extracted JSON-LD entities with provenance (initial location in the html).
        4) Use the _iter_jsonld_nodes helper function (which yields JSON-LD nodes from the soup) to iterate over each JSON-LD node found in the soup:
            a) Check if the node's @type intersects with the TYPE_BLACKLIST; if so, skip this node.
            b) Use the _extract_entity helper function to extract normalized fields from the JSON-LD node into a dict called ent.
            c) Exclude entities that correspond to the PE firm itself, based on domain and name matching (using _name_matches).
            d) Ensure the entity has at least a name; if not, skip it.
            e) Append a dict containing the extracted entity fields along with the originating script element and source kind to the entities list.
        5) Initialize an empty list called results to store the final matched portCo records.
        
        (NOTE: If the json LD entity does truly correspond to a portCo, it should match with one of the cards found earlier, based on scoring, as within the portfolio subpage, 
        the portCos should be represented within cards corresponding to the classes found in step 2. No matching likely means the entity is not a portCo, even if it has an org-like structure.)

        [Step 6 describes this matching process.]
        6) For each extracted entity in entities:
            a) Initialize a variable best as None to keep track of the best matching card for this entity.
            b) for element (el), class string (cls), and signals dict (sig) in the collected cards:
                i) Check if the JSON-LD script element is nested within the card element, namely:
                if the script element is not None and the card element is a parent of the script with respect to the HTML tree, then return True for inside.
                ii) Assign a bonus score of 0.3 if inside is True, else 0.0 (idea: closer proximity implies stronger relationship).
                iii) Compute the confidence score (sc) using the _score helper, passing the entity, card signals, and bonus score.
                iv) Replace the best match for that given entity if this card yields a higher score than the current best.
            c) If any best match was found:
                i) Compile reasons for matching the entity to the card, based on which criteria were met (type whitelist, url domain match, logo domain match, name match, inside card).
                ii) Determine the rank of the match as "A" if the score is >= 1.8, else "B".
                iii) Append a dict to results containing the matched portCo information, including name, url, logo, jsonld_type, matched_by reasons, container_class, score, rank_label, page_url, and provenance.
        7) De-duplicate the results by (name, url domain) to ensure unique portCo entries.
        8) Return the de-duplicated list of matched portCo records.
                



        Returns list of records:
        {name, url, logo, jsonld_type, matched_by, container_class, score, rank_label, page_url, provenance}
        """

        #parses HTML into a structured tree using an lxml parser known as a BeautifulSoup object.
        #Using to find all class elements that match the card_class_tokens provided from step 2, and extract JSON-LD entities from the page.
        soup = BeautifulSoup(html, "lxml")
        cards = _collect_cards(soup, card_class_tokens)
        for c in cards:
            print(f"Found card with classes: {c[1]} and signals: {c[2]}")
        if not cards:
            print("No candidate cards found on the page with the provided class tokens.")
            print(f"DOUBLE CHECK: card_class_tokens = {card_class_tokens}")

        # Gather JSON-LD entities with provenance
        entities = []

        for i, (node, script_el, src_kind) in enumerate(_iter_jsonld_nodes(soup)):
            # blacklist hard reject
            print(f"Processing JSON-LD number {i+1} for {pe_firm_name}")
            t = node.get("@type")
            types = {t} if isinstance(t, str) else set(t or [])
            if (types & TYPE_BLACKLIST) and not (types & TYPE_WHITELIST): 
                print(f"Skipping blacklisted JSON-LD type: {types}")
                continue

            ent = _extract_entity(node)
            # Exclude the PE firm itself
            #NOTE: checking for name of JSON-LD ensures we dont exclude portCos that happen to share the same domain as the PE firm, due to having their portfolio subpage on the PE firm's domain.
            if ent["_url_domain"] and ent["_url_domain"] == pe_firm_domain.lower() and _name_matches(ent["name"], pe_firm_name):
                print(f"Excluding JSON-LD entity {ent['name']} as it matches PE firm name.")
                continue
            if _name_matches(ent["name"], pe_firm_name):
                print(f"Excluding JSON-LD entity {ent['name']} as it matches PE firm name.")
                continue

            # must have at least a name
            if not ent["name"]:
                print(f"Skipping JSON-LD entity {node} with no name.")
                continue

            entities.append({
                # the ** operator automatically appends all keys/vals from ent, as k/v pairs in the new dict. We could have also just added _script and _source to ent and appended ent directly, but this is cleaner. Remember this operator as it is useful.
                **ent,
                "_script": script_el, 
                "_source": src_kind
            })

        if entities:
            for e in entities:
                print(f"Extracted JSON-LD entity: {e['name']} of type {e['jsonld_type']} from source {e['_source']}")
        else:
            print("No JSON-LD entities extracted from the page.")
            print(f"DOUBLE CHECK: entities list is of size {len(entities)}")

        results = []

        # Try to match each entity to each card (inside proximity bonus when script is inside the card subtree)
        for ent in entities:
            best = None
            for el, cls, sig in cards:
                # inside-card check
                #checks if, firstly the script element the JSON LD entity came from is not None, and secondly if the current card element (el) is a parent of that script element in the HTML tree. If so, it implies that the JSON-LD script is nested within the card element, indicating a closer relationship between the two in the HTML structure.
                inside = ent["_script"] and el in ent["_script"].find_parents()  # True if script nested inside the card. Note that due to the 'and', ent["_script"] is treated as a boolean rather than a script element.
                #bonus given when the JSON LD entity is found within the card element
                bonus = 0.3 if inside else 0.0
                sc = _score(ent, sig, bonus)
                if best is None or sc > best[0]:
                    best = (sc, cls, sig, inside)
            if best:
                sc, cls, sig, inside = best
                if sc >= 1.2:  # threshold per plan
                    #reason matched_by may need to be changed to a dict:
                    # e.g. {"type_whitelist": True, "url_domain_match": False, ...} rather than a list of strings
                    #
                    matched_by = []
                    if ent["jsonld_type"] in TYPE_WHITELIST: matched_by.append("type_whitelist")
                    if ent["_url_domain"] and ent["_url_domain"] == sig.get("link_domain"): matched_by.append("url_domain_match")
                    if ent["_logo_domain"] and ent["_logo_domain"] in {sig.get("link_domain"), sig.get("img_domain")}: matched_by.append("logo_domain_match")
                    if _name_matches(ent["name"], sig.get("name_hint")): matched_by.append("name_match")
                    if inside: matched_by.append("inside_card")

                    rank = "A" if sc >= 1.8 else "B"
                    print(f"Entity {ent['name']} scored {sc} with respect to {cls}, matched by {matched_by}, ranked {rank}.")
                    results.append(
                        {
                        "name": ent["name"],
                        "url": ent["url"],
                        "logo": ent["logo"],
                        "step3_method": 1,
                        "attempt1_specific_info": {
                            "jsonld_type": ent["jsonld_type"],
                            "matched_by": matched_by,
                            "container_class": cls if inside else None,
                            "page_url": page_url,
                            "provenance": {"source": ent["_source"]},
                        },
                        #note: for portCos, numerical scores will be implemented, as portCo confidence score wont be used for discrete decision making, rather it will be used for ranking portCos within the same PE firm.
                        "score": round(sc, 3),
                        "portCo_confidence_rank": rank
                        }
                    )
                else:
                    #weak match fallback for org-like types (rank C)
                    
                    if ent["jsonld_type"] in TYPE_WHITELIST:

                        print(f"Entity {ent['name']} scored {sc}<1.2 with respect to {cls}, however is org-like. Thus will be C ranked.")
                        results.append (
                            {
                            "name": ent["name"],
                            "url": ent["url"],
                            "logo": ent["logo"],
                            "step3_method": 1,
                            "attempt1_specific_info": {
                                "jsonld_type": ent["jsonld_type"],
                                "matched_by": ["type_whitelist"],
                                "container_class": cls if inside else None,
                                "page_url": page_url,
                                "provenance": {"source": ent["_source"]},
                            },
                            "score": round(sc, 3),
                            "portCo_confidence_rank": "C"  # weak match due to low score but org-like type
                            }     

                        )
                        
                    
            else:
                print(f"No matching card found for entity: {ent['name']}")
                if ent["jsonld_type"] in TYPE_WHITELIST:
                    print(f"Entity {ent['name']} while having no matching card, is org-like. Thus will be D ranked.")
                    results.append (
                        {
                        "name": ent["name"],
                        "url": ent["url"],
                        "logo": ent["logo"],
                        "step3_method": 1,
                        "attempt1_specific_info": {
                            "jsonld_type": ent["jsonld_type"],
                            "matched_by": ["type_whitelist"],
                            "container_class": None, # no container since no matching card
                            "page_url": page_url,
                            "provenance": {"source": ent["_source"]},
                        },
                        "score": 0.0, # no score since no matching card
                        "portCo_confidence_rank": "D"  # very weak match due to no card matching but org-like type
                        }     

                    )


            
        # De-dup by (name, url domain)
        seen, out = set(), []
        for r in sorted(results, key=lambda x: (-x["score"], x["name"].lower())):
            key = (r["name"].lower(), _domain(r["url"]))
            if key not in seen:
                seen.add(key)
                out.append(r)
                print(f"Matched portCo: {r['name']} with score {r['score']} using class {r['attempt1_specific_info']['container_class']}, matched by {r['attempt1_specific_info']['matched_by']}")
        if not out:
            print(f"No portCos matched from JSON-LD entities on page: {page_url}")
        
        return out
        


    

    #Using the above helper functions to execute step 3 attempt 1:

    try:
        response = requests.get(portfolio_website["website_found"], timeout=15)
        if response.status_code != 200:
            print(f"Failed to fetch {portfolio_website['website_found']}: Status code {response.status_code}")
            return None
    
        

        html_content = response.text
        
        print(f"Extracting portCos from JSON LD for {portfolio_website['website_found']}...")

        if portfolio_website.get("pe_firm_name"):
            print(f"PE-firm Name: {repr(portfolio_website.get('pe_firm_name'))}")
        else:
            print("PE firm name not provided: note that error may occur for the portCo extraction if the PE firm name is required for exclusion logic.")

        portcos = extract_portcos_from_jsonld(
            html_content,
            portfolio_website["website_found"],
            portco_classes,
            portfolio_website.get("pe_firm_name") or "",
            #ensures pe_firm_domain and url domain are comparable by stripping "www." and lowercasing
            _domain(portfolio_website.get("pe_firm_website", ""))
        )

        return portcos

    except Exception as e:
        print(f"Error fetching or processing {portfolio_website['website_found']}: {e}")
        return None


    
