# PortCo Labeling System

Simple labeling system for supervised GNN training.

## Quick Start

```bash
# 1. Install dependencies
pip install pandas requests beautifulsoup4 streamlit

# 2. Prepare your CSV with PE firms (pe_firms.csv):
# FullName,Website
# Bain Capital,https://www.baincapital.com
# Apollo Global,https://www.apolloglobal.com

# 3. Extract leaves from portfolio pages (from repo root)
python -m pipeline.portCo_Identification.html_GNN.AI_WRITTEN_LABELLING_PROCESS.GNN_training_target

# 4. Label PortCo names in browser
streamlit run app.py

# 5. Find your labels in labels.json
```

## Workflow

1. **GNN_training_target.py**: 
   - Asks for portfolio page URL for each PE firm (copy & paste)
   - Extracts all text elements (leaves) from each page
   - Saves to `labeling_data.json`

2. **app.py**: 
   - Load `labeling_data.json`
   - For each leaf node, mark if it's a PortCo name
   - Choose text source: innerText or urlText
   - Save labels to `labels.json`

## Output Format

`labels.json`:
```json
{
    "Bain Capital_0": {
        "15": {
            "is_portco": true,
            "text_source": "innerText",
            "innerText": "Stripe",
            "urlText": ""
        }
    }
}
```

Done.
