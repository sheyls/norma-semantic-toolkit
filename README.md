# NORMA — Normative Ontology for Regulatory Machine-readable Annotations

NORMA transforms BPMN processes annotated with legal norms into a semantic knowledge graph (OWL 2 + SWRL). It is a **norm determination engine** — given a set of annotated BPMN files, NORMA determines which obligations, prohibitions, and permissions apply to a given legal role under a given set of conditions.

```
Annotated BPMN  →  Knowledge Graph (ABox/TBox)  →  SWRL rules + SPARQL
```

---

## Requirements

- Python 3.10+
- [Camunda Modeler 8](https://camunda.com/platform/modeler/) (to annotate BPMN files)

---

## Repository Structure

```
norma_build.py                 ← CLI: KG pipeline (recommended entry point)
norma_rules.py                 ← CLI: SWRL rule extraction
norma/
  parsing/
    bpmn_parser.py             ← BPMN XML → reduced directed graph
  kg/
    builder.py                 ← BPMN folder → JSON intermediate + Turtle ABox
    normalizer.py              ← Entity label normalization (fuzzy deduplication)
  rules/
    extractor.py               ← BPMN graph → RuleIR (path enumeration)
    ir.py                      ← Rule intermediate representation
  exporters/
    swrl.py                    ← RuleIR → SWRL/OWL XML
ontology/
  norma-ontology-v1.ttl        ← TBox in Turtle (canonical)
  norma-ontology-v1.rdf        ← TBox in RDF/XML (for Protégé / OWLAPI tools)
regulations/
  eu-ai-act/
    bpmn/                      ← *.bpmn files go here
    eu-ai-act.abox.ttl         ← generated ABox (after running the pipeline)
camunda-template/
  camunda8-compliance-template.json   ← Camunda Modeler element template
app/                           ← Web application (FastAPI + D3.js)
  main.py
  sparql_presets.py
  templates/index.html
```

---

## Camunda Element Template

### Installation

Copy `camunda-template/camunda8-compliance-template.json` to:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/camunda-modeler/resources/element-templates/` |
| Windows | `%APPDATA%\camunda-modeler\resources\element-templates\` |
| Linux | `~/.config/camunda-modeler/resources/element-templates/` |

Create the folder if it does not exist, then restart Camunda Modeler. The template will appear in the **Properties Panel** as **"NORMA — Legal Compliance Annotation"** when you select a task or exclusive gateway.

The template is also available from the web application: **Tools → Camunda Template → Download**.

---

### Template Fields

The template applies to `bpmn:Task`, `bpmn:UserTask`, `bpmn:ServiceTask`, `bpmn:ManualTask`, `bpmn:BusinessRuleTask`, `bpmn:SendTask`, and `bpmn:ExclusiveGateway`.

All values are stored as `zeebe:property` bindings and read by the NORMA pipeline.

#### Group 1 — Element Type

| Field | Binding | Values | Notes |
|-------|---------|--------|-------|
| Element Type | `compliance_elementType` | `task` \| `exclusiveGateway` | Controls which groups are shown. Tasks carry norms; gateways evaluate legal conditions. |

---

#### Group 2 — Deontic Norm *(shown when elementType = task)*

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Deontic Modality | `compliance_deonticType` | Dropdown | `obligation` · `prohibition` · `permission` · `recommendation` · `recommendation_not` · `fact` |
| Norm Statement | `compliance_normStatement` | Text area | Human-readable restatement for lawyers. Not parsed by the pipeline. |
| Deontic ID | `compliance_deonticId` | String | Unique ID within the regulation pack. Pattern: `OBL_xxx`, `PRH_xxx`, `PER_xxx`, `REC_xxx`, `REC_NOT_xxx`, `FCT_xxx`. |
| Agent (Who) | `compliance_agent` | String | The norm bearer — who must/must not/may act. Minted as `norma:Agent` in the KG. |
| Action (What) | `compliance_action` | String | Verb phrase — e.g. *establish*, *disclose*, *deploy*. |
| Object (On What) | `compliance_object` | String | Entity acted upon — e.g. *risk_management_system*. Minted as `norma:LegalObject` in the KG. |
| Fact Statement | `compliance_factStatement` | Text area | *(fact only)* Constitutive rule in plain language. |
| Binding Force | `compliance_bindingForce` | Dropdown | `hard_law` · `soft_law` · `internal_policy` · `contractual` |

---

#### Group 3 — Legal Condition *(shown when elementType = exclusiveGateway)*

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Condition Statement | `gw_conditionStatement` | Text area | Legal question at the gateway — e.g. *"Is the AI system classified as high-risk?"* |
| True Branch Label | `gw_trueBranch` | String | Label on the "yes" outgoing flow — e.g. *High-risk* |
| False Branch Label | `gw_falseBranch` | String | Label on the "no" outgoing flow — e.g. *Low-risk* |
| Triggered Norm IDs | `gw_crossRefs` | String | Comma-separated deontic IDs triggered by this condition — used to generate `norma:triggersNorm` links. |

---

#### Group 4 — Scope & Temporal

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Trigger Condition | `compliance_triggerCondition` | Text area | When the norm applies — human-readable, not parsed into SWRL. |
| Jurisdiction | `compliance_jurisdiction` | String | Geographic/legal scope — e.g. *EU*, *US-CA*, *global* |
| Effective Date | `compliance_effectiveDate` | String | `YYYY-MM-DD` — date the norm enters into force. |
| Deadline / Sunset | `compliance_deadline` | String | `YYYY-MM-DD` — date after which the norm ceases to apply. |
| Norm Status | `compliance_status` | Dropdown | `active` · `under_review` · `disputed` · `superseded` · `pending` |

---

#### Group 5 — Consequences & Exceptions

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Exception / Carve-out | `compliance_exception` | Text area | Conditions under which this norm does NOT apply. |
| Sanction / Consequence | `compliance_sanction` | Text area | Consequence of non-compliance — e.g. *"Fine up to €30M or 6% of global annual turnover"* |
| Risk Level | `compliance_riskLevel` | Dropdown | `critical` · `high` · `medium` · `low` |
| Related Norm IDs | `compliance_crossRefs` | String | Comma-separated IDs of related norms — generates `norma:relatesTo` links. |

---

#### Group 6 — Legal Source & Provenance

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Regulation Name | `compliance_regulation` | String | Full regulation name — e.g. *EU AI Act*, *GDPR*. Minted as `norma:LegalSource`. |
| Article / Section | `compliance_article` | String | Article number — e.g. *50*, *6* |
| Paragraph / Subsection | `compliance_paragraph` | String | e.g. *2*, *1(a)* |
| Original Legal Text | `compliance_originalText` | Text area | Verbatim quote from the legislative text — for traceability. |
| Regulation URI | `compliance_regulationURI` | String | ELI-compatible dereferenceable URI of the source document. |

---

#### Group 7 — Annotation Metadata

| Field | Binding | Type | Notes |
|-------|---------|------|-------|
| Extraction Method | `compliance_extractionMethod` | Dropdown | `manual_lawyer` · `manual_analyst` · `llm` · `pattern-matching` · `rule-based` |
| Confidence Score | `compliance_confidence` | String | `0.0–1.0` — annotator certainty. Values below 0.7 flag mandatory legal review. |
| Legal Review | `compliance_legalReview` | Dropdown | `approved` · `pending` · `none` |
| Annotator | `compliance_annotator` | String | Name/ID of the person who created this annotation. |
| Annotation Date | `compliance_annotationDate` | String | `YYYY-MM-DD` |
| Last Reviewed Date | `compliance_lastReviewDate` | String | `YYYY-MM-DD` |

---

## NORMA Ontology (TBox)

### Overview

The TBox is in `ontology/` and is available in two serialization formats:

| File | Format | Use |
|------|--------|-----|
| `norma-ontology-v1.ttl` | Turtle (canonical) | Reference, version control, human editing |
| `norma-ontology-v1.rdf` | RDF/XML | Protégé, OWLAPI-based tools, SWRL engines |

**Ontology IRI:** `https://w3id.org/norma-ontology`  
**Preferred prefix:** `norma:` → `https://w3id.org/norma-ontology#`  
**Version:** 1.0 · **License:** CC BY 4.0

### Design Principle

The TBox is derived strictly from the element template:

- **Dropdown fields** → OWL classes + `owl:NamedIndividual` (oneOf enumeration)
- **Free-text fields** → `owl:DatatypeProperty` (`xsd:string` or `xsd:date`)
- **Structural roles** → `owl:Class` (anchors for ABox individuals)

### Classes

#### Structural Classes

| Class | Role |
|-------|------|
| `norma:NormativeContent` | Root class for content carried by BPMN task elements |
| `norma:LegalCondition` | Content carried by BPMN exclusive gateway elements |
| `norma:Agent` | The bearer of a norm — who must/must not/may act |
| `norma:LegalObject` | The entity on which the prescribed action is performed |
| `norma:LegalSource` | The legislative document from which a norm is extracted |

#### Deontic Modality Classes *(subclasses of NormativeContent)*

| Class | Operator |
|-------|----------|
| `norma:Obligation` | MUST |
| `norma:Prohibition` | MUST NOT |
| `norma:Permission` | MAY |
| `norma:Recommendation` | SHOULD |
| `norma:NegativeRecommendation` | SHOULD NOT |
| `norma:ConstitutiveRule` | IS / COUNTS AS |

#### Binding Force Individuals

`norma:HardLaw` · `norma:SoftLaw` · `norma:InternalPolicy` · `norma:Contractual`

#### Risk Level Individuals

`norma:CriticalRisk` · `norma:HighRisk` · `norma:MediumRisk` · `norma:LowRisk`

#### Norm Status Individuals

`norma:Active` · `norma:UnderReview` · `norma:Disputed` · `norma:Superseded` · `norma:NotYetInForce`

#### Extraction Method Individuals

`norma:ManualLawyer` · `norma:ManualAnalyst` · `norma:LLMExtraction` · `norma:PatternMatching` · `norma:RuleBased`

#### Legal Review Individuals

`norma:Approved` · `norma:PendingReview` · `norma:NotReviewed`

### Object Properties

| Property | Domain | Range | Meaning |
|----------|--------|-------|---------|
| `norma:hasAgent` | NormativeContent | Agent | Who bears the norm |
| `norma:actsOn` | NormativeContent | LegalObject | Object of the prescribed action |
| `norma:fromSource` | NormativeContent | LegalSource | Provenance link |
| `norma:hasBindingForce` | NormativeContent | BindingForce | Legal weight |
| `norma:hasRiskLevel` | NormativeContent | RiskLevel | Non-compliance risk |
| `norma:hasStatus` | NormativeContent | NormStatus | Lifecycle status |
| `norma:hasExtractionMethod` | NormativeContent | ExtractionMethod | How annotation was produced |
| `norma:hasLegalReview` | NormativeContent | LegalReview | Review status |
| `norma:relatesTo` | NormativeContent | NormativeContent | Cross-reference between norms |
| `norma:triggersNorm` | LegalCondition | NormativeContent | Gateway → triggered norm |

### Data Properties

| Property | Type | Source field |
|----------|------|-------------|
| `norma:normStatement` | xsd:string | `compliance_normStatement` |
| `norma:deonticId` | xsd:string | `compliance_deonticId` |
| `norma:action` | xsd:string | `compliance_action` |
| `norma:actsOnLabel` | xsd:string | `compliance_object` |
| `norma:factStatement` | xsd:string | `compliance_factStatement` |
| `norma:triggerCondition` | xsd:string | `compliance_triggerCondition` |
| `norma:jurisdiction` | xsd:string | `compliance_jurisdiction` |
| `norma:effectiveDate` | xsd:date | `compliance_effectiveDate` |
| `norma:deadline` | xsd:date | `compliance_deadline` |
| `norma:exception` | xsd:string | `compliance_exception` |
| `norma:sanction` | xsd:string | `compliance_sanction` |
| `norma:fromRegulation` | xsd:string | `compliance_regulation` |
| `norma:fromArticle` | xsd:string | `compliance_article` |
| `norma:fromParagraph` | xsd:string | `compliance_paragraph` |
| `norma:originalText` | xsd:string | `compliance_originalText` |
| `norma:regulationURI` | xsd:anyURI | `compliance_regulationURI` |
| `norma:confidence` | xsd:decimal | `compliance_confidence` |
| `norma:annotator` | xsd:string | `compliance_annotator` |
| `norma:annotationDate` | xsd:date | `compliance_annotationDate` |
| `norma:lastReviewDate` | xsd:date | `compliance_lastReviewDate` |
| `norma:conditionStatement` | xsd:string | `gw_conditionStatement` |
| `norma:trueBranchLabel` | xsd:string | `gw_trueBranch` |
| `norma:falseBranchLabel` | xsd:string | `gw_falseBranch` |

---

## Knowledge Graph (ABox)

### What the Pipeline Produces

Running `norma_build.py` on a folder of annotated BPMN files generates an **ABox** — a Turtle file that imports the TBox and declares all individuals as OWL named individuals:

| Individual type | Minted from | IRI pattern |
|-----------------|-------------|-------------|
| Norm (Obligation, Prohibition, …) | `compliance_deonticId` | `norma-abox/{pack}#{id}` |
| Agent | `compliance_agent` | `norma-abox/{pack}#agent_{label}` |
| Legal Object | `compliance_object` | `norma-abox/{pack}#obj_{label}` |
| Legal Source | `compliance_regulation` | `norma-abox/{pack}#src_{label}` |
| Legal Condition | gateway element ID | `norma-abox/{pack}#cond_{id}` |

The same agent or regulation appearing across multiple BPMN files is resolved to a single individual (optionally via the normalizer).

### Building the KG

```bash
# Build a regulation pack → generates .json + .abox.ttl
python norma_build.py regulations/eu-ai-act/

# Skip entity label normalization
python norma_build.py regulations/eu-ai-act/ --no-normalize

# Generate a normalization override template, then apply it
python norma_build.py regulations/eu-ai-act/ --template overrides.json
python norma_build.py regulations/eu-ai-act/ --override overrides.json

# Build an organisation's internal policies
python norma_build.py organizations/acme-corp/internal/ --org --reg-base regulations/
```

**Outputs** (written into the same folder as the BPMN files):

| File | Description |
|------|-------------|
| `<pack>.json` | JSON intermediate (one record per annotated element) |
| `<pack>.abox.ttl` | Turtle ABox — imports `norma-ontology-v1.ttl` |

### Normalization

When the same regulation or agent is written inconsistently across files ("IA Act", "ia act", "EU AI Act"), the normalizer resolves them to a single canonical label before generating the ABox. Fuzzy similarity threshold is configurable (default 0.82):

```bash
# Standalone normalizer on an existing JSON intermediate
python kg_normalizer.py pack.json --template overrides.json
python kg_normalizer.py pack.json --override overrides.json --out pack_normalized.json

# Custom threshold
python norma_build.py regulations/eu-ai-act/ --threshold 0.90
```

### Visualizing the KG

Load the ABox in the **NORMA web app** (see [Web Application](#web-application)) or in any OWL/SPARQL tool:

- **Protégé**: open `norma-ontology-v1.rdf` as the TBox, then merge/import the ABox Turtle file
- **Apache Jena / Fuseki**: load both TBox and ABox; SPARQL 1.1 endpoint available
- **NORMA app**: upload the ABox via the *Upload* panel — the D3.js force-directed graph renders automatically in the *Knowledge Graph* panel

---

## SWRL Rules

### What SWRL Rules Express

SWRL (Semantic Web Rule Language) rules encode the **norm applicability logic** derived from the execution paths through the BPMN. Each rule corresponds to one start-to-end path through the reduced BPMN graph:

```
[gateway condition is TRUE] ∧ [agent matches] ∧ ... → [norm applies]
```

The rule body contains Boolean data atoms derived from gateway annotations (`gw_conditionStatement`). The rule head contains object-property assertions connecting agents and norms.

### Generating SWRL Rules

```bash
# Run from project root
python norma_rules.py regulations/eu-ai-act/bpmn/art50-art95.bpmn outputs/rules.swrl.owl
```

**Output:**

| File | Format | Use |
|------|--------|-----|
| `rules.swrl.owl` | OWL/XML + SWRL | Protégé SWRL tab, SWRL engines |

### Loading SWRL Rules in Protégé

1. Open the TBox (`ontology/norma-ontology-v1.rdf`) in Protégé.
2. File → Merge Ontology → select the ABox `.ttl`.
3. File → Merge Ontology → select the SWRL `.owl` file.
4. Activate the SWRL tab (View → Tabs → SWRL).
5. Run the Drools/Pellet reasoner to materialise inferences.

### Rule Intermediate Representation

Internally, NORMA uses a `RuleIR` object (`norma/rules/ir.py`) that captures:

- `rid` — rule identifier (path hash)
- `conditions` — list of `Condition` atoms (gateway predicates + Boolean values)
- `relations` — list of `RelationAtom` (object-property assertions in the head)
- `data_atoms` — list of `DataAtom` (datatype assertions in the head)
- `actions` — list of `Action` (optional action labels)

The `RuleIR` objects are consumed by the SWRL exporter (`norma/exporters/swrl.py`).

---

## SPARQL Queries

### Running Queries

The NORMA web app exposes a full **SPARQL 1.1 endpoint** backed by pyoxigraph. After loading a regulation pack:

- **In-app**: open the *SPARQL* panel — use the preset library or write your own query
- **Programmatic**: `POST /api/sparql` with `{"query": "SELECT ..."}` (JSON body)
- **curl**: `curl -X POST http://localhost:8000/api/sparql -H "Content-Type: application/json" -d '{"query":"SELECT * WHERE {?s ?p ?o} LIMIT 10"}'`

### Preset Query Library

Eight curated queries are available in the SPARQL panel and via `GET /api/sparql-presets`:

| ID | Label | What it returns |
|----|-------|-----------------|
| `all-norms` | All norms | Every norm with binding force, risk level, and article reference |
| `agents` | Agents per norm | Which agents are bound by each norm and the norm's binding force |
| `conditions` | Gateway conditions | All LegalCondition individuals with their true/false branch labels |
| `hard-law` | Hard-law obligations | Obligations classified as HardLaw with regulation/article/paragraph |
| `prohibitions` | Prohibitions | All Prohibition norms with action, object, and risk level |
| `by-regulation` | Norms by regulation | All norms grouped by the regulation they derive from |
| `critical-risks` | Critical-risk norms | Norms marked Critical or High risk |
| `count-by-type` | Count norms by type | Summary count of each deontic modality |

### Example Queries

**All agents bound by hard-law obligations:**
```sparql
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent ?norm ?article
WHERE {
  ?norm a norma:Obligation ;
        norma:hasBindingForce norma:HardLaw ;
        norma:hasAgent ?agent ;
        norma:fromArticle ?article .
  ?agent rdfs:label ?agent .
}
```

**Norms that apply to a specific agent:**
```sparql
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?type ?riskLevel
WHERE {
  VALUES ?type { norma:Obligation norma:Prohibition norma:Permission }
  ?norm a ?type ;
        rdfs:label ?label ;
        norma:hasAgent ?agent ;
        norma:hasRiskLevel ?riskLevel .
  ?agent rdfs:label "AI_Provider"@en .
}
```

**Gateway conditions that trigger a given norm:**
```sparql
PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?cond ?statement
WHERE {
  ?cond a norma:LegalCondition ;
        norma:conditionStatement ?statement ;
        norma:triggersNorm <https://w3id.org/norma-abox/eu-ai-act#OBL_1> .
}
```

### Extending the Preset Library

Add entries to `app/sparql_presets.py`:

```python
{
    "id": "my-query",
    "label": "My custom query",
    "description": "What this query returns.",
    "query": "PREFIX norma: <https://w3id.org/norma-ontology#>\nSELECT ..."
}
```

The UI picks them up automatically on next load.

---

## Web Application

### Starting the App

```bash
cd app
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000` in your browser.

### UI Panels

The single-page application has the following panels accessible from the sidebar:

| Panel | What it does |
|-------|-------------|
| **Home** | Landing page — overview, quick-start guide, architecture diagram |
| **Upload** | Upload a `.bpmn` or `.abox.ttl` file to create a new regulation pack in the workspace |
| **Norm Annotations** | Browse and edit all template fields for every annotated element. Fields are always shown, even if empty — lawyers can fill or correct them in-browser. |
| **Knowledge Graph** | D3.js force-directed graph of the ABox. Nodes are colour-coded by type (norms, agents, objects, sources). Click a node to inspect its properties. |
| **SPARQL** | Full SPARQL 1.1 editor with preset query library, results table, and raw JSON toggle |
| **ABox** | Turtle source viewer + download buttons (`.ttl` and `.rdf`) |
| **Camunda Template** | Download link + installation guide + full field reference |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web application (HTML) |
| `POST` | `/api/upload` | Upload a BPMN or ABox Turtle file |
| `GET` | `/api/packs` | List loaded regulation packs |
| `GET` | `/api/pack/{pack}/norms` | All annotated elements with every template field |
| `PATCH` | `/api/pack/{pack}/norm/{norm_id}` | Update template fields for one norm (in-memory) |
| `GET` | `/api/pack/{pack}/graph` | D3.js-ready node/link JSON for the KG visualisation |
| `POST` | `/api/sparql` | Execute a SPARQL 1.1 query against the loaded store |
| `GET` | `/api/sparql-presets` | Return the curated preset query library |
| `GET` | `/api/pack/{pack}/abox` | Download the ABox as Turtle (`.ttl`) |
| `GET` | `/api/pack/{pack}/download/abox-rdf` | Download the ABox as RDF/XML (`.rdf`) |
| `GET` | `/api/download/template` | Download the Camunda element template JSON |

---

## Quick Start

### Step 1 — Install the Camunda element template

Copy `camunda-template/camunda8-compliance-template.json` to the Camunda Modeler templates folder (see [Installation](#installation) above) and restart Modeler.

### Step 2 — Annotate a BPMN process

Open or create a BPMN file in Camunda Modeler. For each task or gateway that carries a legal norm:

1. Select the element.
2. In the Properties Panel, choose **NORMA — Legal Compliance Annotation** from the template dropdown.
3. Fill in the fields (see [Template Fields](#template-fields) above).

Save the file inside a `bpmn/` subfolder of your regulation pack, e.g.:

```
regulations/eu-ai-act/bpmn/art50-art95.bpmn
```

### Step 3 — Build the knowledge graph

```bash
python norma_build.py regulations/eu-ai-act/
```

This produces `eu-ai-act.json` and `eu-ai-act.abox.ttl` in `regulations/eu-ai-act/`.

### Step 4 — Extract SWRL rules

```bash
python norma_rules.py regulations/eu-ai-act/bpmn/art50-art95.bpmn outputs/rules.swrl.owl
```

This produces `rules.swrl.owl` — an OWL/XML file containing the SWRL rules, ready to load in Protégé.

### Step 5 — Explore in the web app

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000`, upload the ABox Turtle file, and explore norms, the KG, and SPARQL queries interactively.

---

## Example — EU AI Act Art. 50 / Art. 95

A ready-to-use example is in `regulations/eu-ai-act/bpmn/art50-art95.bpmn`.

```bash
python norma_build.py regulations/eu-ai-act/
python norma_rules.py regulations/eu-ai-act/bpmn/art50-art95.bpmn outputs/rules.swrl.owl
```

The BPMN models the following norms:

| ID | Type | Agent | Article |
|----|------|-------|---------|
| OBL_1 | Obligation | AI owner | Art. 50 §2 |
| REC_1 | Recommendation | AI owner | Art. 95 §2 |

---

## Licence

CC BY 4.0 — Sheyla Leyva-Sánchez et al.
