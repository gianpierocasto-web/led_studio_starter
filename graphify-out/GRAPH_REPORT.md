# Graph Report - LED_Studio_Starter  (2026-11-12)

## Corpus Check
- 1 files · ~4,899 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 135 nodes · 284 edges · 7 communities
- Extraction: 68% EXTRACTED · 31% INFERRED · 1% AMBIGUOUS · INFERRED: 87 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Catalog Design Ideas
- Blender Builder Script
- Sources And Layout
- Product Controls
- Graph Bootstrap Docs
- Reel Dimensions
- LED Reel Render

## God Nodes (most connected - your core abstractions)
1. `Graph` - 16 edges
2. `Cinque indicazioni operative` - 16 edges
3. `build_reel()` - 14 edges
4. `build_strip()` - 12 edges
5. `SCAMPER` - 12 edges
6. `Spirale planare di avvolgimento` - 10 edges
7. `build_path()` - 9 edges
8. `Modello di bobina per famiglia` - 9 edges
9. `Sistema quote in metri` - 9 edges
10. `LedStudioStarter` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Append Prodotto | 02_Caldo_10mm` --conceptually_related_to--> `02 PCB e componenti su curva`  [AMBIGUOUS]
  VERIFICA.txt → LEGGIMI.txt
- `Sistema quote in metri` --semantically_similar_to--> `Disambiguazione dell'altezza`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Arrotondamento dei giri interni` --semantically_similar_to--> `Campionamento del passo commerciale`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Gruppi condivisi fra le scene` --semantically_similar_to--> `Preset PCB condiviso fra le viste`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Sistema quote in metri` --semantically_similar_to--> `Modalità di avvolgimento`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Confronto delle strade di generazione** — brainstorming_report_strada_sostituzioni_manuali, brainstorming_report_strada_array_curve_modifier, brainstorming_report_strada_geometry_nodes, brainstorming_report_strada_gn_addon_python, brainstorming_report_strada_foto_nastro [EXTRACTED 1.00]
- **Componenti della soluzione raccomandata** — brainstorming_report_idea_scena_master, brainstorming_report_idea_due_viste, brainstorming_report_idea_libreria_bobine, brainstorming_report_idea_modulo_pcb, brainstorming_report_idea_generazione_curve, brainstorming_report_strada_geometry_nodes [EXTRACTED 1.00]
- **Gruppi del generatore LED** — leggimi_gruppo_00_prodotto_completo, leggimi_gruppo_01_percorso_spirale, leggimi_gruppo_02_pcb, leggimi_gruppo_03_bobina [EXTRACTED 1.00]
- **LED Strip Wound on Supply Reel** — preview_supply_reel, preview_reel_frame, preview_led_strip, preview_strip_tail, preview_smd_leds [EXTRACTED 1.00]

## Communities (7 total, 0 thin omitted)

### Community 0 - "Catalog Design Ideas"
Cohesion: 0.10
Nodes (7): Blender Manual Command Line, Componenti rigidi su supporto flessibile, Blender Manual Instance on Points, Blocchi package, fosforo, resistenza e contatti, 02 PCB e componenti su curva, Passo radiale, Componenti rigidi realizzati

### Community 1 - "Blender Builder Script"
Cohesion: 0.21
Nodes (10): build_master(), build_path(), build_reel(), build_strip(), Graph, look_at(), main(), make_material() (+2 more)

### Community 2 - "Sources And Layout"
Cohesion: 0.11
Nodes (15): BMAD Quick Flow, Blender Manual Curve Spiral, Blender Manual Curve to Mesh, Blender Manual Curve to Points, Fonti tecniche, Immagine di riferimento della composizione, Incognite di contesto, Catalogo a composizione costante (+7 more)

### Community 3 - "Product Controls"
Cohesion: 0.18
Nodes (11): Append collezione Prodotto, Modificatore Configurazione prodotto, 00 Prodotto completo, led_starter.py, Preset scena 10 mm, Preset scena 8 mm, Preset scena RGB 12 mm, Append Prodotto | 02_Caldo_10mm (+3 more)

### Community 4 - "Graph Bootstrap Docs"
Cohesion: 0.29
Nodes (11): ensure-bootstrap.ps1, generate-readme.ps1, Git commit 402e0c6, graph.json, GRAPH_REPORT.md, graphify, Knowledge Graph, LedStudioStarter (+3 more)

### Community 5 - "Reel Dimensions"
Cohesion: 0.31
Nodes (5): Modello di bobina per famiglia, Gioco flange, 03 Bobina parametrica, Giri uscita e Apertura uscita, Variazione larghezza PCB +4 mm

### Community 6 - "LED Reel Render"
Cohesion: 0.32
Nodes (7): Dark SMD Marks on Strip, Coiled White LED Strip, LED Strip Reel Product Render, Flanged Six-Spoke Plastic Reel, SMD LED Emitters, Exposed LED Strip Tail, LED Strip Supply Reel

## Ambiguous Edges - Review These
- `02 PCB e componenti su curva` → `Append Prodotto | 02_Caldo_10mm`  [AMBIGUOUS]
  VERIFICA.txt · relation: conceptually_related_to
- `led_starter.py` → `Geometry Nodes con add-on Python`  [AMBIGUOUS]
  LEGGIMI.txt · relation: conceptually_related_to
- `Dark SMD Marks on Strip` → `SMD LED Emitters`  [AMBIGUOUS]
  preview.png · relation: conceptually_related_to
- `Script JSX` → `Struttura cartelle`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **4 isolated node(s):** `BMAD Quick Flow`, `Render Cycles del preset 10 mm`, `Flanged Six-Spoke Plastic Reel`, `Git commit 402e0c6`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 20 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Cinque indicazioni operative` connect `Catalog Design Ideas` to `Sources And Layout`, `Product Controls`, `Reel Dimensions`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `build_reel()` (e.g. with `.cube()` and `.finish()`) actually correct?**
  _`build_reel()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `BMAD Quick Flow`, `Render Cycles del preset 10 mm`, `Flanged Six-Spoke Plastic Reel` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Catalog Design Ideas` be split into smaller, more focused modules?**
  _Cohesion score 0.1010752688172043 - nodes in this community are weakly interconnected._
- **Why does `Spirale planare di avvolgimento` connect `Sources And Layout` to `Catalog Design Ideas`, `Reel Dimensions`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `02 PCB e componenti su curva` and `Append Prodotto | 02_Caldo_10mm`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `led_starter.py` and `Geometry Nodes con add-on Python`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._