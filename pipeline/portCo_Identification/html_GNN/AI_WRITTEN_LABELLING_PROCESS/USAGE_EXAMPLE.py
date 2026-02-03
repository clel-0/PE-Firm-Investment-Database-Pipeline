"""
USAGE EXAMPLE - PortCo Labeling System

This shows exactly what the user sees and does.
"""

# ============================================================================
# STEP 1: Prepare CSV
# ============================================================================

"""
Create file: pe_firms.csv

PE_firm_name,website
Bain Capital,https://www.baincapital.com
Apollo Global,https://www.apolloglobal.com
Carlyle Group,https://www.carlyle.com
"""

# ============================================================================
# STEP 2: Extract Leaves
# ============================================================================

"""
$ python GNN_training_target.py pe_firms.csv labeling_data.json

Loaded 3 PE firms from pe_firms.csv
============================================================
Enter portfolio page URLs (copy & paste from browser)
============================================================

Bain Capital
------------------------------------------------------------
Enter portfolio page URL (copy & paste): https://www.baincapital.com/portfolio
✓ Fetched 125432 characters
✓ Extracted 342 leaves

Apollo Global
------------------------------------------------------------
Enter portfolio page URL (copy & paste): https://www.apolloglobal.com/companies
✓ Fetched 98765 characters
✓ Extracted 287 leaves

Carlyle Group
------------------------------------------------------------
Enter portfolio page URL (copy & paste): 
Skipped.

============================================================
✓ Saved 2 samples to labeling_data.json
Ready to label in Streamlit: streamlit run app.py
============================================================
"""

# ============================================================================
# STEP 3: Label in Streamlit App
# ============================================================================

"""
$ streamlit run app.py

[Browser opens automatically]

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Label PortCo Names                                         │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Setup                                                   │ │
│ │                                                         │ │
│ │ Labeling data JSON path: labeling_data.json            │ │
│ │ [Load Data]                                             │ │
│ │                                                         │ │
│ │ Save labels to: labels.json                             │ │
│ │ [Save Labels]                                           │ │
│ │                                                         │ │
│ │ Progress: 1/2                                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Sample: [Bain Capital_0 ▼]                                 │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ Sample: Bain Capital_0                                      │
│ Total leaves: 342                                           │
│                                                             │
│ ▼ **15** - p: Stripe                                        │
│   ├─ InnerText: Stripe                                      │
│   ├─ UrlText:                                               │
│   ├─ [☑] Is PortCo name?                                    │
│   └─ Text source: ( ◉ innerText )                           │
│                                                             │
│ ▼ **16** - a: Visit                                         │
│   ├─ InnerText: Visit Website                               │
│   ├─ UrlText: stripe                                        │
│   ├─ [☑] Is PortCo name?                                    │
│   └─ Text source: (    urlText ◉ )                          │
│                                                             │
│ ▼ **20** - div: Disclaimer text                             │
│   ├─ InnerText: Copyright 2024...                           │
│   ├─ UrlText:                                               │
│   └─ [☐] Is PortCo name?                                    │
│                                                             │
│ [...more leaves...]                                         │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ [← Previous] [Next →] [🗑️ Clear]                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

User actions:
1. Loads data
2. Expands leaves one by one
3. Checks "Is PortCo name?" for company names
4. Selects text source
5. Uses Previous/Next to navigate
6. Clicks "Save Labels" when done
"""

# ============================================================================
# STEP 4: Labeled Data Output
# ============================================================================

"""
File created: labels.json

{
    "Bain Capital_0": {
        "15": {
            "is_portco": true,
            "text_source": "innerText",
            "innerText": "Stripe",
            "urlText": ""
        },
        "16": {
            "is_portco": true,
            "text_source": "urlText",
            "innerText": "Visit Website",
            "urlText": "stripe"
        },
        "20": {
            "is_portco": false
        },
        "21": {
            "is_portco": true,
            "text_source": "innerText",
            "innerText": "Figma",
            "urlText": ""
        },
        ...
    },
    "Apollo Global_1": {
        "8": {
            "is_portco": true,
            "text_source": "innerText",
            "innerText": "Dell Technologies",
            "urlText": ""
        },
        ...
    }
}

Now ready for GNN training!
"""

print(__doc__)
