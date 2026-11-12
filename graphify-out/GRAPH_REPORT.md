# Graph Report - LED_Studio_Starter  (2026-11-12)

## Corpus Check
- 4 files · ~27,242 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .mdc 1, .blend 1)

## Summary
- 153 nodes · 316 edges · 7 communities (6 shown, 1 thin omitted)
- Extraction: 71% EXTRACTED · 28% INFERRED · 1% AMBIGUOUS · INFERRED: 89 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c5118d75`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Catalog Design Ideas
- Blender Builder Script
- Spirale planare di avvolgimento
- Product Controls
- Graph Bootstrap Docs
- led_starter.py
- LED Reel Render

## God Nodes (most connected - your core abstractions)
1. `Graph` - 18 edges
2. `Cinque indicazioni operative` - 16 edges
3. `build_master()` - 15 edges
4. `build_strip()` - 13 edges
5. `SCAMPER` - 12 edges
6. `build_reel()` - 11 edges
7. `build_path()` - 10 edges
8. `exercise_library()` - 10 edges
9. `main()` - 10 edges
10. `Spirale planare di avvolgimento` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Append Prodotto | 02_Caldo_10mm` --conceptually_related_to--> `02 PCB e componenti su curva`  [AMBIGUOUS]
  VERIFICA.txt → LEGGIMI.txt
- `Sistema quote in metri` --semantically_similar_to--> `Disambiguazione dell'altezza`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Gioco flange` --semantically_similar_to--> `Spazio fra flange legato alla larghezza`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Variazione larghezza PCB +4 mm` --semantically_similar_to--> `Spazio fra flange legato alla larghezza`  [INFERRED] [semantically similar]
  VERIFICA.txt → brainstorming-report.md
- `Modificatore Configurazione prodotto` --semantically_similar_to--> `Pannello di preset e controlli`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Confronto delle strade di generazione** — brainstorming_report_strada_sostituzioni_manuali, brainstorming_report_strada_array_curve_modifier, brainstorming_report_strada_geometry_nodes, brainstorming_report_strada_gn_addon_python, brainstorming_report_strada_foto_nastro [EXTRACTED 1.00]
- **Componenti della soluzione raccomandata** — brainstorming_report_idea_scena_master, brainstorming_report_idea_due_viste, brainstorming_report_idea_libreria_bobine, brainstorming_report_idea_modulo_pcb, brainstorming_report_idea_generazione_curve, brainstorming_report_strada_geometry_nodes [EXTRACTED 1.00]
- **Gruppi del generatore LED** — leggimi_gruppo_00_prodotto_completo, leggimi_gruppo_01_percorso_spirale, leggimi_gruppo_02_pcb, leggimi_gruppo_03_bobina [EXTRACTED 1.00]
- **LED Strip Wound on Supply Reel** — preview_supply_reel, preview_reel_frame, preview_led_strip, preview_strip_tail, preview_smd_leds [EXTRACTED 1.00]

## Communities (7 total, 1 thin omitted)

### Community 1 - "Blender Builder Script"
Cohesion: 0.28
Nodes (5): build_master(), build_path(), build_reel(), build_strip(), Graph

### Community 2 - "Spirale planare di avvolgimento"
Cohesion: 0.09
Nodes (19): BMAD Quick Flow, Blender Manual Command Line, Componenti rigidi su supporto flessibile, Blender Manual Curve Spiral, Blender Manual Curve to Mesh, Blender Manual Curve to Points, Fonti tecniche, Immagine di riferimento della composizione (+11 more)

### Community 3 - "Product Controls"
Cohesion: 0.13
Nodes (16): Append collezione Prodotto, Blocchi package, fosforo, resistenza e contatti, Modificatore Configurazione prodotto, Gioco flange, 00 Prodotto completo, 03 Bobina parametrica, Passo radiale, Preset scena 10 mm (+8 more)

### Community 4 - "Graph Bootstrap Docs"
Cohesion: 0.29
Nodes (11): ensure-bootstrap.ps1, generate-readme.ps1, Git commit 402e0c6, graph.json, GRAPH_REPORT.md, graphify, Knowledge Graph, LedStudioStarter (+3 more)

### Community 5 - "led_starter.py"
Cohesion: 0.13
Nodes (12): exercise_library(), instance_points(), load_panel(), look_at(), main(), make_box(), make_material(), make_pcb_piece() (+4 more)

### Community 6 - "LED Reel Render"
Cohesion: 0.32
Nodes (7): Dark SMD Marks on Strip, Coiled White LED Strip, LED Strip Reel Product Render, Flanged Six-Spoke Plastic Reel, SMD LED Emitters, Exposed LED Strip Tail, LED Strip Supply Reel

## Ambiguous Edges - Review These
- `led_starter.py` → `Geometry Nodes con add-on Python`  [AMBIGUOUS]
  LEGGIMI.txt · relation: conceptually_related_to
- `02 PCB e componenti su curva` → `Append Prodotto | 02_Caldo_10mm`  [AMBIGUOUS]
  VERIFICA.txt · relation: conceptually_related_to
- `Script JSX` → `Struttura cartelle`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to
- `Dark SMD Marks on Strip` → `SMD LED Emitters`  [AMBIGUOUS]
  preview.png · relation: conceptually_related_to

## Knowledge Gaps
- **4 isolated node(s):** `BMAD Quick Flow`, `Render Cycles del preset 10 mm`, `Git commit 402e0c6`, `Flanged Six-Spoke Plastic Reel`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 30 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Geometry Nodes con add-on Python` connect `Catalog Design Ideas` to `led_starter.py`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `build_master()` (e.g. with `.call()` and `.compare()`) actually correct?**
  _`build_master()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `BMAD Quick Flow`, `Render Cycles del preset 10 mm`, `Git commit 402e0c6` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Catalog Design Ideas` be split into smaller, more focused modules?**
  _Cohesion score 0.11596638655462185 - nodes in this community are weakly interconnected._
- **Why does `Pannello di preset e controlli` connect `Catalog Design Ideas` to `Product Controls`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `led_starter.py` and `Geometry Nodes con add-on Python`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `02 PCB e componenti su curva` and `Append Prodotto | 02_Caldo_10mm`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._