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

The NORMA annotation template is applied directly inside Camunda Modeler to BPMN tasks and exclusive gateways. Each annotated element becomes a node in the NORMA knowledge graph. This section describes every field in the template, organised by section, explaining what it captures and why it is necessary.

---

## Element Type

The template applies to two structurally different kinds of BPMN elements, and the first field makes that distinction explicit.

**Element Type** determines whether the element being annotated is a task or an exclusive gateway. A task represents a norm: something a legal role must do, must not do, may do, or should do. An exclusive gateway represents a legal condition: a yes/no question whose answer determines which norms are applicable in a given situation. This field controls the visibility of all other fields in the template and is the entry point of the entire annotation.

---

## Norm Content

This section captures the substantive content of the norm. It is the semantic core of the annotation — the information that defines what the law prescribes, to whom, on what, and with what legal weight.

**Deontic Modality** specifies the modal operator of the norm. In standard deontic logic every norm establishes a normative relation between a subject and an action through one of the following operators: obligation (must be done), prohibition (must not be done), permission (may be done), recommendation (should be done), negative recommendation (should not be done), or constitutive rule (defines what counts as what in the legal order). This field determines how the norm individual is classified in the knowledge graph and which properties are assigned to it.

**Norm Statement** is a plain-language restatement of the norm written by the annotator. It is not parsed automatically by the pipeline. Its function is to provide the auditable bridge between the formal annotation and the legal intention behind it, allowing a lawyer or auditor to verify that the formalisation correctly represents the original provision.

**Responsible Party (Who)** is the legal role that is the subject of the norm — the entity that must, must not, may, or should act. It is expressed as an abstract role exactly as it appears in the law, not as a concrete organisation: AI Provider, Data Controller, Manufacturer, Deployer. This is the WHO of the WHO–WHAT–ON-WHAT structure that formalises every regulative norm. The pipeline generates with this value an Agent entity shared across all norms that reference the same role within the regulation pack.

**Legal Action (What)** is the action that the norm prescribes, prohibits, permits, or recommends, expressed as a verb phrase in the infinitive: establish, disclose, deploy, mark, notify. This is the WHAT of the structural triple. It is expressed as free text because the vocabulary of legal actions varies enormously across regulations and cannot be enumerated in advance.

**Legal Object / Target (On What)** is the entity on which the action falls — the system, resource, data, or document that is affected by the norm. Examples include personal data, AI system, audit log, risk management system. This is the ON-WHAT of the structural triple. The pipeline generates with this value a Legal Object entity shared across norms that reference the same object.

**Constitutive Rule / Fact Statement** only appears when the modality is set to Constitutive Rule / Fact. Unlike regulative norms, constitutive rules do not prescribe behaviour but establish legal classifications: under what conditions a system is high-risk, what counts as data processing, what entity counts as an AI provider. This field captures those declarations in plain language. A separate field is necessary because the semantic structure of constitutive rules is fundamentally different from regulative norms — they have no WHO, WHAT, or ON-WHAT.

**Binding Force** captures the legal weight of the norm. Hard law is directly enforceable and its breach carries formal legal consequences. Soft law encompasses guidelines, standards, and codes of conduct that orient behaviour without legally obliging it. Internal policy and contractual obligation operate in sub-regulatory domains. This field is essential for any organisation that needs to distinguish which norms are legally mandatory and which are recommendations, and for the reasoning system to treat each category differently.

---

## Legal Condition

This section is active only when the element is an exclusive gateway. It captures the legal condition that determines which branch of the process applies and therefore which norms are relevant.

**Condition Statement** is the legal question evaluated at the gateway, phrased so that it admits a yes or no answer. For example: Does the system generate synthetic content? Is the AI system classified as high-risk under Annex III? This question becomes the antecedent of the automatic reasoning rules — its boolean value determines which norms are inferred as applicable.

**True Branch Label** is the display label on the outgoing flow when the condition is satisfied, typically Yes. The pipeline needs this label to correctly map the graph arc to the true value of the condition in the reasoning rules.

**False Branch Label** is the display label on the outgoing flow when the condition is not satisfied, typically No. It serves the same purpose as the true branch label but for the false value.

---

## Scope and Temporal

This section defines the boundaries of the norm's applicability — territorial, temporal, and circumstantial. It allows the system to filter norms by context and to manage the temporal evolution of regulation.

**Trigger Condition** is a plain-language description of the circumstances under which the norm applies: when processing biometric data, upon deployment in a high-risk context. It is not processed as an automatic rule. Its function is to document the annotator's interpretive reasoning, providing auditable context that explains why the norm was annotated as applying in certain circumstances.

**Jurisdiction** is the territorial scope in which the norm has legal force: EU, UK, US-CA, global. It allows the system to manage scenarios where regulations from different jurisdictions coexist in the same knowledge graph and to filter norms by the territory in which an organisation operates.

