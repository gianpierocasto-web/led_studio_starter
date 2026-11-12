# Graph Report - LED_Studio_Starter  (2026-11-12)

## Corpus Check
- Corpus is ~4,787 words - fits in a single context window. You may not need a graph.

## Summary
- 123 nodes · 265 edges · 11 communities (6 shown, 5 thin omitted)
- Extraction: 66% EXTRACTED · 32% INFERRED · 1% AMBIGUOUS · INFERRED: 86 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Reference And Layout
- Product Presets
- Reel Geometry Builders
- Blender Scene Script
- Winding Risk Checks
- LED Reel Render
- Rigid Parts On Curve

## God Nodes (most connected - your core abstractions)
1. `Graph` - 16 edges
2. `Cinque indicazioni operative` - 16 edges
3. `build_reel()` - 14 edges
4. `build_strip()` - 12 edges
5. `SCAMPER` - 12 edges
6. `Spirale planare di avvolgimento` - 10 edges
7. `build_path()` - 9 edges
8. `Sistema quote in metri` - 9 edges
9. `Modello di bobina per famiglia` - 9 edges
10. `build_master()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Modificatore Configurazione prodotto` --semantically_similar_to--> `Pannello di preset e controlli`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Append Prodotto | 02_Caldo_10mm` --conceptually_related_to--> `02 PCB e componenti su curva`  [AMBIGUOUS]
  VERIFICA.txt → LEGGIMI.txt
- `Sistema quote in metri` --semantically_similar_to--> `Disambiguazione dell'altezza`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Gioco flange` --semantically_similar_to--> `Spazio fra flange legato alla larghezza`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md
- `Passo radiale` --semantically_similar_to--> `Passo radiale legato allo spessore`  [INFERRED] [semantically similar]
  LEGGIMI.txt → brainstorming-report.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Gruppi del generatore LED** — leggimi_gruppo_00_prodotto_completo, leggimi_gruppo_01_percorso_spirale, leggimi_gruppo_02_pcb, leggimi_gruppo_03_bobina [EXTRACTED 1.00]
- **Confronto delle strade di generazione** — brainstorming_report_strada_sostituzioni_manuali, brainstorming_report_strada_array_curve_modifier, brainstorming_report_strada_geometry_nodes, brainstorming_report_strada_gn_addon_python, brainstorming_report_strada_foto_nastro [EXTRACTED 1.00]
- **Componenti della soluzione raccomandata** — brainstorming_report_idea_scena_master, brainstorming_report_idea_due_viste, brainstorming_report_idea_libreria_bobine, brainstorming_report_idea_modulo_pcb, brainstorming_report_idea_generazione_curve, brainstorming_report_strada_geometry_nodes [EXTRACTED 1.00]
- **LED Strip Wound on Supply Reel** — preview_supply_reel, preview_reel_frame, preview_led_strip, preview_strip_tail, preview_smd_leds [EXTRACTED 1.00]

## Communities (11 total, 5 thin omitted)

### Community 0 - "Reference And Layout"
Cohesion: 0.10
Nodes (18): BMAD Quick Flow, Blender Manual Command Line, Blender Manual Curve Spiral, Blender Manual Curve to Mesh, Blender Manual Curve to Points, Fonti tecniche, Immagine di riferimento della composizione, Incognite di contesto (+10 more)

### Community 1 - "Product Presets"
Cohesion: 0.15
Nodes (16): Append collezione Prodotto, Blocchi package, fosforo, resistenza e contatti, Modificatore Configurazione prodotto, Gioco flange, 00 Prodotto completo, 03 Bobina parametrica, led_starter.py, Passo radiale (+8 more)

### Community 2 - "Reel Geometry Builders"
Cohesion: 0.46
Nodes (5): build_master(), build_path(), build_reel(), build_strip(), Graph

### Community 3 - "Blender Scene Script"
Cohesion: 0.23
Nodes (5): look_at(), main(), make_material(), set_input(), setup_scene()

### Community 6 - "LED Reel Render"
Cohesion: 0.32
Nodes (7): Dark SMD Marks on Strip, Coiled White LED Strip, LED Strip Reel Product Render, Flanged Six-Spoke Plastic Reel, SMD LED Emitters, Exposed LED Strip Tail, LED Strip Supply Reel

### Community 8 - "Rigid Parts On Curve"
Cohesion: 0.67
Nodes (3): Componenti rigidi su supporto flessibile, Blender Manual Instance on Points, Componenti rigidi realizzati

## Ambiguous Edges - Review These
- `02 PCB e componenti su curva` → `Append Prodotto | 02_Caldo_10mm`  [AMBIGUOUS]
  VERIFICA.txt · relation: conceptually_related_to
- `led_starter.py` → `Geometry Nodes con add-on Python`  [AMBIGUOUS]
  LEGGIMI.txt · relation: conceptually_related_to
- `SMD LED Emitters` → `Dark SMD Marks on Strip`  [AMBIGUOUS]
  preview.png · relation: conceptually_related_to

## Knowledge Gaps
- **3 isolated node(s):** `Render Cycles del preset 10 mm`, `BMAD Quick Flow`, `Flanged Six-Spoke Plastic Reel`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 19 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Cinque indicazioni operative` connect `Asset Library Ideas` to `Reference And Layout`, `Winding Risk Checks`, `Geometry Nodes Choice`, `Locked Master Scene`, `Photo On Tape`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `build_reel()` (e.g. with `.cube()` and `.finish()`) actually correct?**
  _`build_reel()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Render Cycles del preset 10 mm`, `BMAD Quick Flow`, `Flanged Six-Spoke Plastic Reel` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Reference And Layout` be split into smaller, more focused modules?**
  _Cohesion score 0.0960591133004926 - nodes in this community are weakly interconnected._
- **Why does `Spirale planare di avvolgimento` connect `Reference And Layout` to `Winding Risk Checks`, `Geometry Nodes Choice`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `02 PCB e componenti su curva` and `Append Prodotto | 02_Caldo_10mm`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `led_starter.py` and `Geometry Nodes con add-on Python`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._