"""
Streamlit app for labeling PortCo names from portfolio pages.
"""

import streamlit as st
import json
import os
from pathlib import Path


st.set_page_config(page_title="Label PortCo Names", layout="wide")
st.title("Label PortCo Names")

# ============================================================================
# SIDEBAR: Setup and Controls
# ============================================================================

st.sidebar.header("Setup")

def get_latest_labeling_data_path() -> str:
    output_dir = Path(__file__).resolve().parents[4] / "output"
    if not output_dir.exists():
        return "labeling_data.json"

    candidates = sorted(
        output_dir.glob("labeling_data_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return str(candidates[0]) if candidates else "labeling_data.json"


labeling_data_path = st.sidebar.text_input(
    "Labeling data JSON path:",
    value=get_latest_labeling_data_path()
)

if st.sidebar.button("Load Data"):
    if os.path.exists(labeling_data_path):
        with open(labeling_data_path, 'r', encoding='utf-8') as f:
            st.session_state.labeling_data = json.load(f)
        st.sidebar.success("✓ Data loaded")
    else:
        st.sidebar.error(f"File not found: {labeling_data_path}")

output_path = st.sidebar.text_input(
    "Save labels to:",
    value="labels.json"
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

st.subheader(f"Sample: {current_sample_id}")
st.caption(f"Total leaves: {len(leaves)}")

if current_sample_id not in st.session_state.labels:
    st.session_state.labels[current_sample_id] = {}

current_labels = st.session_state.labels[current_sample_id]

# Display each leaf
for tag_id, leaf_info in sorted(leaves.items(), key=lambda x: int(x[0])):
    inner = leaf_info['innerText'][:100]
    url = leaf_info['urlText'][:50]
    
    with st.expander(f"**{tag_id}** - {leaf_info['tagName']}: {inner}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**InnerText:**")
            st.text(leaf_info['innerText'])
        
        with col2:
            st.write("**UrlText:**")
            st.text(leaf_info['urlText'])
        
        st.divider()
        
        # Labeling
        is_portco = st.checkbox(
            "Is PortCo name?",
            value=tag_id in current_labels and current_labels[tag_id]['is_portco'],
            key=f"{current_sample_id}_{tag_id}_check"
        )
        
        if is_portco:
            text_source = st.radio(
                "Text source:",
                ["innerText", "urlText"],
                index=0 if (tag_id not in current_labels or current_labels[tag_id].get('text_source') == 'innerText') else 1,
                key=f"{current_sample_id}_{tag_id}_source",
                horizontal=True
            )
            
            current_labels[tag_id] = {
                'is_portco': True,
                'text_source': text_source,
                'innerText': leaf_info['innerText'],
                'urlText': leaf_info['urlText']
            }
        else:
            if tag_id in current_labels:
                del current_labels[tag_id]

st.divider()

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
        if current_sample_id in st.session_state.labels:
            del st.session_state.labels[current_sample_id]
        st.rerun()
