# coral-python — Panoramica

Una guida a cosa sia questo progetto, perché esista, com'è costruito e come estenderlo — per due
tipi di pubblico: chi vuole **aggiungere una libreria CFD/scientifica** e chi vuole **migliorarne il
design interno o il suo contratto con la piattaforma DealiiX**.

Questo documento completa `README.md` (setup + comandi quotidiani) e `CLAUDE.md` (riferimento sui
meccanismi per lo sviluppo assistito da AI). Questo è la *storia*: obiettivi, architettura, motivazioni e un
resoconto onesto di punti di forza e di debolezza.

*Ultimo aggiornamento: 2026-07-21. Descrive coral-python allo stadio di **MVP locale** — un backend
coral-compatibile che esegue i grafi end-to-end in locale — ora ristrutturato come un **monorepo di plugin**
(un contratto `coral-core`, un host `coral-app` e un `coral-plugin-*` per ogni capacità, scoperti tramite
entry point). Vedi [Roadmap / lavori rinviati](#roadmap--lavori-rinviati) per cosa è ancora fuori dallo scope
(esecuzione remota/Slurm, stadi di pipeline).*

## Indice

- [Obiettivi e contesto](#obiettivi-e-contesto)
- [Architettura](#architettura)
- [Installazione](#installazione)
- [Uso](#uso)
- [Aggiungere una nuova libreria](#aggiungere-una-nuova-libreria-persona-a)
- [Estendere gli interni o i contratti](#estendere-gli-interni-o-i-contratti-persona-b)
- [Motivazioni di design / FAQ](#motivazioni-di-design--faq)
- [Punti di forza e di debolezza](#punti-di-forza-e-di-debolezza)
- [Roadmap / lavori rinviati](#roadmap--lavori-rinviati)

---

## Obiettivi e contesto

**La piattaforma DealiiX** è un editor visuale a nodi: gli utenti costruiscono un grafo di chiamate a
funzioni, costruttori di classi e chiamate a metodi, poi lo esportano come JSON e lo eseguono su un backend.
Il backend originale è **CORAL**, un motore C++ costruito su deal.II per simulazioni agli elementi finiti.

**coral-python esiste come caso di prova per la cross-validazione.** Se l'approccio della piattaforma — un
editor visuale a nodi che parla con un backend puramente attraverso un protocollo JSON — è solido, dovrebbe
funzionare anche con un *secondo motore indipendente* costruito con strumenti diversi per un dominio diverso
(Python + [PhiFlow](https://github.com/tum-pbs/PhiFlow) per la simulazione di fluidi, invece di C++ + deal.II
per gli elementi finiti). coral-python è quel secondo motore.

Per rendere il confronto significativo, coral-python non inventa un proprio protocollo — è
**coral-compatibile**: parla la *stessa* superficie CLI e lo *stesso* schema JSON del binario CORAL in C++.
Dal punto di vista della piattaforma, passare dal backend C++ a coral-python significa cambiare due
impostazioni (il percorso dell'eseguibile e il valore del "plugin") e nient'altro. Vedi
[Architettura](#architettura) per sapere esattamente qual è quel contratto.

---

## Architettura

### Un monorepo di plugin: core, host, plugin

Il codice vive in pacchetti sotto `packages/*`, con una regola di dipendenza rigorosamente unidirezionale:
**core → nulla di interno; app → core; ogni plugin → core; l'host non importa mai un plugin.**

```
                   ┌──────────────────────────────┐
                   │  coral-core                  │   the contract only: a Plugin
                   │  Plugin (ABC):               │   ABC with two @abstractmethods.
                   │    get_functions()           │   Depends on nothing internal.
                   │    get_classes()             │
                   └───────────────▲──────────────┘
                                   │ subclass
        ┌────────────────────────────────────────────────────┐
        │  coral-plugin-math    -> MathPlugin                │   each declares itself under the
        │  coral-plugin-string  -> StringPlugin              │   entry-point group "coral.plugins",
        │  coral-plugin-phiflow -> PhiFlowPlugin             │   pointing at its Plugin class
        └──────────────────────────▲─────────────────────────┘
                                   │ discover() / load(name) — lazy: list without importing;
                                   │                           import only the requested plugin
        ┌──────────────────────────▲─────────────────────────┐
        │  coral-app  (the host)                             │
        │    discover / load / load_all                      │
        │    build_function_map() / build_class_map()        │
        │    PRIMITIVES_MAP                                  │
        └───────────────┬─────────────────────┬──────────────┘
                        │                     │
              ┌───────────────────┐ ┌───────────────────┐
              │  registry.py      │ │  executor.py      │
              │  describes nodes  │ │  runs nodes       │
              └─────────┬─────────┘ └─────────┬─────────┘
                        ▼                     ▼
                 node_types.json        graph results
```

**La scoperta è pigra e passa dai metadati standard.** I plugin si dichiarano sotto il gruppo di entry point
`coral.plugins` di `importlib.metadata`, puntando alla loro **classe** `Plugin`. Il `discover()` dell'host
elenca i nomi dei plugin installati *senza importarne nessuno*; `load(name)` importa **solo** quel singolo
plugin, verifica che sia sottoclasse di `Plugin` (`TypeError` altrimenti) e lo istanzia. Un nome sconosciuto →
`LookupError`. È questo che permette a un plugin sconosciuto quando l'host è stato costruito — incluso uno di
terze parti — di essere trovato e caricato puramente dai suoi metadati installati.

**Il contratto è una ABC imposta, non una convenzione.** La `Plugin` di `coral-core` usa `@abstractmethod`,
quindi un plugin che dimentica `get_functions()` o `get_classes()` non può nemmeno essere istanziato. Non c'è
un metodo `name` — il nome dell'entry point (`math` / `string` / `phiflow`) *è* l'identità del plugin, ed è la
stringa che il contratto `-p` della piattaforma passa.

Dentro l'host, `registry.py` ed `executor.py` **non si importano a vicenda.** Entrambi importano solo da
`coral_app` (`from coral_app import PRIMITIVES_MAP, build_function_map, build_class_map` — riga identica in
entrambi i file). Questo è voluto: il compito del registry è *descrivere* cosa è chiamabile; il compito
dell'executor è *eseguirlo*. Vedi [Estendere gli interni](#estendere-gli-interni-o-i-contratti-persona-b) per
capire perché questo disaccoppiamento conta.

### I due contratti

Tutto ciò che la piattaforma ha bisogno da coral-python si riduce a due contratti:

**1. Il contratto CLI.** `coral` (il console script di `coral-app`) espone la stessa superficie del binario
`coral` in C++:

```
coral -p <plugins> register [--output FILE]              # write the node registry
coral -p <plugins> run <graph.json> [--touch-dir DIR]    # execute a graph
```

`-p`/`--plugin` è riutilizzato: per coral in C++ è il percorso a un plugin compilato (`.so`); per coral-python
è una **lista separata da virgole di nomi di plugin da caricare** (es. `"math,string"`; vuoto significa
"carica ogni plugin installato" — vedi `_resolve_modules` in `coral_app/cli.py`, che risolve il vuoto a
`discover()`). Questa è l'*unica* differenza semantica di cui la piattaforma deve essere a conoscenza, ed è
solo una stringa che essa già passa in modo opaco. Lo script di avvio `coral-py` incapsula il console script
così che la piattaforma possa puntare l'impostazione `coralBinaryPath` direttamente a esso (vedi `README.md`
per l'invocazione esatta).

**2. Il contratto JSON.** Due forme JSON:

- **Registry** (`node_types.json`, prodotto da `register`) — un dizionario indicizzato per la stringa `type`
  di ciascun nodo, una voce per ogni primitivo/funzione/costruttore/metodo. È generato da
  `coral_app/registry.py:generate_registry()`.
- **Grafo** (consumato da `run`) — `{"workflow": {"nodes": {...}, "edges": {...}}, ...}`, dove ogni nodo è
  *snello* (lean): solo `{"type": "...", "value": ...}` (primitivi) o `{"type": "..."}` (tutto il resto).
  Niente `node_type`, niente `method_name` — l'executor deduce cosa **sia** un nodo puramente dalla sua
  stringa `type` (vedi `coral_app/executor.py:_classify`). Questo combacia esattamente con ciò che la
  piattaforma esporta.

### Il flusso dei dati in pratica

```
1. Probe:    la piattaforma esegue `coral-py -p "math,string" register`
             → l'host scopre i plugin, carica math + string (solo quelli),
               registry.py introspeziona i loro get_functions()/get_classes()
             → scrive node_types.json
             → la piattaforma lo legge e popola la barra laterale

2. Build:    l'utente trascina i nodi sul canvas, li collega,
             la piattaforma esporta un graph.json snello

3. Run:      la piattaforma esegue `coral-py -p "math,string" run graph.json`
             → executor.py carica graph.json, classifica ogni nodo per `type`,
               fa l'ordinamento topologico e chiama le vere funzioni/classi Python
             → i risultati sono stampati su stdout (catturati come log dell'esecuzione)
```

### Come il registry legge le firme — `inspect.signature`, e se convenga tenerlo

Il registry è interamente **guidato dalle annotazioni**, e il meccanismo che legge quelle annotazioni è
`inspect.signature` della libreria standard. Vale la pena capirlo con precisione, perché è il singolo fatto
che spiega perché la maggior parte delle librerie ha bisogno di un wrapper.

**Come funziona.** `registry.py` chiama `inspect.signature(...)` su ogni callable — una funzione
(`_add_function_node`), un costruttore (`_add_constructor`, su `cls.__init__`) o un metodo (`_add_methods`).
Poi scorre `sig.parameters` (ordinati, ognuno con la sua `.annotation`) più `sig.return_annotation`, e passa
ogni annotazione attraverso `python_type_to_string`, che la mappa contro il `PRIMITIVES_MAP` di sei voci
(`int`, `float`, `str`, `bool`, `any`, `none`). Da questo derivano due comportamenti:

- Un'annotazione di **parametro mancante** diventa `"any"` — usabile, solo debolmente tipizzata.
- Un'annotazione di **ritorno mancante** non produce **alcun socket di output** (`_process_return_type`
  restituisce `[], []`), quindi il nodo diventa un vicolo cieco. Un ritorno `Tuple[...]`, al contrario,
  diventa un socket di output per elemento.

`executor.py` chiama `inspect.signature` in modo indipendente (quando collega un nodo funzione, costruttore o
metodo) — i due file non condividono mai un helper per le firme, ed è la giuntura "convenzione, non contratto"
descritta in [Estendere gli interni](#estendere-gli-interni-o-i-contratti-persona-b).

**Perché è stato scelto.** È nella libreria standard (zero dipendenze), e una singola chiamata restituisce
parametri ordinati, default e annotazione di ritorno in una forma uniforme tra funzioni, metodi e costruttori.
Per un registry guidato dalle annotazioni è la cosa minima che funziona, ed è del tutto sufficiente per il
codice che possediamo noi — i nostri wrapper tipizzati e le classi Python pure e annotate come `Calculator` si
registrano senza alcun adattatore.

**Il suo limite onesto.** `inspect.signature` legge solo le annotazioni *grezze* che esistono sull'oggetto a
runtime. È un confine netto in due direzioni, ed entrambe sono comuni:

- **Il codice implementato in C non porta annotazioni a runtime.** Tutto in `math`, gran parte di `numpy` e i
  percorsi veloci delle librerie scientifiche si introspezionano con parametri *vuoti* e ritorno *vuoto* —
  quindi si registrerebbero con input `"any"` e nessun output.
- **Le librerie Python pure moderne trasformano le annotazioni in stringhe.** Con
  `from __future__ import annotations` (PEP 563), `inspect.signature` restituisce la *stringa* `"float"`
  invece del tipo `float`, e il controllo di identità di `python_type_to_string` contro `PRIMITIVES_MAP`
  la manca → `"any"`.

Abbiamo misurato quanto dell'ecosistema reale questo esclude, e la risposta fa riflettere: su **751 callable
pubblici** in `numpy` (461), `jax` (98) e `phi.flow` (192), **zero** sono direttamente registrabili in un nodo
pulito e collegabile — `numpy` perché è C (nessuna annotazione), `jax` perché usa PEP 563 (77 dei suoi
callable annotati tornano come stringhe), `phi.flow` perché i suoi tipi non sono primitivi. Scansionando ogni
modulo di terze parti di livello superiore installato qui, solo tre esponevano *qualche* callable usabile
nativamente, ed erano helper incidentali (`pyparsing.col`, `opt_einsum.get_symbol`, `iniconfig.iscommentline`).
**La conclusione pratica: i wrapper scritti a mano e annotati coi tipi sono la regola, non un caso limite** —
vedi [perché `math.sqrt` ha bisogno di un wrapper](#perché-mathsqrt-ha-bisogno-di-un-wrapper-non-possiamo-caricare-le-funzioni-python-dinamicamente).

**Le alternative, e la nostra opinione su ciascuna.**

- **`typing.get_type_hints()`** — risolve le annotazioni-stringa PEP 563 e i riferimenti in avanti che
  `inspect.signature` grezzo lascia come stringhe. È un cambiamento economico e a basso rischio che
  sbloccherebbe l'intera classe delle librerie Python pure e moderne annotate (renderebbe, per esempio,
  leggibili le firme trasformate in stringhe di `jax`). *La nostra opinione: il primo miglioramento che vale la
  pena fare.* Non risolve il codice C (non ci sono comunque annotazioni da risolvere) ed è ancora limitato
  alla mappa di sei primitivi, ma elimina il fallimento evitabile più comune.
- **Parsing statico dell'AST dei file sorgente** — estrae le firme senza importare, evitando gli effetti
  collaterali dell'import. Macchinario più pesante, e ancora dipendente dalle annotazioni (legge gli stessi
  hint). *Non ne vale la pena a questa scala.*
- **Registrazione esplicita con decoratori / schema manuale** — precisa e senza introspezione, ma baratta ogni
  firma con boilerplate scritto a mano. *Vale la pena solo se dobbiamo deliberatamente registrare molti
  callable non annotabili.*
- **Lettura degli stub `.pyi`** — l'*unica* via che potrebbe recuperare i tipi per le funzioni C (`numpy` ecc.),
  dato che quell'informazione vive solo negli stub. Ma è ad alta complessità e fragile (scoperta degli stub,
  disallineamenti di versione). *Probabilmente non ne vale la pena; un wrapper scritto a mano è più semplice e
  più onesto sulle intenzioni.*

**In conclusione.** Teniamo `inspect.signature` per ora — è semplice e pienamente sufficiente per il codice che
possediamo. Se in futuro vorremo che più librerie esterne "funzionino e basta", il percorso pragmatico è
`get_type_hints()` più una mappa di tipi più ricca, in quest'ordine. Ma i wrapper restano inevitabili per le
librerie C e di array qualunque lettore scegliamo: è una proprietà dell'ecosistema Python (nessun tipo a
runtime per il codice compilato), non un difetto di questo design.

### Come l'executor esegue un grafo — ordine di esecuzione e `_classify`

Due meccanismi in `executor.py` trasformano un grafo snello in risultati.

**Ordine di esecuzione.** `get_execution_order()` è un ordinamento topologico (algoritmo di Kahn): costruisce
una lista di adiacenza più un conteggio dei gradi entranti a partire dagli archi, inizializza una coda con ogni
nodo a grado entrante zero, e la svuota decrementando man mano i gradi entranti a valle. Se l'ordine emesso è
più corto del numero di nodi c'è un ciclo, e solleva un errore. La garanzia che questo compra: un nodo gira
solo dopo che esistono tutti i suoi input, mentre i rami indipendenti non hanno un ordine relativo definito
(qualsiasi ordine topologico valido va bene).

**Classificazione dei nodi.** Poiché i nodi snelli portano solo `{type, value?}`, l'executor deve recuperare
cosa sia ciascun nodo prima di poterlo eseguire. `_classify(type_str)` fa esattamente questo, ed è
deliberatamente economico — poche verifiche di appartenenza a hash-map costruite **una sola volta** in
`__init__`, quindi è di fatto **O(1) per nodo** e mai un collo di bottiglia:

```python
if type_str in self.primitives_map: return "primitive"    # O(1)
if type_str in self.function_map:   return "function"      # O(1)
if type_str in self.class_map:      return "constructor"   # O(1)
if "." in type_str and type_str.rsplit(".", 1)[0] in self.class_map:
    return "method"                                        # one split + O(1)
```

Due cose su cui vale la pena essere precisi:

- `_classify` recupera solo il *tipo* (kind) del nodo, non la forma dei suoi argomenti. I nomi e l'ordine dei
  parametri sono ri-derivati al momento della chiamata con `inspect.signature(func | __init__ | method)` — lo
  stesso lettore che usa il registry — e gli input vengono poi collegati come kwargs. Quella chiamata a
  `inspect.signature` per nodo è economica ma non memorizzata in cache.
- Le uniche parti lievemente non lineari vivono altrove, e nessuna conta alle dimensioni di grafo odierne:
  l'ordinamento topologico usa una lista come coda (`queue.pop(0)` è O(n)), e ogni nodo riscansiona l'intera
  lista di archi per trovare i suoi archi entranti (`[e for e in self.edges if e["target"] == node_id]`,
  O(V·E) complessivo). Sostituire con un `collections.deque` e pre-raggruppare gli archi per target renderebbe
  lineare un'intera esecuzione — una vittoria pulita e a basso rischio per la
  [Persona B](#estendere-gli-interni-o-i-contratti-persona-b) se i grafi dovessero mai crescere molto.

---

## Installazione

coral-python è un [**workspace** uv](https://docs.astral.sh/uv/concepts/projects/workspaces/) — un monorepo
di pacchetti sotto `packages/*`, collegati insieme da un `pyproject.toml` + `uv.lock` radice virtuale:

```bash
uv sync          # creates .venv, installs every workspace package editable (incl. the dev group)
```

Poi attiva il venv (`source .venv/bin/activate`) oppure prefissa i comandi con `uv run`. Vedi `README.md` per
la sezione completa di setup, la gestione delle dipendenze (`uv add --package …`) e l'esecuzione della suite
di test.

---

## Uso

```bash
# Generate the registry for one or more plugins (writes node_types.json in the cwd)
uv run coral -p "math" register

# Run a graph with those plugins loaded
uv run coral -p "math" run tests/fixtures/valid_workflows/network-from-fe-math.json
```

Tramite il launcher (ciò che la piattaforma invoca davvero):

```bash
./coral-py -p "math,string,phiflow" register
./coral-py -p "math,string,phiflow" run graph.json
```

`coral-py` esegue il console script `coral` dentro il `.venv` di questo workspace tramite `uv run --project`,
**senza cambiare la cartella di lavoro** — così l'output di `register` e la cartella di lavoro configurata
dalla piattaforma restano coerenti con ciò che la piattaforma si aspetta (vedi i commenti in `coral-py`).

Sul lato piattaforma: Impostazioni → Modalità di esecuzione → **Local / Coral**, con il *Coral binary path*
puntato su `coral-py` e il campo *Coral plugin path* che contiene la lista dei moduli (quel campo accetta testo
libero proprio per supportare questo — vedi dealiiX-platform PR #209). Poi **Save & Sync** interroga il
registry, ed **Execute** esegue un grafo.

---

## Aggiungere una nuova libreria (Persona A)

Vuoi aggiungere il supporto a una libreria CFD/scientifica diversa da PhiFlow — poniamo, un diverso solver di
fluidi, una libreria di mesh o un pacchetto di calcolo numerico.

### I passi

Crei una **nuova distribuzione plugin** sotto `packages/`. Nulla in `coral-core` o `coral-app` cambia —
l'host scopre il tuo plugin a runtime una volta che è installato.

1. **Crea lo scheletro del pacchetto** `packages/coral-plugin-mycfd/`:

   ```
   packages/coral-plugin-mycfd/
   ├── pyproject.toml
   └── src/coral_plugin_mycfd/__init__.py
   ```

2. **Scrivi funzioni/classi wrapper tipizzate** (non chiamate dirette dentro la libreria) e una sottoclasse
   `Plugin`. Vedi
   [perché il wrapping è necessario](#perché-mathsqrt-ha-bisogno-di-un-wrapper-non-possiamo-caricare-le-funzioni-python-dinamicamente)
   più sotto — in breve: il registry può produrre un nodo utile solo se la funzione ha parametri annotati coi
   tipi e un valore di ritorno annotato coi tipi. La ABC `Plugin` *impone* entrambi i metodi (dimenticane uno e
   la classe non può essere istanziata):

   ```python
   # src/coral_plugin_mycfd/__init__.py
   from typing import Any, Dict
   from coral_core import Plugin
   from mycfd import Solver  # the real library — a hard dependency of this plugin (see step 3)

   def create_solver(resolution: int) -> Any:
       """Wrap Solver's constructor with an explicit, registry-friendly signature."""
       return Solver(resolution=resolution)

   class MyCFDPlugin(Plugin):
       def get_functions(self) -> Dict[str, Any]:
           return {"create_solver": create_solver}
       def get_classes(self) -> Dict[str, Any]:
           return {}
   ```

3. **Dichiara l'entry point e le dipendenze** in `packages/coral-plugin-mycfd/pyproject.toml`. Il **nome**
   dell'entry point (`mycfd`) è ciò a cui `-p` fa riferimento; il target è la tua **classe** `Plugin`. Poiché
   il plugin *dichiara* la libreria reale come dipendenza hard, installare il plugin garantisce che sia
   importabile — un'installazione rotta fallisce in modo chiaro con `ImportError` (non c'è **nessuna** guardia
   `try/except AVAILABLE`; la scoperta pigra significa già che un plugin non selezionato non viene mai
   importato):

   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "coral-plugin-mycfd"
   version = "0.0.0"
   requires-python = ">=3.12"
   dependencies = ["coral-core", "mycfd"]

   [project.entry-points."coral.plugins"]
   mycfd = "coral_plugin_mycfd:MyCFDPlugin"

   [tool.hatch.build.targets.wheel]
   packages = ["src/coral_plugin_mycfd"]
   ```

4. **Collega il pacchetto** nel `pyproject.toml` radice così che `uv sync` lo installi dal workspace
   (`[tool.uv.workspace] members = ["packages/*"]` copre già la directory):

   ```toml
   [tool.uv.sources]
   coral-plugin-mycfd = { workspace = true }
   ```

5. **Sincronizza, poi rigenera e controlla il registry**, infine esegui un grafo:

   ```bash
   uv sync
   uv run coral -p "mycfd" register --output=/tmp/check.json
   # inspect /tmp/check.json — every function/class you exposed should have a sensible
   # arguments/inputs/outputs shape, not everything collapsed to "any"
   uv run coral -p "mycfd" run my_test_graph.json
   ```

   `discover()` ora elenca `mycfd`; nessun codice dell'host è cambiato.

> **Non aggiungere `from __future__ import annotations`** ad alcun modulo di plugin (o dell'host). Trasforma le
> annotazioni in stringhe, il che fa leggere al registry `"float"` invece del tipo `float` e collassa ogni
> socket a `"any"`. Un test di guardia (`tests/test_core_contract.py`) lo impone su tutto `packages/*/src`.

### Perché `math.sqrt` ha bisogno di un wrapper? Non possiamo caricare le funzioni Python dinamicamente?

Salta fuori subito appena guardi `coral-plugin-math` — `math.sqrt` non è registrato direttamente; c'è invece un
wrapper `math_sqrt(x: float) -> float` che lo chiama. La ragione è strutturale, non stilistica:

Il registry (`registry.py:generate_registry`) è **guidato dalle annotazioni**. Per ogni parametro e valore di
ritorno chiama `inspect.signature(func)` e converte l'annotazione in una stringa di tipo del protocollo
tramite `python_type_to_string`:

```python
def python_type_to_string(py_type) -> str:
    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return _REVERSE_PRIMITIVES_MAP[Any]
    ...
```

Un'annotazione mancante diventa `"any"`. Peggio, per i valori di **ritorno**, `_process_return_type` tratta
un'annotazione mancante come *nessun socket di output*:

```python
if (return_annotation is not None
    and return_annotation != type(None)
    and return_annotation != inspect.Signature.empty):
    return [_create_output_argument(return_annotation)], [param_idx]
return [], []   # <- missing/None annotation → zero outputs
```

`math.sqrt` è un builtin C (`builtin_function_or_method`). Anche dove `inspect.signature` ha successo su di
esso, i parametri e il ritorno non portano **alcuna annotazione di tipo** — quell'informazione semplicemente
non esiste a runtime per le funzioni implementate in C; vive solo nei file di stub `.pyi`, che qui nulla legge.
Registrare `math.sqrt` direttamente produrrebbe quindi un nodo con un input `"any"` e **nessun socket di
output** — impossibile da collegare a qualsiasi cosa a valle.

Il wrapper è la correzione più piccola: fornisce le annotazioni che l'introspezione a runtime di Python non
riesce a recuperare, ed è anche un posto comodo per il logging e la coercizione di tipo (es. riconvertire uno
scalare NumPy in un `float` Python). È un vincolo reale e strutturale — non un ripiego — ogni volta che
incapsuli un'estensione C o una libreria non annotata.

**Quando non ti serve un wrapper:** se la funzione o la classe è Python puro *e porta già i type hint*,
registrala direttamente — nessun wrapper richiesto. È esattamente ciò che fa `Calculator` in
`coral-plugin-math`: il suo `__init__` e i suoi metodi sono Python annotato, quindi `registry.py` li
introspeziona senza alcun adattatore.

---

## Estendere gli interni o i contratti (Persona B)

Vuoi cambiare come coral-python funziona internamente, o far evolvere il suo contratto con la piattaforma.

### Il disaccoppiamento è reale, ed è il tuo punto di estensione

Poiché `registry.py` ed `executor.py` non si importano mai a vicenda ed entrambi consumano la superficie
dell'host solo attraverso `build_function_map`/`build_class_map`/`PRIMITIVES_MAP`, puoi riscrivere l'intero
livello di scoperta/caricamento in `coral_app/__init__.py` — una diversa strategia di scoperta, caricamento
eager vs. pigro, passare un contesto dell'host a `PluginClass(...)`, qualunque cosa — e sia il generatore del
registry sia l'executor continuano a funzionare *invariati*, purché:

1. `build_function_map(include=...)` / `build_class_map(include=...)` continuino a restituire dizionari
   `{name: callable}` / `{name: class}`, e
2. la forma JSON che ciascun lato produce/consuma resti `{type, arguments, inputs, outputs, node_type}` per le
   voci del registry e `{type, value?}` per i nodi di grafo snelli.

È una giuntura davvero utile: significa che "migliorare il sistema di tipi del registry" e "migliorare come i
plugin vengono scoperti/caricati" sono progetti separabili. Il *contratto* dei plugin stesso (la ABC `Plugin`
di `coral-core`) e il nome del gruppo di entry point (`coral.plugins`) sono l'unica parte che è API pubblica —
una volta che esistono veri plugin di terze parti, tratta entrambi come stabili.

**Il costo di quel disaccoppiamento:** è imposto per *convenzione*, non da un'interfaccia o un test condiviso
che vincoli insieme i due lati. `registry.py` ed `executor.py` codificano **in modo indipendente** le stesse
assunzioni — es. che un nome puntato come `"math.sqrt"` sia una funzione, non un metodo (vedi il commento in
`executor.py:_classify`: *"functions checked before the split so dotted names like `math.sqrt` resolve as
functions, not methods"*), e che l'argomento `self` di un metodo sia sempre l'input all'indice 0. Nulla
controlla che un cambiamento su un lato non rompa silenziosamente le assunzioni dell'altro — se tocchi questo
confine, aggiorna entrambi e riesegui l'intera suite (`uv run pytest`).

### Punti di estensione concreti

- **Sistema di tipi più ricco.** Solo i sei tipi di `PRIMITIVES_MAP` (`int`, `float`, `str`, `bool`, `any`,
  `none`) fanno il round-trip attraverso il registry; ogni altra annotazione (una classe di dominio, `list`,
  un elemento di tupla non primitivo) collassa a `"any"`. Uno schema più ricco (es. registrare i nomi delle
  classi di dominio come loro propri tipi del protocollo, come già fanno gli argomenti `self` dei metodi con il
  nome della classe) darebbe socket più precisi e una migliore validazione sul canvas.
- **Import pigro dei plugin (fatto).** La scoperta tramite entry point importa già solo i plugin nominati in
  `-p`: `discover()` enumera i nomi senza importare, e `load(name)` importa solo quel singolo. Un `phiflow` non
  selezionato non innesca mai la catena di import PhiFlow/JAX. (Questa era una debolezza del vecchio livello
  `definitions/`, ora risolta dall'architettura a plugin.)
- **Stato di esecuzione per-nodo.** La CLI accetta `--touch-dir` per compatibilità con la funzionalità di
  stato per-nodo dal vivo della piattaforma, ma non ci scrive ancora nulla — `executor.py` dovrebbe emettere
  un file di stato per nodo man mano che esegue.
- **Imporre la convenzione registry/executor.** Un test condiviso (o un'unica fonte di "come classificare una
  stringa `type`") contro cui sia `registry.py` sia `executor.py` vengano verificati rimuoverebbe il rischio
  "convenzione, non imposizione" descritto sopra.
- **Esecuzione in tempo lineare.** L'ordinamento topologico dell'executor usa una lista come coda e ogni nodo
  riscansiona l'intera lista di archi per i suoi input (vedi [Come l'executor esegue un grafo](#come-lexecutor-esegue-un-grafo--ordine-di-esecuzione-e-_classify)).
  Un `collections.deque` più gli archi pre-raggruppati per target rende lineare un'intera esecuzione — non
  necessario alle dimensioni odierne, ma una vittoria pulita prima di scalare a grafi grandi. (Nota:
  `_classify` di per sé è già O(1) per nodo.)

---

## Motivazioni di design / FAQ

### Perché `math.sqrt` ha bisogno di un wrapper? Non possiamo caricare le funzioni Python dinamicamente senza wrapping manuale?

Risposto per esteso [sopra](#perché-mathsqrt-ha-bisogno-di-un-wrapper-non-possiamo-caricare-le-funzioni-python-dinamicamente).
In breve: il registry è guidato dalle annotazioni, e Python non espone annotazioni di tipo a runtime per le
funzioni implementate in C — non c'è nulla da introspezionare. Le funzioni e le classi Python pure *con* type
hint (come `Calculator`) non hanno bisogno di alcun wrapper.

### Il disaccoppiamento registry/executor permette davvero a qualcuno di riscrivere il livello di scoperta sotto lo stesso contratto?

Sì — vedi [Estendere gli interni](#il-disaccoppiamento-è-reale-ed-è-il-tuo-punto-di-estensione) sopra. È una
genuina proprietà architetturale (verificato: nessuno dei due moduli importa l'altro; entrambi toccano solo la
superficie pubblica di `coral_app`), con un'unica riserva onesta: la separazione *tra `registry.py` ed
`executor.py`* è basata sulla convenzione, non imposta da un contratto, quindi i cambiamenti su un lato
richiedono un controllo corrispondente sull'altro. (Il contratto dei *plugin*, al contrario, è ora una ABC
imposta — vedi sotto.)

### Perché scoprire i plugin tramite entry point invece di un dizionario `_MODULES` in un unico package?

Il design precedente teneva un dizionario `_MODULES` hardcoded in un `definitions/__init__.py`, aggregando
moduli fratelli che soddisfacevano ciascuno un contratto *duck-typed* `get_functions()`/`get_classes()`. È un
idioma valido a piccola scala, ma ha due limiti strutturali: ogni capacità doveva essere un modulo fratello
*dentro un unico package* (quindi nulla poteva essere installato in modo indipendente o provenire da terze
parti), e il contratto era imposto solo dalla convenzione.

L'architettura a plugin rimuove entrambi i limiti:
- **La scoperta avviene tramite gli entry point della stdlib `importlib.metadata`** (gruppo `coral.plugins`).
  Qualsiasi distribuzione installata che dichiari un entry point viene trovata — inclusa una che non esisteva
  quando l'host è stato costruito. L'host legge metadati standard; un plugin non scrive mai file di proprietà
  dell'host né esegue hook post-installazione. (Alternative scartate: scansione dei path + `inspect`, scansione
  dei namespace package, e `pluggy`/`stevedore` — che si limitano a incapsulare gli entry point. Vince la
  stdlib canonica.)
- **Il contratto è una ABC** (`coral_core.Plugin`), non un `typing.Protocol` né un semplice hook `register()`,
  quindi `@abstractmethod` *impone* che un plugin implementi entrambi i metodi. L'entry point risolve alla
  **classe**; l'host la istanzia (`PluginClass()`), che è il posto naturale per iniettare più avanti un oggetto
  di contesto fornito dall'host.

Due cose da sapere se lavori in `coral_app/__init__.py`:
- `build_function_map` e `build_class_map` condividono un piccolo helper `_selected(include, exclude)` che
  risolve la lista dei nomi (`include=None` → `sorted(discover())`, poi si applica `exclude`). Ciascuna poi
  carica i plugin selezionati e fonde le loro mappe.
- Poiché la fusione fa `.update()` in un dizionario condiviso nell'ordine di selezione, se due plugin espongono
  la stessa chiave (oggi, `print_result` è sia in `coral-plugin-math` sia in `coral-plugin-string`) l'ultimo
  vince silenziosamente. Innocuo oggi dato che il duplicato è identico, ma da sapere prima di aggiungere un
  nome in conflitto. L'ordine "all" è `sorted(discover())`, quindi è deterministico.

---

## Punti di forza e di debolezza

**Punti di forza**

- Separazione pulita con un disaccoppiamento reale e verificabile: un contratto `coral-core`, un host
  `coral-app` e distribuzioni `coral-plugin-*` installabili in modo indipendente; dentro l'host, `registry` ed
  `executor` restano disaccoppiati (descrivere vs. eseguire).
- **Contratto dei plugin imposto.** `coral-core.Plugin` è una ABC — un plugin che omette `get_functions()` o
  `get_classes()` non può nemmeno essere istanziato. Nessun duck typing.
- **Scoperta pigra e basata sugli standard.** I plugin sono trovati tramite gli entry point di
  `importlib.metadata` e importati solo quando selezionati, così un `phiflow` inutilizzato non paga mai il suo
  costo di import — e i plugin di terze parti possono essere aggiunti puramente installandoli.
- Genuinamente coral-compatibile: stessa superficie CLI, stesso schema JSON del backend C++ — la piattaforma
  non ha bisogno di alcun codice specifico per il backend per pilotarlo.
- Il protocollo di grafo snello e indicizzato per tipo combacia esattamente con il formato di export attuale
  della piattaforma (nessun adattatore necessario sul lato piattaforma).
- Superficie piccola e ben testata: **100 test che passano** coprendo il contratto, la scoperta/caricamento, la
  generazione del registry (con pin golden a livello di byte) e l'esecuzione.

**Punti di debolezza**

- **Sistema di tipi con perdita** — solo sei tipi primitivi fanno il round-trip attraverso il registry; tutto
  il resto diventa `"any"`, il che indebolisce la validazione delle connessioni sul canvas.
- **Asimmetria delle annotazioni** — un'annotazione di parametro mancante diventa `"any"` (ancora usabile), ma
  un'annotazione di ritorno mancante non produce *alcun socket di output* (il nodo diventa un vicolo cieco).
  Facile inciamparci quando si scrive un nuovo wrapper.
- **I metodi delle estensioni C vengono scartati silenziosamente.** Il controllo `inspect.isfunction` di
  `_add_methods` filtra via i metodi delle classi implementate in C (es. `datetime`); si registrano solo i
  loro costruttori. Incapsulare in una classe Python pura è l'unico workaround.
- **Convenzione, non contratto, tra `registry.py` ed `executor.py`** (vedi sopra) — codificano in modo
  indipendente le stesse assunzioni di classificazione del `type`. Il contratto dei *plugin* è ora imposto da
  una ABC, ma questa giuntura interna dell'host è ancora basata sulla convenzione — un rischio latente per i
  cambiamenti futuri.
- **Il boilerplate del wrapping manuale** è il prezzo del registry guidato dalle annotazioni; non scala a
  "incapsulare un'intera libreria grande" senza una certa ripetizione.

---

## Roadmap / lavori rinviati

Non fanno parte dell'attuale MVP locale; tracciati per dopo:

- Esecuzione remota (SSH + Slurm), corrispondente alla modalità backend remota della piattaforma.
- Stadi di pipeline (coral-python come uno stadio in un DAG multi-stadio).
- Stato di esecuzione per-nodo tramite `--touch-dir` (vedi [Estendere gli interni](#punti-di-estensione-concreti)).
- Promuovere coral-python da cartella di workspace a git submodule del repository della piattaforma, una volta
  containerizzato per simulare un cluster.
