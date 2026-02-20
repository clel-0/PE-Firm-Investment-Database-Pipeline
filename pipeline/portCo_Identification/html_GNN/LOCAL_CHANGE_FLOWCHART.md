# Local Change Flowchart (Prompt 5 Scope)

```mermaid
flowchart TD
    A[HTML soup input] --> B[A_convert_html_to_tree.convert_html_to_tree]

    subgraph Manual Coupling Inputs
      M1[step3_helperFunctions.inner_text_logic]
      M2[step3_attempt3.name_from_src]
      M3[step3_attempt4.name_from_href]
      M4[text_scoring.element_path_signature]
    end

    M1 --> B
    M2 --> B
    M3 --> B
    M4 --> B

    B --> C[Node dict per tag<br/>children, tagID, tagName, class, UrlText, UrlType, InnerText, sig]
    C --> D[B_convert_node_to_vector.convert_node_to_vector]
    D --> E[Node vectors<br/>vector + sig_vector]

    E --> F[C_subpage_GNN_process.portfolio_page_finder_GNN]
    E --> G[D_naming_GNN_process.GNN_process_portCo]

    F --> H[id_to_score for href-leaf candidates]
    G --> I[leafList for naming scores]

    H --> J[training_functions.page_batch_loss]
    I --> K[training_functions.naming_batch_loss]
```

## What this map is for
- Defines the exact local boundary where Prompt 5 checks coupling contracts.
- Ensures return types from manual helpers match what the tree/vector/model code consumes.
- Highlights where malformed fields silently degrade features vs hard-crash.
