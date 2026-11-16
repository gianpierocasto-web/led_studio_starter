# LED Studio Starter (Blender 5.3+)

Generatore parametrico in Geometry Nodes per visualizzare e renderizzare strisce LED avvolte su bobina con cavo di alimentazione in continuità, caricando asset esterni dalle cartelle `bobine/`, `pcb/` e `cavi/`.

---

## Struttura minima di lavoro

```text
LED_Studio_Starter/
├── LED_Studio.blend               # File di lavoro principale (luce, camera, set)
├── aggiorna_nodi_led_studio.bat   # Aggiorna in-place i soli nodi geometrici senza toccare il set
├── scripts/led_starter.py         # Generatore e gestore nodi/pannello
├── bobine/                        # Un file .blend per modello di bobina
├── pcb/                           # Un file .blend per modulo striscia/PCB
└── cavi/                          # Un file .blend per cavo di alimentazione
```

- Il menu a tendina (**Bobina**, **PCB**, **Cavo**) eredita automaticamente il nome del file `.blend`.
- Puoi personalizzare liberamente camera, luci, fondale, World e impostazioni di render dentro `LED_Studio.blend`: l'importante è non rinominare il modificatore `Configurazione prodotto`, non cancellare il testo interno `LED Studio Libreria` e non lanciare lo script di generazione da zero sullo stesso file.
- Per aggiornare i nodi geometrici dopo un aggiornamento di `scripts/led_starter.py`, chiudi o salva il file e avvia con doppio clic `aggiorna_nodi_led_studio.bat`.

---

## Guida rapida d'uso

1. Apri `LED_Studio.blend` con **Blender 5.3+** (con *Auto Run Python Scripts* abilitato; in caso contrario premi Play una volta sul testo `LED Studio Libreria` nel Text Editor).
2. Seleziona l'oggetto generatore (`LED_02_Caldo_10mm` o equivalente) e vai nella scheda **Modifiers** → pannello **Libreria bobine, PCB e cavi**.
3. Scegli **Bobina**, **PCB** e **Cavo**.
4. Se modifichi e salvi un file esterno in `bobine/`, `pcb/` o `cavi/`, clicca **Ricarica asset** per ri-valutare subito la mesh senza riavviare Blender.
5. Regola i parametri sul modificatore `Configurazione prodotto`:
   - **`Altezza bobina`**: distanza interna fra i due dischi della bobina (determina automaticamente il numero di livelli interi della striscia).
   - **`Raggio mozzo`**: raggio di partenza della prima spira (impostarlo **maggiore** del colletto interno della bobina, es. `>= 0.033 m` su mozzo da `32 mm`).
   - **`Raggio avvolgimento`**: raggio massimo delle spire dentro la flangia.
   - **`Passo radiale`**: distanza radiale tra un giro e il successivo (viene comunque limitato automaticamente allo spessore `Y` reale del PCB per evitare compenetrazioni).
   - **`Giri uscita`** / **`Apertura uscita`**: lunghezza e apertura del tratto libero finale prima del cavo.
   - **`Passo deformazione cavo`**: densità longitudinale della guaina lungo `X` (default `0.001 m = 1 mm`).
   - **`Innesto cavo`**: di quanto il cappuccio/connettore iniziale del cavo scorre sopra l'estremità finale del PCB (calcolato in automatico all'importazione se presente una tasca con pin interni, modificabile a mano).

---

## Best practices per preparare gli asset senza errori

Tutti i numeri in Blender e negli slider sono in **metri** (`0.010 = 10 mm`).

### Regole comuni a tutti i `.blend` esterni

1. **Una sola scena pulita (o gli asset nella scena principale `Scene`)**
   - Non lasciare piani di sfondo (`Plane`, `Floor`, `Fondo`, `Backdrop`), sfere di test o oggetti di studio visibili nella scena: verrebbero importati e arrotolati insieme all'asset.
   - Se usi modificatori `Boolean`, tieni i cutter in una collection dedicata **esclusa dal View Layer** (`Exclude from View Layer`, icona casella di spunta spenta) oppure impostati come `Display As: Wire` e `Disable in Renders`: in questo modo il `Boolean` viene valutato correttamente ma il cutter non entra nella geometria finale.
   - Qualunque collection spenta (`Exclude` o *Hide in Viewport*) o oggetto nascosto al render viene ignorato all'importazione.
2. **Modificatori liberi, nessun bisogno di fare *Apply***
   - Puoi lasciare attivi `Subdivision Surface`, `Bevel`, `Array`, `Solidify`, `Mirror`, `Boolean` e `Smooth by Angle`: all'importazione lo script valuta lo stack completo nella vista reale e consolida l'asset in una mesh unica pronta per la piegatura.
3. **Materiali e texture**
   - I materiali devono essere già assegnati nei file sorgente.
   - Se usi texture immagine esterne (`Image Texture`), **impacchettale nel `.blend`** (*File → External Data → Pack Resources*) oppure tieni una cartella `textures/` relativa al file dell'asset, altrimenti in altri progetti le superfici risulteranno magenta.
