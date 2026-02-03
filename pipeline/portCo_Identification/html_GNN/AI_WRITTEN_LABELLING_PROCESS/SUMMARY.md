# ✅ Simplified PortCo Labeling System

## Summary

The labeling system has been **completely simplified** to just **3 files** focused on the core task: labeling PortCo names for supervised GNN training.

### Files

```
AI_WRITTEN_LABELLING_PROCESS/
├── GNN_training_target.py    ← Extract leaves from portfolio pages
├── app.py                     ← Label PortCo names in browser
├── README.md                  ← Quick start (60 seconds)
└── USAGE_EXAMPLE.py           ← See what it looks like
```

## How It Works

### Phase 1: Extract Leaves (Terminal)

```bash
python GNN_training_target.py pe_firms.csv labeling_data.json
```

- User provides portfolio URL for each PE firm (copy & paste)
- System fetches page, extracts all text elements (leaves)
- Saves to `labeling_data.json` for labeling

### Phase 2: Label PortCo Names (Browser)

```bash
streamlit run app.py
```

- Load `labeling_data.json`
- For each leaf, mark if it's a PortCo name
- Choose text source: `innerText` or `urlText`
- Save to `labels.json`

## Input & Output

**Input CSV** (`pe_firms.csv`):
```
PE_firm_name,website
Bain Capital,https://www.baincapital.com
Apollo Global,https://www.apolloglobal.com
```

**Output** (`labels.json`):
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

## Code Quality

✅ **Simple**: 3 files, ~200 lines total
✅ **Clear**: Each function does one thing
✅ **Fast**: 2-minute setup
✅ **Ready**: For supervised GNN training

No unnecessary abstractions, documentation bloat, or complexity.
