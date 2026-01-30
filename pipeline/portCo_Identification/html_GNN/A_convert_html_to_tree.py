from manual_HTML_analysis.step3_attempt3 import name_from_src
from manual_HTML_analysis.step3_attempt4 import name_from_href
from manual_HTML_analysis.step3_helperFunctions import inner_text_logic, _norm
from manual_HTML_analysis.text_scoring import element_path_signature

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
    id = 0  # unique tagID counter
    id_to_node = {}
 
    def build_node(bs4_element):
        
        nonlocal id
        nonlocal id_to_node


        class_raw = bs4_element.get('class', [])
        class_raw = _norm(" ".join(class_raw)) if class_raw else ""

        inner_text_raw = bs4_element.get_text(separator=' ', strip=True) if bs4_element.get_text() else ""   
        inner_text = inner_text_logic(inner_text_raw)

        if bs4_element.get('href'):
            url_text = name_from_href(bs4_element.get('href'))
            url_type = 0
        elif bs4_element.get('src'):
            url_text = name_from_src(bs4_element.get('src'))
            url_type = 1
        else:
            url_text = ""
            url_type = -1 #represents no url

        #groupID 
        sig = element_path_signature(bs4_element)
        sig = tuple(sig)

        


        node = {
            'children': [],
            'sig': sig,
            'tagID': id,
            'tagName': bs4_element.name if bs4_element.name else "",
            'class': class_raw,
            'UrlText': url_text,
            'UrlType': url_type,
            'InnerText': inner_text,
            'bs4_element': bs4_element  # Store the original bs4 element for reference: namely for href searching
        }

        id_to_node[id] = node
        return node    
    
    

    soup_heads = []
    soup_heads.append(soup.html) # starting from the html tag

    headcheck = True #this will be used to save the head node later

    tree_head = None

    #while loop that builds the tree: BFS traversal
    while soup_heads != []:
        current_bs4 = soup_heads.pop(0)
        current_tree_node = build_node(current_bs4)

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
                child_node = build_node(child)
                id += 1
                current_tree_node['children'].append(child_node)
                soup_heads.append(child)
        

    return tree_head, id_to_node