4. **Orientamento standard degli assi**
   - **`X`**: direzione longitudinale della striscia e del cavo.
   - **`Y`**: spessore (**il lato `-Y` guarda verso l'esterno della bobina**, il lato `+Y` verso il mozzo).
   - **`Z`**: larghezza / altezza assiale della striscia (verticale rispetto alle flange della bobina).

---

### 1. Bobine (`bobine/*.blend`)

- Organizza le due metà in **due collection chiamate `up` e `down`** (anche maiuscole `UP` / `DOWN`).
- Dentro `up` e `down` puoi tenere qualsiasi numero di oggetti e con qualunque nome; evita soltanto oggetti di servizio non appartenenti alla bobina (Empty/Reference/luci di prova vanno fuori o nascosti).
- Origine al centro di simmetria (`X = 0, Y = 0`), asse di rotazione lungo **`Z`**.
- **Colletti interni / nervature**: lo script misura la quota di appoggio `Z` sul **disco esterno della flangia** (`R > 45%` del raggio massimo), così eventuali colletti o battute centrali possono estendersi verso l'interno senza falsare `Altezza bobina`.
- **Verifica rapida**: imposta `Raggio mozzo` superiore al raggio esterno del colletto della bobina e `Raggio avvolgimento` inferiore al raggio esterno delle flange.

---

### 2. Strisce LED / PCB (`pcb/*.blend`)

- Nessun vincolo sul nome delle collection o degli oggetti interni: puoi tenere separati guaina trasparente, adesivo, basetta PCB, fosfori, chip, resistenze e connettori.
- **Continuità tra moduli (`seamless`)**:
  - Le parti continue lungo tutta la lunghezza (basetta, guaina, adesivo, striscia fosfori) devono iniziare e terminare sulle **stesse due coordinate `X` esterne** del modulo e avere alle due estremità `X_min` e `X_max` **vertici di profilo corrispondenti in `(Y, Z)`**, senza tappi interni tra una copia e l'altra: in fase di assemblaggio `Merge by Distance` salda automaticamente *solo* i bordi ai due capi `X` di ogni modulo.
  - Le parti discrete (LED, resistenze, chip) non devono sporgere oltre `[X_min, X_max]`, altrimenti creano discontinuità nel passo di ripetizione.
- **Suddivisione longitudinale**: non è necessario suddividere manualmente in decine di tagli le parti lunghe (`Subdivision` o estrusioni semplici a 2 anelli vanno benissimo): lo script taglia automaticamente lungo `X` ogni `1 mm` tutte le isole lunghe prima di piegarle sulla spirale, preservando le isole piccole già dettagliate.
- **Centratura e spessore**: modella la sezione centrata su `Z = 0` e con il fronte luminoso rivolto verso **`-Y`**.

---

### 3. Cavi di alimentazione (`cavi/*.blend`)

- Nessun vincolo sul nome della collection o degli oggetti: puoi modellare cappuccio/sovrastampaggio, contatti interni, guaina, fili spellati e puntali come oggetti separati.
- **Verso lungo `X`**:
  - Lo standard consigliato è modellare il punto di attacco al PCB vicino a **`X = 0`** e sviluppare il cavo verso **`+X`** (con sezione in `Y, Z` e lato esterno rivolto a `-Y`).
  - Se un cavo è stato modellato all'inverso (attacco vicino a `X = 0` e sviluppo lungo **`-X`**), lo script rileva l'orientamento e lo ruota automaticamente di `180°` attorno a `Y` mantenendo `-Y` verso l'esterno.
- **Parti rigide (`led_role`)**:
  - Per default tutte le parti del cavo seguono la curva della spirale e vengono infittite lungo `X` se necessario.
  - Se un connettore o un cappuccio deve restare completamente **rigido** senza curvarsi, aggiungi su quell'oggetto la *Custom Property* **`led_role`** con valore stringa **`connector`** (*Object Properties → Custom Properties → New*).
- **Innesto sopra la fine del PCB**:
  - Se il cappuccio esterno parte davanti ai contatti/pin interni creando una tasca cava (es. cappuccio da `X = 0`, pin interni arretrati di `19,4 mm`), lo script calcola in automatico il parametro **`Innesto cavo`** facendo calzare il cappuccio sopra l'ultimo tratto di PCB. Puoi comunque rifinirlo a mano dallo slider `Innesto cavo` del modificatore.

---

## Checklist rapida se qualcosa si rompe in viewport

- **Vedi piani giganti o raggi che esplodono**: controlla che nel `.blend` dell'asset non ci sia una seconda scena (`Scene.001`) o un oggetto `Plane` / `Cylinder` di prova rimasto visibile.
- **Manca una modifica fatta su un file esterno**: salva il `.blend` sorgente e clicca **Ricarica asset** nel pannello del modificatore.
- **Le spire si compenetrano radialmente**: alza `Passo radiale` almeno quanto lo spessore `Y` della striscia (e `Raggio mozzo` oltre l'eventuale colletto della bobina).
- **Texture rosa/magenta in render**: impacchetta le texture dentro il `.blend` sorgente (*File → External Data → Pack Resources*) e clicca **Ricarica asset**.
- **Warning su file rinominati/spostati**: esegui `aggiorna_nodi_led_studio.bat` oppure clicca **Ricarica asset** per ripulire eventuali riferimenti a librerie non più esistenti.
