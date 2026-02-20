# html_GNN Bug-Check Prompt Pack (Excluding `F_overall_GNN.py`)

Use these prompts in order. Each prompt is intentionally narrow so findings are attributable and fixable.

## Global instruction prefix (prepend to every prompt)

```
Scope rules:
- Exclude `pipeline/portCo_Identification/html_GNN/F_overall_GNN.py`.
- Perform a bug-check only (no refactor suggestions unless required to fix a bug).
- Return findings as: severity, file, symbol, expected vs actual, concrete fix.
- Prioritize blockers that cause crashes, silent wrong labels, or ineffective training.
- If uncertain, state assumptions explicitly.
```

## Prompt 1 — Canonical data contract audit

**Attach**
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/GNN_training_target.py`
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/app.py`
- `pipeline/portCo_Identification/html_GNN/training_loop.py`
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/README.md`
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/SUMMARY.md`

**Prompt text**
```
Audit schema and I/O contracts only (not model math):
1) labeling artifacts produced by `GNN_training_target.py`,
2) labels saved by `app.py`,
3) formats consumed in `training_loop.py`.

Find key/type mismatches (dict keys, list/int/string expectations, null handling, CSV column expectations).
Output:
- Canonical schema table for each artifact
- Mismatch list with severity
- Minimal patch order (highest impact first)
```

## Prompt 2 — Portfolio-page target flow consistency

**Attach**
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/GNN_training_target.py`
- `pipeline/portCo_Identification/html_GNN/training_loop.py`
- `pipeline/portCo_Identification/html_GNN/training_functions.py`
- `pipeline/portCo_Identification/html_GNN/C_subpage_GNN_process.py`

**Prompt text**
```
Trace portfolio-page ground truth from labeling -> formatter -> training loss.
Validate that the target object shape expected by `page_batch_loss` matches what formatters provide.
Identify mismatch points and crash/silent-error risks only.
```

## Prompt 3 — Naming target / `tagID` lifecycle

**Attach**
- `pipeline/portCo_Identification/html_GNN/AI_WRITTEN_LABELLING_PROCESS/app.py`
- `pipeline/portCo_Identification/html_GNN/training_loop.py`
- `pipeline/portCo_Identification/html_GNN/A_convert_html_to_tree.py`
- `pipeline/portCo_Identification/html_GNN/D_naming_GNN_process.py`

**Prompt text**
```
Audit end-to-end `tagID` consistency for naming labels.
Check whether labeled IDs remain comparable to runtime leaves after tree conversion/traversal.
Flag ID drift, resets, type mismatches, or indexing assumptions that can break supervision.
```

## Prompt 4 — Tree/vector invariants

**Attach**
- `pipeline/portCo_Identification/html_GNN/A_convert_html_to_tree.py`
- `pipeline/portCo_Identification/html_GNN/B_convert_node_to_vector.py`

**Prompt text**
```
Validate structural invariants and downstream assumptions for node dictionaries:
`children`, `level`, `tagID`, `sig`, text/url fields, vector fields.
Find places where missing or malformed values can cause downstream crashes or wrong features.
```

## Prompt 5 — Cross-package feature coupling

**Attach**
- `pipeline/portCo_Identification/html_GNN/A_convert_html_to_tree.py`
- `pipeline/portCo_Identification/manual_HTML_analysis/step3_helperFunctions.py`
- `pipeline/portCo_Identification/manual_HTML_analysis/step3_attempt3.py`
- `pipeline/portCo_Identification/manual_HTML_analysis/step3_attempt4.py`
- `pipeline/portCo_Identification/manual_HTML_analysis/text_scoring.py`

**Prompt text**
```
Audit interface assumptions for imported helper symbols used by tree/feature generation
(e.g., return types, nullable behavior, string/list contracts, rank encoding).
Report only coupling bugs that can break extraction features or labels.
```

## Prompt 6 — Subpage finder logic sanity

**Attach**
- `pipeline/portCo_Identification/html_GNN/C_subpage_GNN_process.py`
- `pipeline/portCo_Identification/html_GNN/training_functions.py`

**Prompt text**
```
Audit subpage finder candidate generation, score mapping, and true-target matching.
Focus on indexing/key alignment, node-to-score mapping, and loss target selection.
```

## Prompt 7 — Naming model + grouping alignment

**Attach**
- `pipeline/portCo_Identification/html_GNN/D_naming_GNN_process.py`
- `pipeline/portCo_Identification/html_GNN/E_name_grouping.py`
- `pipeline/portCo_Identification/html_GNN/training_functions.py`

**Prompt text**
```
Audit naming score/label alignment and grouping logic.
Look for bugs in thresholding/rank interactions and text-vs-url candidate conflicts.
Return only issues that can affect correctness or training signal quality.
```

## Prompt 8 — Training orchestration reliability

**Attach**
- `pipeline/portCo_Identification/html_GNN/training_loop.py`
- `pipeline/portCo_Identification/html_GNN/training_functions.py`

**Prompt text**
```
Audit training orchestration for silent-failure risks:
batch creation, optimizer/loss wiring, checkpoint save/load consistency,
device placement, and reproducibility assumptions.
```

## Prompt 9 — Consolidated pre-integration gate

**Attach**
- All files from Prompts 1–8

**Prompt text**
```
Create a consolidated defect list grouped by severity:
1) crash/blocker
2) silent wrong labels/predictions
3) ineffective training signal
4) low-priority cleanup

Output a minimal fix sequence (with dependency order) before integrating into `F_overall_GNN.py`.
```

---

## Suggested run protocol

1. Run Prompt 1 and patch only schema blockers.
2. Re-run Prompt 1 after fixes to confirm zero schema blockers.
3. Continue 2 -> 3 -> ... -> 9, fixing blockers before moving to next prompt.
4. Keep a `BUGFIX_LOG.md` with: bug, fix commit hash, verification command, result.
