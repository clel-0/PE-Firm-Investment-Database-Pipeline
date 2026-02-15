"""
Streamlit app for labeling PortCo names from portfolio pages.


__STREAMLIT BASICS__
Streamlit is an interactive web app framework centered around a 
dictionary-like object called `session_state`. This allows the programmer to store data
across page reruns. Widgets (sidebar.*, checkboxes, radio buttons, etc.) are directly tied 
to user interactions on the webpage, allowing users to update session_state 
through clicks, selections, and text input in a manner that is easy to code and 
clean to interact with.

You can also write onto the webpage directly using streamlit commands such as 
st.write, st.text, st.metric, st.columns, etc.

Note that the order of the code is important for both code logic and page layout,
as Streamlit executes the script top-to-bottom on every interaction.

Key concepts:
- Script reruns completely on every interaction
- session_state persists data between reruns
- Widget values can be bound to session_state keys
- Code order determines both execution flow and UI layout


__STREAMLIT WIDGETS__

    "st.radio": {
        "arguments": {
            "label": "Display text shown above the radio button options",
            "options": "List of values the user can select (only one allowed)",
            "index": "Which option is pre-selected by index number (0-indexed)",
            "key": "Unique identifier that binds the widget to session state",
            "horizontal": "Display options side-by-side (True) or stacked (False)"
        },
        "returns": "The value of the selected option"
    },
    "st.checkbox": {
        "arguments": {
            "label": "Display text shown next to the checkbox",
            "value": "Pre-checked state (True/False); defaults to False",
            "key": "Unique identifier that binds the widget to session state",
            "disabled": "Whether the checkbox is clickable (True locks it)"
        },
        "returns": "Boolean (True if checked, False if unchecked)"
    }

__OUTPUT STRUCTURE__

save a JSON file with structure:

{website_url: {portco_tagIDs: [], overall_type: "innerText"/"urlText"}}

"""

import streamlit as st
import json
import os
from pathlib import Path
import time

current_time = time.strftime("%Y-%m-%d-%H-%M-%S")


st.set_page_config(page_title="Label PortCo Names", layout="wide")
st.title("Label PortCo Names")

# ============================================================================
# SIDEBAR: Setup and Controls
# ============================================================================

st.sidebar.header("Setup")

def get_labeling_data_files() -> list:
    output_dir = Path(__file__).resolve().parents[4] / "output"
    if not output_dir.exists():
        return ["labeling_data.json"]

    candidates = sorted(
        output_dir.glob("labeling_data_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return [str(p) for p in candidates] if candidates else ["labeling_data.json"]


available_files = get_labeling_data_files()
labeling_data_path = st.sidebar.selectbox(
    "Labeling data JSON file:",
    options=available_files,
    index=0
)

if st.sidebar.button("Load Data"):
    if os.path.exists(labeling_data_path):
        with open(labeling_data_path, 'r', encoding='utf-8') as f:
            st.session_state.labeling_data = json.load(f)
        st.sidebar.success("✓ Data loaded")
    else:
        st.sidebar.error(f"File not found: {labeling_data_path}")


repo_root = Path(__file__).parent.parent.parent.parent.parent

output_path = st.sidebar.text_input(
    "Save labels to:",
    value=str(repo_root / "output" / f"naming_data_{current_time}.json")
)

if st.sidebar.button("Save Labels", type="primary"):

    if 'labels' in st.session_state:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.labels, f, indent=2, ensure_ascii=False)
        st.sidebar.success(f"✓ Saved to {output_path}")

st.sidebar.divider()

# Show progress
if 'labeling_data' in st.session_state and 'labels' in st.session_state:
    total = len(st.session_state.labeling_data)
    labeled = len(st.session_state.labels)
    st.sidebar.metric("Progress", f"{labeled}/{total}")

# ============================================================================
# Initialize session state
# ============================================================================

if 'labeling_data' not in st.session_state:
    st.session_state.labeling_data = {}
if 'labels' not in st.session_state:
    st.session_state.labels = {}
if 'current_sample_idx' not in st.session_state:
    st.session_state.current_sample_idx = 0


# ============================================================================
# Main interface
# ============================================================================

if not st.session_state.labeling_data:
    st.warning("⚠️ Load data using sidebar")
    st.stop()

sample_ids = list(st.session_state.labeling_data.keys())
current_sample_id = st.selectbox(
    "Select sample:",
    sample_ids,
    index=st.session_state.current_sample_idx
)
st.session_state.current_sample_idx = sample_ids.index(current_sample_id)

st.divider()

# ============================================================================
# Display and label leaves
# ============================================================================

sample_data = st.session_state.labeling_data[current_sample_id]
leaves = sample_data['leaves']
portfolio_page_url = sample_data.get('portfolio_url', 'N/A' )

st.subheader(f"Sample: {current_sample_id}")
st.caption(f"Total leaves: {len(leaves)}")
st.caption(f"Portfolio page URL: {portfolio_page_url}")

label_key = portfolio_page_url  # website_url in the output JSON

if label_key not in st.session_state.labels:
    st.session_state.labels[label_key] = {"portco_tagIDs": [], "overall_type": "innerText"}

current_labels = st.session_state.labels[label_key]

leafList = [l for l in leaves.items() if l[1]['innerText']]
if leafList != leaves.items():
    st.info(f"Showing {len(leafList)} leaves with non-empty innerText out of {len(leaves)} total leaves.")

# Display each leaf
for tag_id, leaf_info in sorted(leafList, key=lambda x: int(x[0])):
    inner = leaf_info['innerText']
    url = leaf_info['urlText'] if leaf_info['urlText'] else ""
    if isinstance(url, list):
        url = url[0] if url else ""
    
    with st.expander(f"**{tag_id}** - {leaf_info['tagName']}: {inner}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**InnerText:**")
            st.text(inner)
        
        with col2:
            st.write("**UrlText:**")
            st.text(url)
        
        st.divider()
        
        # Labeling
        is_portco = st.checkbox(
            "Is PortCo name?",
            value=tag_id in current_labels["portco_tagIDs"],
            key=f"{current_sample_id}_{tag_id}_check"
        )

        if is_portco:
            # We want ONE overall type for the page; use the stored one as the default
            text_source = st.radio(
                "Text source (applies to the whole page):",
                ["innerText", "urlText"],
                index=0 if current_labels.get("overall_type", "innerText") == "innerText" else 1,
                key=f"{current_sample_id}_{tag_id}_source",
                horizontal=True
            )

            current_labels["overall_type"] = text_source

            if tag_id not in current_labels["portco_tagIDs"]:
                current_labels["portco_tagIDs"].append(tag_id)

        else:
            if tag_id in current_labels["portco_tagIDs"]:
                current_labels["portco_tagIDs"].remove(tag_id)

st.divider()


# No PE firms have 0 portcos. Therefore an empty portco_tagIDs list implies labeling was not completed for that page. 
for k,v in st.session_state.labels.items():
    if v["portco_tagIDs"] == []:
        del st.session_state.labels[k]


# Navigation
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Previous"):
        st.session_state.current_sample_idx = max(0, st.session_state.current_sample_idx - 1)
        st.rerun()

with col2:
    if st.button("Next →"):
        st.session_state.current_sample_idx = min(len(sample_ids) - 1, st.session_state.current_sample_idx + 1)
        st.rerun()

with col3:
    if st.button("🗑️ Clear this sample"):
        label_key = portfolio_page_url
        if label_key in st.session_state.labels:
            del st.session_state.labels[label_key]
        st.rerun()