**Effective Date** is the date from which the norm is legally in force. It enables temporal reasoning: determining which norms were applicable at a given moment in time, identifying norms not yet in force, and detecting compliance obligations that predate the availability of the system.

**Deadline / Sunset Date** is the compliance deadline or expiry date of the norm. It is useful for obligations with implementation or transposition deadlines and for identifying norms that are no longer applicable.

**Norm Status** captures the lifecycle state of the norm. Norms are not static: they are adopted, reviewed, challenged, and repealed. This field allows the system to distinguish active norms from obsolete ones, preventing the reasoner from inferring obligations based on repealed provisions. Norms with status Superseded are retained in the knowledge graph for historical traceability.

---

## Consequences and Exceptions

This section captures information about the consequences of non-compliance and the exceptions to the norm's applicability. It does not participate directly in automatic reasoning but is essential for the operational use of the knowledge graph.

**Exception / Carve-out** records the conditions under which the norm expressly does not apply. In law every norm can have exceptions that limit its scope. This field captures them in free text because exceptions vary enormously in structure across regulations. The system stores them in the knowledge graph as a property of the norm. Their formalisation into negation rules belongs to the defeasible logic layer, which operates above this pipeline.

**Sanction / Consequence of Breach** is the legal consequence of non-compliance where known: administrative fines, civil liability, supervisory sanctions. It does not participate in automatic reasoning but is essential information for an organisation to assess the actual risk of each norm and prioritise its compliance efforts.

**Compliance Criticality** is the operational severity of non-compliance from the perspective of the organisation. It is conceptually distinct from binding force: an internal policy can be of critical operational severity, and a hard-law norm can be of low criticality if the breach risk is minimal in practice. This field allows compliance officers to prioritise which norms to address first.

---

## Legal Source

This section captures the legislative provenance of the norm — where it comes from, where exactly it sits in the legal text, and how to access the source. It is the section that guarantees the traceability of the system.

**Regulation Name** is the full name of the legislative instrument from which the norm is derived: EU AI Act, GDPR, DSA. The pipeline uses this name to create a Legal Source entity shared across all norms in the same regulation pack. Consistency in the name across different BPMN files within the same pack is important — the pipeline normaliser resolves variants automatically, but consistency is always preferable.

**Article / Section** is the article or section number within the legislative instrument. Together with the paragraph, it forms the exact legislative locator. This locator appears in every conclusion inferred by the system — every automatically derived obligation carries its legislative traceability embedded within it, which is a baseline requirement for any compliance system with legal validity.

**Paragraph / Subsection** is the paragraph, subparagraph, or point within the article. It enables fine-grained provenance: a norm is traceable not just to an article but to the specific paragraph that mandates it. This level of precision is especially important in regulations such as the AI Act, where different paragraphs of the same article impose different obligations on different actors.

**Original Legal Text** is the verbatim quotation from the legislative text that supports the annotation. It is the primary verification field of the system: it allows any lawyer or auditor to check directly that the formalised annotation faithfully represents the original legal provision. Without this field the traceability chain is incomplete.

**Regulation URI** is the stable, dereferenceable identifier of the legislative instrument, preferably an ELI (European Legislation Identifier) URI where available. It converts the norms in the knowledge graph into linked data — Legal Source entities can be connected directly to repositories such as EUR-Lex, making the graph interoperable with the European legal data ecosystem.

---

## Annotation Metadata

This section does not describe the norm itself but the annotation. It captures who produced it, how, with what degree of certainty, and in what governance state it currently sits.

**Extraction Method** is the procedure by which the annotation was produced. It distinguishes between manual annotation by a lawyer, manual annotation by an analyst, extraction by a language model, pattern matching, and rule-based extraction. It is fundamental for scientific reproducibility and for operational governance: annotations produced by automatic methods must receive legal review before being used in production reasoning.

**Confidence Score** is the annotator's certainty in their interpretation of the legal provision, expressed on a scale from 0.0 to 1.0. Legal text is frequently ambiguous, and this field allows that ambiguity to be quantified. The pipeline uses low values to flag annotations that require mandatory review before being activated in the reasoning system. Without this field all annotations are treated as equally certain, which is scientifically incorrect.

**Legal Review Status** is the validation state of the annotation by legal counsel: reviewed and approved, pending legal review, or not reviewed. It allows an organisation to activate in its reasoning system only norms that have passed legal review, ensuring that the production knowledge graph contains only validated knowledge.

**Annotator** is the name or identifier of the person who created the annotation. Together with the annotation date and confidence score, it completes the provenance record of the annotation and makes it possible to contact the annotator to resolve interpretive doubts or to update the annotation after a legislative amendment.

**Annotation Date** is the date on which the annotation was created. It makes it possible to identify annotations that may have become outdated following a subsequent amendment to the regulation.

**Last Reviewed Date** is the date of the most recent legal review. If this date precedes a known amendment to the regulation, the annotation may need updating. This field underpins the long-term maintenance of the knowledge graph — without it there is no systematic way to identify which annotations need revision when the law changes.

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
