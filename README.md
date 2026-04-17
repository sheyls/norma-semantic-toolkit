# NORMA — Normative Ontology for Regulatory Machine-readable Annotations

NORMA transforms BPMN processes annotated with legal norms into a semantic knowledge graph (OWL 2 + SWRL). It is a **norm determination engine** — given annotated BPMN files, NORMA determines which obligations, prohibitions, and permissions apply to a given legal role under a given set of conditions.

```
Annotated BPMN  →  Knowledge Graph (ABox/TBox)  →  SWRL rules + SPARQL + REST API
```

---

## Table of Contents

- [Requirements](#requirements)
- [Repository Structure](#repository-structure)
- [Camunda Element Template](#camunda-element-template)
- [NORMA Annotation Template — Field Reference](#norma-annotation-template--field-reference)
- [NORMA Ontology (TBox)](#norma-ontology-tbox)
- [Knowledge Graph (ABox)](#knowledge-graph-abox)
- [SWRL Rules](#swrl-rules)
- [SPARQL Queries](#sparql-queries)
- [Web Application](#web-application)
- [Quick Start](#quick-start)
- [Example — EU AI Act](#example--eu-ai-act)
- [Licence](#licence)

---

## Requirements

- Python 3.10+
- [Camunda Modeler 8](https://camunda.com/platform/modeler/) (to annotate BPMN files)
- `pip install fastapi uvicorn pyoxigraph jinja2 python-multipart`

---

## Repository Structure

```
norma/
  parsing/
    bpmn_parser.py          ← BPMN XML → reduced directed graph
  kg/
    builder.py              ← BPMN folder → JSON intermediate + Turtle ABox
    normalizer.py           ← Entity label normalization (fuzzy deduplication)
  rules/
    ir.py                   ← Rule intermediate representation (RuleIR)
    extractor.py            ← Reduced graph → RuleIR (DFS path enumeration)
  exporters/
    swrl.py                 ← RuleIR → SWRL/OWL XML
  utils.py                  ← to_symbol() and other helpers
norma_build.py              ← CLI: KG pipeline (batch use)
norma_rules.py              ← CLI: standalone SWRL rule extraction
ontology/
  norma-ontology-v1.ttl     ← TBox in Turtle (canonical)
  norma-ontology-v1.rdf     ← TBox in RDF/XML (for Protégé / OWLAPI tools)
regulations/
  eu-ai-act/
    bpmn/                   ← *.bpmn files go here
    eu-ai-act.abox.ttl      ← pre-built ABox (fallback)
camunda-template/
  camunda8-compliance-template.json   ← Camunda Modeler element template
app/
  main.py                   ← FastAPI web application (auto-builds at startup)
  sparql_presets.py         ← Curated preset SPARQL queries
  templates/index.html      ← Single-page UI
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

Create the folder if it does not exist, then restart Camunda Modeler. The template appears in the **Properties Panel** as **"NORMA — Legal Compliance Annotation"** when you select a task or exclusive gateway.

The template is also available as a download from the web application: **Tools → Camunda Template → Download** (`GET /api/download/template`).

---

# NORMA Annotation Template — Field Reference

The NORMA annotation template is applied directly inside Camunda Modeler to BPMN tasks and exclusive gateways. Each annotated element becomes a node in the NORMA knowledge graph. The template is organised into seven sections.

---

## Element Type

**Element Type** determines whether the annotated element is a task or an exclusive gateway. A task represents a norm — something a legal role must do, must not do, may do, or should do. An exclusive gateway represents a legal condition — a yes/no question whose answer determines which norms apply in a given situation. This field controls the visibility of all other fields and is the entry point of the annotation.

---

## Norm Content

This section captures the substantive content of the norm. It is the semantic core of the annotation — defining what the law prescribes, to whom, on what, and with what legal weight.

**Deontic Modality** specifies the modal operator of the norm. Available values: obligation (MUST), prohibition (MUST NOT), permission (MAY), recommendation (SHOULD), negative recommendation (SHOULD NOT), constitutive rule (IS / COUNTS AS). This field determines how the norm individual is classified in the knowledge graph and which deontic class it belongs to.

**Norm Statement** is a plain-language restatement of the norm. It is not parsed automatically. Its function is to provide the auditable bridge between the formal annotation and the legal intention behind it.

**Responsible Party (Who)** is the legal role that is the subject of the norm — the entity that must, must not, or may act. It is expressed as an abstract role (e.g., AI Provider, Data Controller, Deployer). The pipeline generates a `LegalAgent` individual shared across all norms that reference the same role.

**Legal Action (What)** is the verb phrase of the prescribed, prohibited, or permitted action in the infinitive (e.g., establish, disclose, deploy, mark, notify). This is the WHAT of the WHO–WHAT–ON-WHAT structure of every regulative norm.

**Legal Object / Target (On What)** is the entity on which the action falls — the system, data, or document affected by the norm (e.g., personal data, AI system, audit log). The pipeline generates a `LegalObject` individual shared across norms that reference the same object.

**Constitutive Rule / Fact Statement** only appears when the modality is set to Constitutive Rule / Fact. Unlike regulative norms, constitutive rules define legal classifications: under what conditions a system is high-risk, what counts as data processing. This field captures those declarations.

**Binding Force** captures the legal weight of the norm: hard law (directly enforceable), soft law (guidelines and codes of conduct), internal policy, or contractual obligation.

---

## Legal Condition

This section is active only when the element is an exclusive gateway.

**Condition Statement** is the legal yes/no question evaluated at the gateway (e.g., "Does the system generate synthetic content?"). This question becomes the predicate of the SWRL rule body — its boolean value determines which norms are inferred as applicable.

**True Branch Label** is the display label on the outgoing flow when the condition is satisfied (default: "Yes"). The pipeline uses this label to map the graph arc to the boolean `true` value in the SWRL body.

**False Branch Label** is the display label on the outgoing flow when the condition is not satisfied (default: "No"). It serves the same purpose for the boolean `false` value.

---

## Scope and Temporal

**Trigger Condition** is a plain-language description of the circumstances under which the norm applies. It is stored as a data property and not processed as a rule.

**Jurisdiction** is the territorial scope of the norm (e.g., EU, UK, US-CA).

**Effective Date** is the date from which the norm is legally in force (`xsd:date`).

**Deadline / Sunset Date** is the compliance deadline or expiry date (`xsd:date`).

**Norm Status** captures the lifecycle state: Active, UnderReview, Disputed, Superseded, or NotYetInForce.

---

## Consequences and Exceptions

**Exception / Carve-out** records the conditions under which the norm expressly does not apply. Stored as a data property; full formalisation into negation rules belongs to the defeasible logic layer.

**Sanction / Consequence of Breach** is the legal consequence of non-compliance (e.g., administrative fines). Not used in automatic reasoning.

**Compliance Criticality** is the operational severity of non-compliance from the organisation's perspective: Critical, High, Medium, or Low. Distinct from binding force — an internal policy can have Critical criticality, and a hard-law norm can have Low if breach risk is minimal.

---

## Legal Source

**Regulation Name** is the full name of the legislative instrument (e.g., EU AI Act, GDPR). The pipeline creates a `LegalSource` individual shared across all norms from the same regulation within a pack.

**Article / Section** is the article or section number. Every automatically derived norm conclusion carries its legislative locator.

**Paragraph / Subsection** is the paragraph, subparagraph, or point within the article.

**Original Legal Text** is the verbatim quotation from the legislative text. The primary verification field — allows any lawyer or auditor to check that the annotation faithfully represents the provision.

**Regulation URI** is the stable identifier of the legislative instrument, preferably an ELI URI (e.g., `https://eur-lex.europa.eu/...`). Converts norms into linked data interoperable with EUR-Lex.

---

## Annotation Metadata

**Extraction Method** is the procedure by which the annotation was produced: ManualLawyer, ManualAnalyst, LLMExtraction, PatternMatching, or RuleBased. Fundamental for scientific reproducibility and governance.

**Confidence Score** is the annotator's certainty (0.0–1.0). Allows quantifying legal ambiguity.

**Legal Review Status** is the validation state: Approved, PendingReview, or NotReviewed.

**Annotator** is the identifier of the person who created the annotation.

**Annotation Date** is the date the annotation was created.

**Last Reviewed Date** is the date of the most recent legal review.

---

## NORMA Ontology (TBox)

### Overview

The TBox is in `ontology/` in two serialisation formats:

| File | Format | Use |
|------|--------|-----|
| `norma-ontology-v1.ttl` | Turtle (canonical) | Reference, version control, human editing |
| `norma-ontology-v1.rdf` | RDF/XML | Protégé, OWLAPI-based tools, SWRL engines |

**Ontology IRI:** `https://w3id.org/norma-ontology`  
**Preferred prefix:** `norma:` → `https://w3id.org/norma-ontology#`  
**Version:** 1.0 · **License:** CC BY 4.0

### Design Principle

The TBox has two layers:

- **Shortcut literal layer** — the set of data properties used by the pipeline. These carry plain-text values read directly from BPMN annotation fields (e.g., `norma:agentText`, `norma:fromArticle`). This layer is always populated by the pipeline.
- **Extended semantic layer** — a richer vocabulary aligned with PROV-O, ELI (European Legislation Identifier), and OWL-Time. This layer supports federation with legal data ecosystems but is not instantiated by the pipeline.

The TBox is derived strictly from the element template:
- **Dropdown fields** → OWL classes + `owl:NamedIndividual` (oneOf enumeration)
- **Free-text fields** → `owl:DatatypeProperty` (`xsd:string` or `xsd:date`)
- **Structural roles** → `owl:Class` (anchors for ABox individuals)

### Classes

#### Structural Classes

| Class | Role |
|-------|------|
| `norma:RegulativeNorm` | Root class for content carried by BPMN task elements |
| `norma:LegalCondition` | Content carried by BPMN exclusive gateway elements |
| `norma:LegalAgent` | The bearer of a norm — who must/must not/may act |
| `norma:LegalObject` | The entity on which the prescribed action is performed |
| `norma:LegalSource` | The legislative document from which a norm is extracted |
| `norma:ComplianceCriticality` | Risk level of non-compliance (`Critical/High/Medium/Low`) |

#### Deontic Modality Classes *(subclasses of RegulativeNorm)*

| Class | Operator |
|-------|----------|
| `norma:Obligation` | MUST |
| `norma:Prohibition` | MUST NOT |
| `norma:Permission` | MAY |
| `norma:Recommendation` | SHOULD |
| `norma:NegativeRecommendation` | SHOULD NOT |
| `norma:ConstitutiveRule` | IS / COUNTS AS |

#### Named Individuals

**Binding Force:** `norma:HardLaw` · `norma:SoftLaw` · `norma:InternalPolicy` · `norma:Contractual`

**Risk Level:** `norma:Critical` · `norma:High` · `norma:Medium` · `norma:Low`

**Norm Status:** `norma:Active` · `norma:UnderReview` · `norma:Disputed` · `norma:Superseded` · `norma:NotYetInForce`

**Extraction Method:** `norma:ManualLawyer` · `norma:ManualAnalyst` · `norma:LLMExtraction` · `norma:PatternMatching` · `norma:RuleBased`

**Legal Review:** `norma:Approved` · `norma:PendingReview` · `norma:NotReviewed`

### Object Properties

| Property | Domain | Range | Meaning |
|----------|--------|-------|---------|
| `norma:hasLegalAgent` | RegulativeNorm | LegalAgent | Who bears the norm |
| `norma:isLegalAgentOf` | LegalAgent | RegulativeNorm | Inverse of `hasLegalAgent` |
| `norma:hasObject` | RegulativeNorm | LegalObject | Object of the prescribed action |
| `norma:hasLegalSource` | RegulativeNorm | LegalSource | Provenance link |
| `norma:hasBindingForce` | RegulativeNorm | BindingForce | Legal weight |
| `norma:hasComplianceCriticality` | RegulativeNorm | ComplianceCriticality | Non-compliance risk level |
| `norma:hasNormStatus` | RegulativeNorm | NormStatus | Lifecycle status |
| `norma:hasExtractionMethod` | RegulativeNorm | ExtractionMethod | How annotation was produced |
| `norma:hasReviewStatus` | RegulativeNorm | ReviewStatus | Review state |
| `norma:relatesTo` | RegulativeNorm | RegulativeNorm | Cross-reference between norms |

### Data Properties

| Property | Type | Source field |
|----------|------|-------------|
| `norma:deonticId` | xsd:string | `compliance_deonticId` *(auto-generated if blank)* |
| `norma:normStatement` | xsd:string | `compliance_normStatement` |
| `norma:agentText` | xsd:string | `compliance_agent` |
| `norma:actionText` | xsd:string | `compliance_action` |
| `norma:objectText` | xsd:string | `compliance_object` |
| `norma:factStatement` | xsd:string | `compliance_factStatement` |
| `norma:conditionTrigger` | xsd:string | `compliance_triggerCondition` |
| `norma:jurisdiction` | xsd:string | `compliance_jurisdiction` |
| `norma:effectiveDate` | xsd:date | `compliance_effectiveDate` |
| `norma:deadline` | xsd:date | `compliance_deadline` |
| `norma:exception` | xsd:string | `compliance_exception` |
| `norma:sanction` | xsd:string | `compliance_sanction` |
| `norma:fromRegulation` | xsd:string | `compliance_regulation` |
| `norma:fromArticle` | xsd:string | `compliance_article` |
| `norma:fromParagraph` | xsd:string | `compliance_paragraph` |
| `norma:originalText` | xsd:string | `compliance_originalText` |
| `norma:sourceURI` | xsd:anyURI | `compliance_regulationURI` |
| `norma:confidenceScore` | xsd:decimal | `compliance_confidence` |
| `norma:annotator` | xsd:string | `compliance_annotator` |
| `norma:annotationDate` | xsd:date | `compliance_annotationDate` |
| `norma:lastReviewDate` | xsd:date | `compliance_lastReviewDate` |
| `norma:conditionStatement` | xsd:string | `gw_conditionStatement` |
| `norma:trueBranchLabel` | xsd:string | `gw_trueBranch` |
| `norma:falseBranchLabel` | xsd:string | `gw_falseBranch` |

---

## Knowledge Graph (ABox)

### What the Pipeline Produces

The pipeline generates an **ABox** — a Turtle file that imports the TBox and declares all individuals as OWL named individuals:

| Individual type | Minted from | IRI pattern |
|-----------------|-------------|-------------|
| Norm | `compliance_deonticId` (or auto-generated) | `{abox_iri}#{slug(deontic_id)}` |
| Agent | `compliance_agent` | `{abox_iri}#Agent_{slug(label)}` |
| Legal Object | `compliance_object` | `{abox_iri}#Object_{slug(label)}` |
| Legal Source | `compliance_regulation` | `{abox_iri}#Regulation_{slug(label)}` |

where `abox_iri` is `https://w3id.org/norma-abox/{pack}` (e.g., `https://w3id.org/norma-abox/eu-ai-act`).

The deontic ID is auto-generated when the annotator leaves `compliance_deonticId` blank:

```
Pattern: {PREFIX}_{slug(BPMN_element_name)}
Prefixes: OBL_ (obligation), PRH_ (prohibition), PER_ (permission),
          REC_ (recommendation), REC_NOT_ (negative recommendation), FCT_ (fact)

Example: task named "Mark synthetic content" with type "obligation"
         → OBL_Mark_synthetic_content
```

The same agent, object, or regulation appearing across multiple BPMN files within the same pack is resolved to a single individual.

### Startup Auto-Build

The **web application auto-builds the ABox and extracts all rules at startup** — no manual build step is required. On startup, `app/main.py` scans every subfolder of `regulations/`:

1. Reads all `*.bpmn` files in `regulations/{pack}/bpmn/`
2. Builds the ABox live via `parse_bpmn_folder` → `to_json` → `to_turtle`
3. Extracts `RuleIR` objects via DFS path enumeration
4. Tags each rule with its source BPMN filename (`rule.source`)
5. Loads the ABox and TBox into a pyoxigraph in-memory SPARQL store

If the live build fails, the app falls back to a pre-built `*.abox.ttl` file in the pack folder.

### CLI Pipeline (batch use)

```bash
# Build a regulation pack → generates <pack>.json + <pack>.abox.ttl
python norma_build.py regulations/eu-ai-act/

# Skip entity label normalization
python norma_build.py regulations/eu-ai-act/ --no-normalize

# Generate a normalization override template, then apply it
python norma_build.py regulations/eu-ai-act/ --template overrides.json
python norma_build.py regulations/eu-ai-act/ --override overrides.json
```

### Normalization

When the same regulation or agent is written inconsistently across files ("IA Act", "ia act", "EU AI Act"), the normalizer resolves variants to a single canonical label before generating the ABox. The similarity threshold is configurable (default 0.82).

### Visualizing the KG

- **NORMA web app**: open the *Knowledge Graph* panel to see the D3.js force-directed graph. Click any node to inspect its properties.
- **Protégé**: open `norma-ontology-v1.rdf` as the TBox, then File → Merge Ontology → select the ABox Turtle file.
- **Apache Jena / Fuseki**: load both TBox and ABox; SPARQL 1.1 endpoint available.

---

## SWRL Rules

### What SWRL Rules Express

SWRL (Semantic Web Rule Language) rules encode the **norm applicability logic** derived from the execution paths through the BPMN. The BPMN is reduced to a directed graph where only three node types are preserved: `startEvent`, `endEvent`, and `exclusiveGateway`. Tasks are accumulated on the edges between these nodes.

A DFS traversal from the start event to each end event enumerates every distinct execution scenario. Each path from start to end becomes one `RuleIR` object and one SWRL rule.

**Rule structure:**

```
BODY:  [condition_A = TRUE] ∧ [condition_B = FALSE] ∧ ...
HEAD:  norma:Obligation(:OBL_X)
       norma:isLegalAgentOf(:Agent_AI_provider, :OBL_X)
       norma:hasObject(:OBL_X, :Object_synthetic_content)
       norma:fromArticle(:OBL_X, "50")
       ...
```

The rule body contains boolean data atoms derived from gateway `gw_conditionStatement` annotations. The rule head contains:
- **ClassAtom**: asserts the OWL class of the norm individual (e.g., `norma:Obligation(:OBL_X)`) so that a SWRL reasoner can infer the deontic modality without the ABox.
- **RelationAtoms**: object-property assertions linking the norm to its agent, object, binding force, and risk level.
- **DataAtoms**: data-property assertions (article, paragraph, regulation, agent text, action text, object text, source URI).

### Unconditional Norms

BPMN paths with no exclusive gateways produce rules with an empty body. These **unconditional norms** are not exported as SWRL rules — they are fully declared in the ABox and no rule is needed to derive them. The SWRL exporter silently skips them.

### Condition Value Matching

When a SWRL rule fires depends on the boolean value assigned to each gateway condition. The extractor resolves condition values as follows:

1. If the sequence flow label exactly matches the gateway's `gw_trueBranch` annotation → `true`
2. If the sequence flow label exactly matches `gw_falseBranch` → `false`
3. Fallback: the label is in `{"yes", "true", "1", "sim", "ja", "oui", "approved"}` → `true`; otherwise `false`

This handles both default Camunda labels ("Yes"/"No") and custom branch labels ("Approved"/"Rejected").

### Rule Intermediate Representation

`RuleIR` (`norma/rules/ir.py`) is the internal representation of one rule:

| Field | Type | Description |
|-------|------|-------------|
| `rid` | `str` | Rule identifier (e.g., `r1`, `r2`, …) |
| `conditions` | `Tuple[Condition, ...]` | SWRL body — gateway boolean predicates |
| `relations` | `Tuple[RelationAtom, ...]` | SWRL head — object-property assertions |
| `data_atoms` | `Tuple[DataAtom, ...]` | SWRL head — data-property assertions |
| `class_atoms` | `Tuple[ClassAtom, ...]` | SWRL head — rdf:type assertions for norm individuals |
| `actions` | `Tuple[Action, ...]` | Auxiliary summary labels (not exported to SWRL) |
| `source` | `str` | Source BPMN filename (e.g., `test.bpmn`) |

Each `Condition` has a `predicate` (the `gw_conditionStatement` slug, kind `"rules"`), a `subject` (variable, kind `"var"`), and a boolean `value`.

Each `RelationAtom` has a `predicate` (kind `"tbox"`), a `subject`, and an `object`, all of kind `"abox"` or `"tbox"`.

Each `ClassAtom` has a `class_ref` (kind `"tbox"`, e.g., `"Obligation"`) and a `subject` (kind `"abox"`, the norm individual).

### Generating SWRL Rules (CLI)

```bash
# Produces <file>.swrl.owl next to the input BPMN
python norma_rules.py regulations/eu-ai-act/bpmn/test.bpmn

# Explicit output path
python norma_rules.py regulations/eu-ai-act/bpmn/test.bpmn outputs/rules.swrl.owl
```

### Loading SWRL Rules in Protégé

1. Open the TBox (`ontology/norma-ontology-v1.rdf`) in Protégé.
2. File → Merge Ontology → select the ABox `.ttl`.
3. File → Merge Ontology → select the SWRL `.swrl.owl` file.
4. Activate the SWRL tab (View → Tabs → SWRL).
5. Run the Drools/Pellet reasoner to materialise inferences.

---

## SPARQL Queries

### Running Queries

The NORMA web app exposes a full **SPARQL 1.1 endpoint** backed by pyoxigraph, one store per regulation pack.

- **In-app**: open the *SPARQL* panel — use the preset library or write your own query.
- **GET**: `GET /api/sparql/{pack}?query=SELECT+...`
- **POST**: `POST /api/sparql/{pack}` with the SPARQL query string as the request body.
- **curl**:
  ```bash
  curl -X POST http://localhost:8000/api/sparql/eu-ai-act \
    -H "Content-Type: text/plain" \
    --data "SELECT * WHERE {?s ?p ?o} LIMIT 10"
  ```

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

SELECT ?agent ?norm ?article
WHERE {
  ?norm a norma:Obligation ;
        norma:hasBindingForce norma:HardLaw ;
        norma:isLegalAgentOf ?agent ;
        norma:fromArticle ?article .
}
```

**All norms applicable to a given agent:**
```sparql
PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?norm ?type ?action ?article
WHERE {
  VALUES ?type { norma:Obligation norma:Prohibition norma:Permission }
  ?norm a ?type ;
        norma:agentText ?agent ;
        norma:actionText ?action ;
        norma:fromArticle ?article .
  FILTER(CONTAINS(LCASE(?agent), "ai provider"))
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
# From the project root
uvicorn app.main:app --reload
```

Open `http://localhost:8000`. The app **automatically builds the knowledge graph and extracts all rules** for every regulation pack found in `regulations/` at startup. No separate build step is needed.

### UI Panels

| Panel | What it does |
|-------|-------------|
| **Home** | Landing page — overview, architecture, pack summary |
| **Upload** | Upload a `.bpmn` file to create a new pack on-the-fly |
| **Norm Annotations** | Browse every annotated BPMN element with all template fields. Supports in-browser editing (changes are in-memory). |
| **Knowledge Graph** | D3.js force-directed graph of the ABox. Nodes are colour-coded by type (norms, agents, objects, sources, conditions). Click a node to inspect its properties. |
| **SPARQL** | Full SPARQL 1.1 editor with preset library, results table, and raw JSON toggle |
| **ABox** | Turtle source viewer + download buttons (`.ttl` and `.rdf`) |
| **Camunda Template** | Download link + installation guide + full field reference |

### API Endpoints

#### Pack discovery and content

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web application (HTML) |
| `GET` | `/api/packs` | List all loaded regulation packs |
| `GET` | `/api/pack/{pack}/abox` | ABox Turtle source text |
| `GET` | `/api/pack/{pack}/swrl` | SWRL OWL/XML text (if pre-generated) |
| `GET` | `/api/pack/{pack}/download/abox` | Download ABox as Turtle (`.ttl`) |
| `GET` | `/api/pack/{pack}/download/abox-rdf` | Download ABox as RDF/XML (`.rdf`) |
| `GET` | `/api/pack/{pack}/download/swrl` | Download SWRL OWL file |

#### Norm annotations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/pack/{pack}/norms` | All annotated elements — every template field, plus minimal triggering conditions |
| `PATCH` | `/api/pack/{pack}/norm/{norm_id}` | Update template fields for one norm (in-memory) |

#### Norm evaluation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/pack/{pack}/conditions` | List all unique gateway conditions (predicate name + human-readable label) |
| `POST` | `/api/pack/{pack}/evaluate` | Evaluate a condition assignment → applicable norms |

The `/evaluate` endpoint accepts a JSON body mapping condition predicate names to boolean values:
```json
{ "GenerationOfSyntheticContent": true, "SystemIsHighRisk": false }
```
A rule matches when **all** its conditions are answered and satisfied. Each unique norm is returned at most once — deduplicated across all matched paths. The response includes the norm's agent, action, object, regulation, article, paragraph, binding force, risk level, and source BPMN file.

#### Knowledge graph visualisation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/pack/{pack}/graph` | D3.js-ready `{nodes, edges}` JSON for the force graph |

#### SPARQL

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sparql/{pack}` | SPARQL 1.1 query via `?query=` param |
| `POST` | `/api/sparql/{pack}` | SPARQL 1.1 query via request body |
| `GET` | `/api/sparql-presets` | Curated preset query library |

#### Upload and tools

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload a `.bpmn` file — builds ABox + SWRL on-the-fly |
| `GET` | `/api/download/template` | Download Camunda element template JSON |

### Norm Annotations Endpoint Detail

`GET /api/pack/{pack}/norms` returns one entry per annotated BPMN element. The `conditions` field of each norm entry shows the **minimal triggering conditions**: the intersection of condition-sets across all rules that contain that norm. Only conditions that are required on every path leading to the norm are shown — this gives the tightest condition set that always triggers the norm regardless of which path is taken.

---

## Quick Start

### Step 1 — Install the Camunda element template

Copy `camunda-template/camunda8-compliance-template.json` to the Camunda Modeler templates folder (see [Installation](#installation) above) and restart Modeler.

### Step 2 — Annotate a BPMN process

Open or create a BPMN file in Camunda Modeler. For each task or gateway that carries a legal norm:

1. Select the element.
2. In the Properties Panel, choose **NORMA — Legal Compliance Annotation** from the template dropdown.
3. Set **Element Type** to `task` (for norms) or `exclusiveGateway` (for conditions).
4. Fill in the fields.

Save the file inside the `bpmn/` subfolder of a regulation pack:

```
regulations/my-regulation/bpmn/my-norms.bpmn
```

### Step 3 — Start the web application

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000`. The app detects the new BPMN file at startup, builds the knowledge graph, and extracts all rules automatically. No separate build step is needed.

### Step 4 — Explore in the web app

- **Norm Annotations** panel: browse every annotated element with all template fields.
- **Knowledge Graph** panel: interactive force-directed graph.
- **SPARQL** panel: run queries against the SPARQL store.
- **Conditions** → **Evaluate**: select which gateway conditions hold and see which norms apply.

---

## Example — EU AI Act

Ready-to-use BPMN files are in `regulations/eu-ai-act/bpmn/`:

| File | Content |
|------|---------|
| `test.bpmn` | Full annotated example with multiple norms, gateways, and conditions |
| `art50-art95.bpmn` | Art. 50 transparency obligations and Art. 95 codes of practice |

Start the app and the EU AI Act pack loads automatically:

```bash
uvicorn app.main:app --reload
# → [norma] Loaded: eu-ai-act — N rule(s)
```

To generate the SWRL file independently:

```bash
python norma_rules.py regulations/eu-ai-act/bpmn/test.bpmn
# → regulations/eu-ai-act/bpmn/test.swrl.owl
```

---

## Licence

CC BY 4.0 — Sheyla Leyva-Sánchez et al.
