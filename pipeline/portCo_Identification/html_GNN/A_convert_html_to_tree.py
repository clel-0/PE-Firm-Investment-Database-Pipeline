from ..manual_HTML_analysis.step3_attempt3 import name_from_src
from ..manual_HTML_analysis.step3_attempt4 import name_from_href
from ..manual_HTML_analysis.step3_helperFunctions import inner_text_logic, _norm
from ..manual_HTML_analysis.text_scoring import element_path_signature

from bs4 import BeautifulSoup as B
from bs4 import Tag

#1) 
def convert_html_to_tree(soup: B):
    """
    Convert bs4 html to tree with tags as nodes, and one-way edges from parent to child.
    For each node, compute the 351 dim vector embedding as per the description above.
    Returns the tree structure, and the hashmap of tagID to node vector.

    Namely:

    Returns the head of the tree, where the node structure is as follows:
    {
        'children': list of child nodes (same structure),
        'sig': tuple, #element path signature
        'tagID': int,
        'tagName': str,
        'class': str,
        'UrlText': str,
        'UrlType': {-1,0,1}, (src => 1, href => 0, none => -1)
        'InnerText': str
    }

    (vector will be added later, as vectorisation is dependent on the above attributes)

    """

    
    tag_id = 0  # unique tagID counter
    id_to_node = {}
    queued = set()  # Track which bs4 elements have been queued
 
    def build_node(bs4_element):
        
        nonlocal tag_id
        nonlocal id_to_node

 
        try:
            class_raw = bs4_element.get('class', [])
            class_raw = _norm(" ".join(class_raw)) if class_raw else ""

              
            inner_text = inner_text_logic(bs4_element)
            if not inner_text:
                #check alternative inner text sources for certain tags
                if bs4_element.name == 'img':
                    inner_text = bs4_element.get('alt', '')
                    if ";" in inner_text:
                        inner_text = inner_text.split(";")[0]  #take text before semicolon, as alt text often has "Company Name; additional info"

            if bs4_element.get('href'):
                url_text = name_from_href(bs4_element.get('href'))
                url_type = 0
            elif bs4_element.get('src'):
                url_text = name_from_src(bs4_element.get('src'))
                url_type = 1
            else:
                url_text = ""
                url_type = -1 #represents no url

            if isinstance(url_text, list):
                url_text = url_text[0] if url_text else ""  # Take first element if list, else empty string
            if isinstance(url_text, tuple):
                url_text = url_text[0] if url_text else ""

            
            try:
                sig = element_path_signature(bs4_element)
                sig = tuple(sig)
            except Exception as e:
                print(f"Warning: Could not compute signature for {bs4_element.name}: {e}")
                sig = ()

            node = {
                'children': [],
                'sig': sig,
                'tagID': tag_id,
                'tagName': bs4_element.name if bs4_element.name else "",
                'class': class_raw,
                'UrlText': url_text,
                'UrlType': url_type,
                'InnerText': inner_text,
                'bs4_element': bs4_element  # Store the original bs4 element for reference: namely for href searching
            }

            id_to_node[tag_id] = node
            tag_id += 1  # Increment here so every node gets unique ID
            return node
        except Exception as e:
            import traceback
            print(f"ERROR in build_node: {e}")
            traceback.print_exc()
            return None    
    
    

    root_tag = soup.html if getattr(soup, "html", None) is not None else soup.find(True)
    if root_tag is None:
        return None, {}

    soup_heads = []
    soup_heads.append((root_tag, None)) # (bs4_element, parent_tree_node)
    queued.add(id(root_tag)) #this ensures we don't re-queue the same bs4 element

    headcheck = True #this will be used to save the head node later

    tree_head = None

    #while loop that builds the tree: BFS traversal
    while soup_heads != []:
        current_bs4, parent_node = soup_heads.pop(0)
        
        # Build node only once when popped from queue
        current_tree_node = build_node(current_bs4)

        # Skip if build_node returned None
        if current_tree_node is None:
            print("Skipping a node due to build_node failure.")
            continue
        
        # Attach to parent if not root
        if parent_node is not None:
            parent_node['children'].append(current_tree_node)

        #sets the head node  
        if headcheck:
            tree_head = current_tree_node
            headcheck = False

        children = [
            c for c in current_bs4.children
            if isinstance(c, Tag)
        ]
        
        #builds the child nodes and appends them to the current tree node
        for child in children:
            if isinstance(child, Tag):
                # Only add to queue if not already queued
                if id(child) not in queued:
                    soup_heads.append((child, current_tree_node))
                    queued.add(id(child))
        

    return tree_head, id_to_node