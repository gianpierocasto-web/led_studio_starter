# Graph Report - LED_Studio_Starter  (2026-11-13)

## Corpus Check
- 4 files · ~31,344 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 4, .mdc 1, .blend 1)

## Summary
- 95 nodes · 185 edges · 13 communities (7 shown, 6 thin omitted)
- Extraction: 79% EXTRACTED · 20% INFERRED · 1% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `da9926bd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Rendering parametrico di strisce LED in Blender
- Graph
- build_master
- exercise_library
- Graph Bootstrap Docs
- led_starter.py
- build_strip
- main
- analyze_strip
- build_reel
- densify_tubes
- make_cable
- realize_collection

## God Nodes (most connected - your core abstractions)
1. `Graph` - 20 edges
2. `build_master()` - 17 edges
3. `build_strip()` - 13 edges
4. `build_cable()` - 13 edges
5. `build_reel()` - 11 edges
6. `exercise_library()` - 11 edges
7. `main()` - 11 edges
8. `Rendering parametrico di strisce LED in Blender` - 11 edges
9. `build_path()` - 10 edges
10. `LedStudioStarter` - 9 edges

## Surprising Connections (you probably didn't know these)
- `build_master()` --calls--> `Graph`  [EXTRACTED]
  scripts/led_starter.py → scripts/led_starter.py  _Bridges community 1 → community 2_
- `build_reel()` --calls--> `Graph`  [EXTRACTED]
  scripts/led_starter.py → scripts/led_starter.py  _Bridges community 1 → community 9_
- `build_strip()` --calls--> `Graph`  [EXTRACTED]
  scripts/led_starter.py → scripts/led_starter.py  _Bridges community 1 → community 6_
- `exercise_library()` --calls--> `make_material()`  [EXTRACTED]
  scripts/led_starter.py → scripts/led_starter.py  _Bridges community 7 → community 3_
- `main()` --calls--> `build_path()`  [EXTRACTED]
  scripts/led_starter.py → scripts/led_starter.py  _Bridges community 1 → community 7_

## Import Cycles
- None detected.

## Communities (13 total, 6 thin omitted)

### Community 0 - "Rendering parametrico di strisce LED in Blender"
Cohesion: 0.12
Nodes (16): Bobina, Cinque indicazioni operative, Confronto tra le strade possibili, Dettaglio inferiore, Fonti tecniche, Idee generate, Interfaccia proposta, Obiettivo della sessione (+8 more)

### Community 1 - "Graph"
Cohesion: 0.38
Nodes (3): build_cable(), build_path(), Graph

### Community 3 - "exercise_library"
Cohesion: 0.25
Nodes (5): check_cable(), exercise_library(), load_panel(), make_box(), make_pcb_piece()

### Community 4 - "Graph Bootstrap Docs"
Cohesion: 0.29
Nodes (11): ensure-bootstrap.ps1, generate-readme.ps1, Git commit 402e0c6, graph.json, GRAPH_REPORT.md, graphify, Knowledge Graph, LedStudioStarter (+3 more)

### Community 5 - "led_starter.py"
Cohesion: 0.20
Nodes (3): look_at(), set_input(), setup_scene()

### Community 6 - "build_strip"
Cohesion: 0.29
Nodes (3): place(), build_strip(), curve_frame()

### Community 7 - "main"
Cohesion: 0.40
Nodes (4): main(), make_material(), mesh_report(), replace_text()

## Ambiguous Edges - Review These
- `Script JSX` → `Struttura cartelle`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **1 isolated node(s):** `Git commit 402e0c6`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 43 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_strip()` connect `build_strip` to `Graph`, `build_master`, `led_starter.py`, `main`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `build_master()` (e.g. with `.call()` and `.compare()`) actually correct?**
  _`build_master()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Git commit 402e0c6` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Rendering parametrico di strisce LED in Blender` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Why does `Graph` connect `Graph` to `build_reel`, `build_master`, `led_starter.py`, `build_strip`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `build_strip()` (e.g. with `.finish()` and `.link()`) actually correct?**
  _`build_strip()` has 6 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Script JSX` and `Struttura cartelle`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._