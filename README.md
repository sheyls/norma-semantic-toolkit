# NORMA Semantic Toolkit

[![Ontology DOI](https://img.shields.io/badge/Ontology%20DOI-10.5281%2Fzenodo.19765302-blue)](https://doi.org/10.5281/zenodo.19765302)
[![Zenodo Community](https://img.shields.io/badge/Zenodo-NORMA%20Community-blue?logo=zenodo)](https://zenodo.org/communities/norma)
[![Code License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-0b7285.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Content License: CC BY 4.0](https://img.shields.io/badge/Content-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-97%20passing-brightgreen)](#testing)
[![OWL 2 DL](https://img.shields.io/badge/Ontology-OWL%202%20DL-orange)](https://www.w3.org/TR/owl2-overview/)
[![Ontology Docs](https://img.shields.io/badge/Docs-NORMA--O%20Ontology-navy)](https://w3id.org/def/norma-o)

**NORMA** is an open semantic resource for the formal representation and computational processing of legal norms extracted from regulatory documents. It combines an OWL 2 DL ontology, a structured annotation methodology based on BPMN, an automated knowledge-graph construction pipeline, and a SWRL rule generation engine. The result is a self-consistent, queryable, and reasoner-ready knowledge graph that faithfully instantiates the ontology from annotated process models.

> Sheyla Leyva-Sánchez · Ontology Engineering Group, Universidad Politécnica de Madrid · Code: Apache-2.0 · Ontology and research artifacts: CC BY 4.0  
> Ontology DOI: [10.5281/zenodo.19765302](https://doi.org/10.5281/zenodo.19765302) · All resources: [zenodo.org/communities/norma](https://zenodo.org/communities/norma)

---

## Table of Contents

- [Overview](#overview)
- [Motivations and Design Goals](#motivations-and-design-goals)
- [Repository Structure](#repository-structure)
- [The NORMA Ontology (TBox)](#the-norma-ontology-tbox)
- [Annotation Methodology](#annotation-methodology)
- [Knowledge Graph Construction Pipeline](#knowledge-graph-construction-pipeline)
- [SWRL Rule Generation](#swrl-rule-generation)
- [SPARQL Interface](#sparql-interface)
- [Web Application](#web-application)
- [Example — EU AI Act](#example--eu-ai-act)
- [Quick Start](#quick-start)
  - [Option A — Docker (zero configuration)](#option-a--docker-zero-configuration)
  - [Option B — Local install](#option-b--local-install)
  - [Option C — Reproduce the paper results](#option-c--reproduce-the-paper-results)
- [Step-by-Step Tutorial: From a blank BPMN to a knowledge graph](#step-by-step-tutorial-from-a-blank-bpmn-to-a-knowledge-graph)
- [Reproducibility](#reproducibility)
- [Alignment with Established Standards](#alignment-with-established-standards)
- [Constraints and Limitations](#constraints-and-limitations)
- [Requirements](#requirements)
- [Testing](#testing)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)

---

## Overview

Regulatory compliance requires understanding which legal obligations, prohibitions, permissions, and recommendations apply to a given agent or system under a specific set of conditions. This determination is non-trivial when norms are scattered across lengthy legal texts and their applicability depends on branching conditions (e.g., whether an AI system is high-risk, whether a controller processes biometric data).

NORMA addresses this by providing:

1. **An OWL 2 DL ontology** (`norma-o`) that formally defines the vocabulary of legal norms, their structural components, provenance metadata, and condition-triggering mechanisms.
2. **A Camunda 8 element template** that enables legal experts to annotate BPMN process diagrams with structured normative metadata directly inside a standard process modelling tool — no RDF or SPARQL knowledge required.
3. **An automated construction pipeline** (`norma_engine`) that transforms annotated BPMN files into a validated OWL ABox, resolving entity references and enforcing ontological constraints.
4. **A SWRL rule generator** that derives condition-aware inference rules from the gateway logic embedded in the BPMN, enabling norm determination under a reasoner.
5. **A REST API and web application** for interactive exploration, SPARQL querying, norm editing, SWRL inspection, and artifact download.

The pipeline is end-to-end: from a BPMN file annotated by a legal expert to a downloadable, reasoner-ready OWL knowledge graph in a single command.

```
Annotated BPMN diagram(s)
        │
        ▼
  norma-build <regulation-folder>/
        │
        ├──▶  <pack>.abox.ttl    OWL ABox (named individuals, all triples)
        ├──▶  <pack>.swrl.owl    SWRL rules (conditional norm activation)
        ├──▶  <pack>.json        JSON intermediate (for inspection/debugging)
        │
        └──▶  REST API / Web UI  SPARQL · graph · norm editor · download
```

---

## Motivations and Design Goals

**Ontological fidelity.** Every individual in the ABox is an exact instantiation of a TBox class; every property triple respects the declared domain, range, and cardinality constraints. The pipeline enforces this automatically — ghost properties and domain violations cannot enter the graph.

**Separation of annotation from reasoning.** Structural facts about norms (agent, action, object, source, provenance) are asserted in the ABox. Conditional applicability is captured separately as SWRL rules whose bodies encode gateway truth values and whose heads assert the deontic type of the activated norm. This separation keeps the ABox stable and lets the SWRL layer be regenerated independently.

**Reuse of established vocabularies.** The ontology aligns with ELI (European Legislation Identifier) for legal sources and jurisdiction, PROV-O for annotation provenance, FOAF for agent typing, and SKOS for extensible controlled vocabularies. This maximises interoperability without reinventing existing standards.

**Practical usability.** The annotation interface is a standard Camunda Modeler element template — no RDF tooling is required from the legal expert. The web application allows non-technical users to inspect, query, and export the knowledge graph without writing SPARQL or OWL.

**Deterministic and reproducible.** The pipeline is a pure, stateless transformation of BPMN input to RDF output. Given the same input, every run produces byte-for-byte identical ABox and SWRL files. This is verified by `reproduce.sh` on every commit.

---

## Repository Structure

```
norma-semantic-toolkit/
│
├── norma-ontology/
│   ├── norma-ontology-v1.ttl          # OWL 2 DL ontology (Turtle)
│   ├── norma-ontology-v1.rdf          # OWL 2 DL ontology (RDF/XML)
│   └── norma-o.svg                    # Visual diagram of the ontology
│
├── camunda-template/
│   └── camunda8-compliance-template.json  # Camunda 8 element template
│
├── norma_engine/                      # Core Python package (stdlib only)
│   ├── parsing/
│   │   └── bpmn_parser.py             # BPMN XML → reduced graph (nodes, edges, gateways)
│   ├── kg/
│   │   ├── builder.py                 # ABox Turtle generator
│   │   └── normalizer.py              # Entity label reconciliation (fuzzy + override)
│   ├── rules/
│   │   ├── ir.py                      # Intermediate representation (RuleIR, Atom types)
│   │   └── extractor.py               # Path enumeration (DFS) → SWRL IR
│   ├── exporters/
│   │   ├── swrl.py                    # RuleIR → OWL/XML SWRL serialisation
│   │   └── human_readable.py          # RuleIR → natural-language rule strings
│   └── cli/
│       ├── build.py                   # `norma-build` — full pipeline orchestrator
│       └── rules.py                   # `norma-rules` — standalone SWRL extractor
│
├── regulations/
│   └── eu-ai-act/
│       ├── bpmn/                      # 6 annotated BPMN diagrams (source corpus)
│       ├── entities.json              # Entity reconciliation overrides
│       ├── eu-ai-act.abox.ttl         # Generated ABox (committed)
│       ├── eu-ai-act.swrl.owl         # Generated SWRL rules (committed)
│       └── eu-ai-act.json             # Generated JSON intermediate (committed)
│
├── web-app/
│   ├── backend/                       # FastAPI application
│   │   ├── main.py                    # REST API routes and startup
│   │   ├── services/
│   │   │   ├── pipeline.py            # Build, export, and query orchestration
│   │   │   ├── storage.py             # Pack registry, persistence, and auto-load
│   │   │   └── graphdb.py             # Oxigraph SPARQL store + graph builder
│   │   └── sparql_presets.py          # Curated SPARQL query library
│   └── frontend/                      # React + Vite + D3.js single-page application
│
├── tests/                             # 97 unit and integration tests
│   ├── test_parsing.py
│   ├── test_rules.py
│   ├── test_kg.py
│   ├── test_normalizer.py
│   ├── test_exporters.py
│   ├── test_swrl_case_runner.py
│   └── eu_ai_act_cases.json           # 5 end-to-end SWRL evaluation scenarios
│
├── reproduce.sh                       # Reproducibility script (build + test + determinism check)
├── Dockerfile                         # Multistage build (Node 20 + Python 3.11)
├── docker-compose.yml                 # Local development stack
├── docker-compose.prod.yml            # Production stack
└── pyproject.toml                     # Package definition (norma-engine v1.0.0)
```

---

## The NORMA Ontology (TBox)

**IRI:** `https://w3id.org/def/norma-o`  
**Version IRI:** `https://w3id.org/def/norma-o/1.0`  
**Documentation:** [https://w3id.org/def/norma-o](https://w3id.org/def/norma-o)  
**Serialisations:** Turtle (`norma-ontology-v1.ttl`) and RDF/XML (`norma-ontology-v1.rdf`)  
**License:** CC BY 4.0  
**DOI:** [10.5281/zenodo.19765302](https://doi.org/10.5281/zenodo.19765302)  
**Dedicated repository:** [sheyls/NORMA-O](https://github.com/sheyls/NORMA-O)

![NORMA-O ontology diagram](norma-ontology/norma-o.svg)

### Statistics

| Element | Count |
|---|---|
| Classes | 23 |
| Object properties | 33 |
| Datatype properties | 24 |
| Named individuals (TBox controlled vocabulary) | 23 |

### Class Hierarchy

The ontology is organised around three principal clusters:

**Normative content** — the legal norm itself:
- `NormativeContent` ← `RegulativeNorm` ← `Obligation`, `Prohibition`, `Permission`, `Recommendation`, `NegativeRecommendation`
- `NormativeContent` ← `ConstitutiveRule`

**Legal structure** — the components of a norm:
- `LegalAgent`, `LegalAction`, `LegalObject`, `LegalSource`, `LegalSourceExpression`

**Condition and triggering** — the n-ary relation pattern for conditional norm activation:
- `LegalCondition` →`hasTrigger`→ `TriggerEvent` →`activatesNorm`→ `NormativeContent`
- `TriggerEvent` →`hasOutcome`→ `ConditionOutcome` (`TrueOutcome`, `FalseOutcome`, …)
- A property chain shortcut `triggersNorm = hasTrigger ∘ activatesNorm` supports direct querying.

**Provenance** — aligned with PROV-O:
- `AnnotationActivity` (subclass of `prov:Activity`) →`wasAssociatedWith`→ `AnnotatorAgent`
- `NormativeContent` (subclass of `prov:Entity`) →`wasGeneratedBy`→ `AnnotationActivity`

### Controlled Vocabularies (SKOS ConceptSchemes)

Each enumerated dimension is modelled as a SKOS scheme with declared `owl:NamedIndividual` members, allowing open extension without modifying the ontology:

| Scheme | Members |
|---|---|
| `BindingForce` | `HardLaw`, `SoftLaw`, `InternalPolicy`, `Contractual` |
| `NormStatus` | `Active`, `UnderReview`, `Disputed`, `Superseded`, `NotYetInForce` |
| `ComplianceCriticality` | `Critical`, `High`, `Medium`, `Low` |
| `ExtractionMethod` | `ManualLawyer`, `ManualAnalyst`, `LLMExtraction`, `PatternMatching`, `RuleBased` |
| `ReviewStatus` | `Approved`, `PendingReview`, `NotReviewed` |
| `ConditionOutcome` | `TrueOutcome`, `FalseOutcome` (extensible) |

### External Alignments

| Standard | Usage in NORMA |
|---|---|
| **ELI** | `LegalSource ⊑ eli:LegalResource`; `eli:jurisdiction` with `eli:AdministrativeArea` for jurisdiction |
| **PROV-O** | `AnnotationActivity ⊑ prov:Activity`; `NormativeContent ⊑ prov:Entity`; `AnnotatorAgent ⊑ prov:Agent` |
| **FOAF** | Imported for agent-level interoperability; `foaf:Person`, `foaf:Organization`, `foaf:Group` available for instance-level typing |
| **SKOS** | All controlled vocabularies use SKOS `ConceptScheme` / `Concept` structure |
| **BIBO** | `bibo:doi`, `bibo:status` for ontology-level bibliographic metadata |
| **LKIF-Core** | Informative alignments via `rdfs:seeAlso`: `RegulativeNorm` ↔ `lkif:Norm`; `Obligation`, `Prohibition`, `Permission` ↔ LKIF deontic counterparts |

---

## Annotation Methodology

NORMA uses **BPMN (Business Process Model and Notation)** as the annotation surface. Process diagrams are created in [Camunda Modeler 8](https://camunda.com/platform/modeler/) and enriched with normative metadata through a structured element template (Zeebe extension properties).

### Why BPMN?

BPMN is already widely used in compliance and regulatory contexts to represent procedural obligations. Using it as the annotation medium means:
- Legal experts work in a familiar visual environment with explicit control-flow semantics.
- Exclusive gateway conditions directly encode the conditional applicability of norms — no additional formalisation step is needed.
- The process graph provides a machine-readable structure from which SWRL inference rules can be derived automatically.

### Loading the Camunda Template

Before annotating, import the element template into Camunda Modeler:

1. Open Camunda Modeler 8.
2. Go to **File → Templates → Open Templates Folder**.
3. Copy `camunda-template/camunda8-compliance-template.json` into that folder.
4. Restart Modeler. The **NORMA Norm Annotation** template will appear in the element properties panel when you select a task.

### Annotation Fields

Each BPMN **task** represents one normative statement. Select a task and choose the NORMA template to fill in:

| Field | Ontology mapping | Type |
|---|---|---|
| `compliance_deonticType` | `rdf:type` → `norma:Obligation` / `Prohibition` / etc. | Controlled vocab |
| `compliance_deonticId` | `norma:deonticId` | String (auto-generated if blank) |
| `compliance_normStatement` | `norma:normStatement` | Free text |
| `compliance_agent` | `norma:LegalAgent` individual + `norma:hasLegalAgent` | String → IRI |
| `compliance_action` | `norma:LegalAction` individual + `norma:hasLegalAction` | String → IRI |
| `compliance_object` | `norma:LegalObject` individual + `norma:hasLegalObject` | String → IRI |
| `compliance_regulation` | `norma:LegalSource` individual + `norma:hasLegalSource` | String → IRI |
| `compliance_article` | `norma:fromArticle` (norm) + `norma:articleNumber` (source) | String |
| `compliance_bindingForce` | `norma:hasBindingForce` | Controlled vocab |
| `compliance_status` | `norma:hasNormStatus` | Controlled vocab |
| `compliance_riskLevel` | `norma:hasComplianceCriticality` | Controlled vocab |
| `compliance_extractionMethod` | `norma:hasExtractionMethod` | Controlled vocab |
| `compliance_legalReview` | `norma:hasReviewStatus` | Controlled vocab |
| `compliance_jurisdiction` | `eli:jurisdiction` → `eli:AdministrativeArea` | String → IRI |
| `compliance_annotator` | `norma:AnnotatorAgent` individual | String → IRI |
| `compliance_annotationDate` | `norma:annotationDate` | ISO date |
| `compliance_confidence` | `norma:confidenceScore` | Decimal [0, 1] |
| `compliance_originalText` | `norma:originalText` (on source) | Free text |

**Exclusive gateways** carry condition metadata (`gw_conditionStatement`) that the pipeline uses to construct `LegalCondition` and `TriggerEvent` individuals and to build SWRL rule bodies.

---

## Knowledge Graph Construction Pipeline

The `norma_engine` package implements a four-stage pipeline, invoked with a single command:

```bash
norma-build regulations/eu-ai-act/
```

### Stage 1 — BPMN Parsing

`norma_engine.parsing.bpmn_parser` reads all `.bpmn` files in the `bpmn/` subfolder, extracts Zeebe extension properties from task and gateway elements, and constructs a **reduced graph**: a list of annotated nodes, directed edges, and a gateway outgoing-edge index. The parser handles multiple files in a single pass and merges their element lists.

### Stage 2 — Entity Reconciliation

`norma_engine.kg.normalizer` detects near-duplicate entity labels across BPMN files (e.g., `"AI provider"` vs `"AI providers"`) using fuzzy string matching (SequenceMatcher ratio, default threshold 0.82). Canonical labels are selected automatically by frequency and first-seen order, with a fallback to a `KNOWN_ALIASES` table for well-known regulatory terms. Uncertain merges are flagged as warnings so the operator can review them.

An **override file** (`entities.json`, optional) lets you lock specific merges or confirm that two similar labels are intentionally distinct:

```json
{
  "regulation": { "AI Act": "EU AI Act" },
  "_confirmed_separate": [["comply with obligations", "comply with marking obligations"]]
}
```

Generate a template to fill in:

```bash
norma-build regulations/eu-ai-act/ --template overrides.json
# edit overrides.json, then:
norma-build regulations/eu-ai-act/ --override overrides.json
```

### Stage 3 — ABox Construction

`norma_engine.kg.builder` converts reconciled records into a Turtle ABox that:
- Declares all named individuals with correct `rdf:type` assertions.
- Asserts all data and object properties with domain/range compliance.
- Instantiates the n-ary `LegalCondition → TriggerEvent → NormativeContent` pattern for each exclusive gateway and its outgoing branches.
- Creates `AnnotationActivity` individuals linked to each norm, stamping `norma:annotationDate` and `norma:wasAssociatedWithAnnotator`.
- Mints provisional `eli:AdministrativeArea` individuals for jurisdiction strings.
- Imports the TBox (`owl:imports <https://w3id.org/def/norma-o>`), making the ABox self-contained for any OWL reasoner.

### Stage 4 — SWRL Rule Extraction

`norma_engine.rules.extractor` enumerates all paths through the BPMN graph from start event to norm-bearing tasks using depth-first search. For each path, it collects gateway conditions and the norms they activate, constructing a `RuleIR` object:

- **Body:** one `DatavaluedPropertyAtom` per gateway condition on the path (`conditionPredicate(?x, true)` or `(?x, false)`)
- **Head:** one `IndividualPropertyAtom` asserting `norma:activatesNorm` from the trigger event to the applicable norm individual

`norma_engine.exporters.swrl` serialises the IR to OWL/XML SWRL. Unconditional norms (not guarded by any gateway) are fully declared in the ABox and are not emitted as rules — they always apply.

---

## SWRL Rule Generation

SWRL rules encode conditional norm applicability in a standard, reasoner-executable format. Each rule follows this pattern:

**Example rule (EU AI Act, biometric identification):**

```xml
<swrl:Imp>
  <swrl:body>
    <swrl:AtomList>
      <swrl:DatavaluedPropertyAtom>
        <swrl:propertyPredicate rdf:resource="…#Is_the_AI_system_used_for_biometric_purposes"/>
        <swrl:argument1 rdf:resource="…#var_x"/>
        <swrl:argument2 rdf:datatype="xsd:boolean">true</swrl:argument2>
      </swrl:DatavaluedPropertyAtom>
    </swrl:AtomList>
  </swrl:body>
  <swrl:head>
    <swrl:AtomList>
      <swrl:IndividualPropertyAtom>
        <swrl:propertyPredicate rdf:resource="norma:activatesNorm"/>
        <swrl:argument1 rdf:resource="…#TriggerEvent_…"/>
        <swrl:argument2 rdf:resource="…#OBL_Respect_high_risk_obligations"/>
      </swrl:IndividualPropertyAtom>
    </swrl:AtomList>
  </swrl:head>
</swrl:Imp>
```

**Human-readable equivalent (also generated):**

```
Is_the_AI_system_used_for_biometric_purposes(?x, true)
  ⇒ activatesNorm(TriggerEvent_…, OBL_Respect_high_risk_obligations)
```

To evaluate which norms apply to a specific AI system, load the ABox + SWRL into a SWRL-capable reasoner (Pellet, HermiT with SWRL extension), create an individual representing the system, assert the relevant boolean properties, and run the reasoner. The inferred `norma:activatesNorm` triples identify the applicable norms.

The web application's **Evaluate** panel does this directly in the browser: select a regulation pack, toggle yes/no for each condition, and the applicable norms are highlighted immediately.

---

## SPARQL Interface

The web application exposes a SPARQL 1.1 endpoint backed by [Oxigraph](https://github.com/oxigraph/oxigraph). The ABox and TBox are loaded into the same dataset, enabling queries that combine instance-level and schema-level information.

A library of curated preset queries is provided in `web-app/backend/sparql_presets.py`:

| Query | Description |
|---|---|
| All norms | Every norm with binding force, risk level, and article reference |
| Agents per norm | Which agents are bound by each norm |
| Gateway conditions | Legal conditions with their trigger events and activated norms |
| Hard-law obligations | Obligations classified as hard law, grouped by regulation and article |
| Critical-risk norms | Norms marked as critical or high compliance risk |
| Prohibitions | All prohibitions with agent, action, object, and risk level |
| Norms by regulation | All norms grouped by their source regulation |
| Count by type | Summary count of each deontic modality |

Each preset includes commented-out `FILTER` clauses ready to be activated for targeted queries. The SPARQL console in the web app lets you run presets or write free-form queries and download results as CSV.

---

## Web Application

The web application provides a graphical interface for the full artifact stack. It is built with FastAPI (backend) and React + Vite + D3.js (frontend).

**On startup, the EU AI Act knowledge graph is automatically loaded** — no configuration required. Open the app and the corpus is already there, fully queryable.

### Key Features

- **Knowledge graph visualisation** — force-directed graph of all ABox individuals and their semantic relationships. Nodes are colour-coded by ontological type (norms, agents, actions, objects, sources, conditions). `TriggerEvent` reification nodes are collapsed into direct `LegalCondition --when true/false→ Norm` edges for readability.
- **Norm editor** — inline editing of norm metadata (binding force, status, risk level, review status, annotator, annotation date) with immediate ABox regeneration.
- **SWRL viewer** — OWL/XML syntax and human-readable rule display side by side.
- **Evaluate panel** — interactive condition checker: toggle yes/no for each gateway condition and see which norms activate in real time, without a reasoner.
- **SPARQL console** — free-form and preset queries against the Oxigraph store; results downloadable as CSV.
- **Entity reconciliation panel** — review and resolve near-duplicate entity labels, confirm intentional distinctions, and trigger pack rebuilds.
- **Artifact download** — ABox (Turtle and RDF/XML), SWRL (OWL/XML), JSON intermediate, and Camunda element template.
- **Multi-pack support** — official regulation packs (folder-backed, built from BPMN) and user-uploaded BPMN files coexist in the same session.

### REST API (selected endpoints)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/pack/{pack}/abox` | ABox in Turtle |
| `GET` | `/api/pack/{pack}/swrl` | SWRL in OWL/XML |
| `GET` | `/api/pack/{pack}/rules` | Rules as JSON with human-readable forms |
| `GET` | `/api/pack/{pack}/graph` | Graph nodes and edges as JSON |
| `POST` | `/api/pack/{pack}/rebuild` | Rebuild pack from source BPMN |
| `GET/POST` | `/api/sparql/{pack}` | SPARQL 1.1 query endpoint |
| `GET` | `/api/pack/{pack}/conditions` | All gateway conditions with evaluatable predicates |
| `POST` | `/api/pack/{pack}/evaluate` | Evaluate a condition set → applicable norms |
| `POST` | `/api/upload` | Upload a new BPMN file as a user pack |

---

## Example — EU AI Act

The repository includes annotated BPMN models for a fragment of the **EU Artificial Intelligence Act**, covering prohibited practices (Article 5), high-risk system obligations (Articles 8–22), conformity presumption (Article 42), transparency obligations (Article 50), real-world testing (Articles 60–61), and voluntary codes of conduct (Article 95). This serves as the primary end-to-end example.

**Six BPMN process models** are provided in `regulations/eu-ai-act/bpmn/`:

| File | Regulatory scope |
|---|---|
| `diagram GPAI.bpmn` | General-purpose AI model obligations |
| `diagram biometrics .bpmn` | Biometric identification system obligations |
| `diagram criminal purpose.bpmn` | Criminal-purpose profiling norms |
| `diagram cybersecurity exemption.bpmn` | Cybersecurity certification exemptions |
| `diagram generating content.bpmn` | AI-generated content transparency |
| `diagram real time biometrics.bpmn` | Real-time remote biometric identification |

After entity normalisation across diagrams, the pipeline produces:

- **9 unique norms**: 5 obligations, 2 prohibitions, 1 recommendation, 1 negative recommendation
- **15 gateway conditions** across all diagrams, encoding conditional norm applicability
- **13 trigger events** linking conditions to applicable norms
- **16 SWRL rules** derived from conditional paths through the BPMN graphs
- **1 legal source**: `Regulation_EU_AI_Act` with article-level references per norm
- **8 legal actions**, **1 legal agent** (`Agent_AI_provider`), **1 legal object** (`Object_AI_system`)
- **Full provenance** per norm: 9 `AnnotationActivity` individuals → `NORMAAnnotator` → `LegalSource`

The generated ABox (`regulations/eu-ai-act/eu-ai-act.abox.ttl`) is a valid OWL 2 DL ontology importable directly into Protégé or any OWL reasoner.

---

## Quick Start

### Option A — Docker (zero configuration)

Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

```bash
git clone https://github.com/anaigmo/norma-semantic-toolkit.git
cd norma-semantic-toolkit
docker compose up
```

Open [http://localhost:5173](http://localhost:5173). The EU AI Act knowledge graph is pre-loaded automatically.

To stop: `docker compose down`.

### Option B — Local install

Requires Python ≥ 3.10 and Node.js ≥ 20.

**1. Install the core engine**

```bash
git clone https://github.com/anaigmo/norma-semantic-toolkit.git
cd norma-semantic-toolkit
pip install -e .
```

This installs the `norma-engine` package and registers two CLI commands: `norma-build` and `norma-rules`.

**2. Build the EU AI Act knowledge graph**

```bash
norma-build regulations/eu-ai-act/
```

This runs all four pipeline stages and writes three files into `regulations/eu-ai-act/`:
- `eu-ai-act.abox.ttl` — OWL ABox (all named individuals and triples)
- `eu-ai-act.swrl.owl` — SWRL rules (conditional norm activation)
- `eu-ai-act.json` — JSON intermediate (for inspection)

**3. (Optional) Extract SWRL rules for a single BPMN file**

```bash
norma-rules "regulations/eu-ai-act/bpmn/diagram GPAI.bpmn"
```

Output is written alongside the input file as `diagram GPAI.swrl.owl`.

**4. Run the web application**

```bash
# Backend (terminal 1)
pip install -r web-app/backend/requirements.txt
cd web-app && uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend (terminal 2)
cd web-app/frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The `eu-ai-act` pack is pre-loaded.

### Option C — Reproduce the paper results

```bash
pip install -e .
bash reproduce.sh
```

`reproduce.sh` does four things:
1. Regenerates the EU AI Act ABox and SWRL from the source BPMN corpus.
2. Runs the engine test suite (79 tests; the 18 web-app tests need the FastAPI stack and are run separately).
3. Builds the knowledge graph twice in isolated environments.
4. Asserts SHA-256 identity of all output files — both between the two runs (determinism) and against the artifacts committed in this repository, which are snapshotted before step 1 rewrites them.

Expected output ends with:

```
  [OK]   eu-ai-act.abox.ttl  sha256=b37aae65ea29d4e4742a74d56e63456cbf62b6b1c4c2d3c43ffd039e1518a138
  [OK]   eu-ai-act.swrl.owl  sha256=abfedffa2eb1d3d33d19fc3636d573185cf510a86f35a01a79149dd962b6eaf3
  [OK]   eu-ai-act.json  sha256=7ba605cf8fea21c82f2d55e5ebe7384bc7dccba29ae272a27c5754c084b3e0c4

  Reproducibility: PASSED — pipeline is deterministic and the
  committed artifacts match a clean rebuild.
```

---

## Step-by-Step Tutorial: From a blank BPMN to a knowledge graph

This walkthrough takes you from an empty Camunda diagram to a generated ABox and SWRL file in under 10 minutes. You will annotate a simple norm — *"AI providers must comply with transparency obligations"* — conditional on the system generating synthetic content.

### Prerequisites

- Camunda Modeler 8 installed ([download](https://camunda.com/platform/modeler/))
- NORMA engine installed: `pip install -e .`
- NORMA element template loaded (see [Loading the Camunda Template](#loading-the-camunda-template))

### Step 1 — Create the BPMN diagram

1. Open Camunda Modeler and create a new **BPMN diagram**.
2. Add a **Start Event**, an **Exclusive Gateway**, and two outgoing branches.
3. Label the gateway `gw_conditionStatement = "Is the AI system used to generate synthetic content?"`.
4. On the **true** branch, add a **Task** (this will be your norm). Label it: `Comply with transparency obligations`.
5. On the **false** branch, add an **End Event** (no norm applies).
6. Connect the task to an **End Event** on the true branch as well.

Your diagram should look like:

```
[Start] → [Gateway: generates synthetic content?]
               ├── yes → [Task: Comply with transparency obligations] → [End]
               └── no  → [End]
```

### Step 2 — Annotate the task

1. Select the task `Comply with transparency obligations`.
2. In the properties panel, click **+ Template** and choose **NORMA Norm Annotation**.
3. Fill in the fields:

| Field | Value |
|---|---|
| Deontic type | `Obligation` |
| Norm ID | `OBL_transparency_synthetic_content` (or leave blank to auto-generate) |
| Norm statement | `AI providers must label AI-generated synthetic content as such.` |
| Agent | `AI provider` |
| Action | `label synthetic content` |
| Object | `AI system` |
| Regulation | `EU AI Act` |
| Article | `50` |
| Binding force | `HardLaw` |
| Compliance criticality | `High` |
| Extraction method | `ManualLawyer` |
| Review status | `PendingReview` |

4. Select the **gateway** and set `gw_conditionStatement` to: `Is it used to generate synthetic content?`

### Step 3 — Save the BPMN file

Save the file as `regulations/my-regulation/bpmn/diagram transparency.bpmn` (create the folder if needed).

### Step 4 — Run the pipeline

```bash
norma-build regulations/my-regulation/
```

The pipeline prints:
```
── KG Build: my-regulation ──────────────────────────────────────────
   BPMN source: regulations/my-regulation/bpmn
    diagram transparency.bpmn: 1 elements
   Total: 1 elements from 1 file(s)

[✓] JSON:  regulations/my-regulation/my-regulation.json
[✓] ABox:  regulations/my-regulation/my-regulation.abox.ttl

── Rule Extraction: my-regulation ─────────────────────────────────
   diagram transparency.bpmn: 1 rule(s)
[✓] SWRL:  regulations/my-regulation/my-regulation.swrl.owl
```

### Step 5 — Inspect the ABox

Open `regulations/my-regulation/my-regulation.abox.ttl` in a text editor or Protégé. You will find:

```turtle
:OBL_transparency_synthetic_content
    a owl:NamedIndividual, norma:Obligation ;
    norma:normStatement "AI providers must label AI-generated synthetic content as such." ;
    norma:hasLegalAgent :Agent_AI_provider ;
    norma:hasLegalAction :Action_label_synthetic_content ;
    norma:hasLegalObject :Object_AI_system ;
    norma:hasLegalSource :Regulation_EU_AI_Act ;
    norma:fromArticle "50" ;
    norma:hasBindingForce norma:HardLaw ;
    norma:hasComplianceCriticality norma:High ;
    norma:wasGeneratedBy :Ann_OBL_transparency_synthetic_content .
```

### Step 6 — Inspect the SWRL rule

Open `regulations/my-regulation/my-regulation.swrl.owl`. You will find one rule:

```
Is_it_used_to_generate_synthetic_content(?x, true)
  ⇒ activatesNorm(TriggerEvent_…, OBL_transparency_synthetic_content)
```

### Step 7 — View in the web application

Start the web application (Option B, step 4 above) and upload your BPMN file via the **Upload** button. The norm, graph, SWRL rule, and SPARQL interface are immediately available.

---

## Reproducibility

The pipeline is a deterministic, stateless transformation. Given the same BPMN input, every run produces byte-for-byte identical outputs. This is enforced by `reproduce.sh`, which builds the EU AI Act knowledge graph twice in isolated environments and asserts SHA-256 identity:

| Artifact | SHA-256 |
|---|---|
| `eu-ai-act.abox.ttl` | `b37aae65ea29d4e4742a74d56e63456cbf62b6b1c4c2d3c43ffd039e1518a138` |
| `eu-ai-act.swrl.owl` | `abfedffa2eb1d3d33d19fc3636d573185cf510a86f35a01a79149dd962b6eaf3` |
| `eu-ai-act.json` | `7ba605cf8fea21c82f2d55e5ebe7384bc7dccba29ae272a27c5754c084b3e0c4` |

The full EU AI Act annotation corpus (6 BPMN diagrams) is committed in `regulations/eu-ai-act/bpmn/`. Every result reported in the accompanying paper can be regenerated and verified by running `bash reproduce.sh`.

---

## Alignment with Established Standards

| Standard | Role |
|---|---|
| **OWL 2 DL** | Formal knowledge representation; full reasoner compatibility |
| **SWRL** | Conditional norm inference; compatible with Pellet and Drools SWRL bridge |
| **SPARQL 1.1** | Query interface; backed by Oxigraph |
| **BPMN 2.0** | Annotation surface; processed via standard XML parsing |
| **ELI** | Legal source typing and jurisdiction; aligns with European linked-data legal infrastructure |
| **PROV-O** | Annotation provenance; sub-properties of `prov:wasGeneratedBy`, `prov:wasAssociatedWith`, `prov:wasAttributedTo` |
| **FOAF** | Agent-level interoperability; imported at TBox level |
| **LKIF-Core** | Informative cross-vocabulary alignment via `rdfs:seeAlso`; no formal import |
| **SKOS** | Extensible controlled vocabularies; each dimension is an open `ConceptScheme` |
| **Camunda 8 / Zeebe** | Annotation tooling; element template distributable via Camunda marketplace |

---

## Constraints and Limitations

**Single regulation granularity.** The pipeline operates on a folder of BPMN files representing a single regulation or regulatory domain. Cross-regulation norm interaction and derogation are not modelled; multi-regulation inference would require additional axioms.

**Jurisdiction URIs.** When a jurisdiction string is provided in the annotation template but no authoritative URI is available, the pipeline mints a provisional local individual (`rdfs:label`-only). These provisional resources must be aligned to authoritative URIs (EU Vocabularies, Wikidata) as a post-processing step.

**SWRL reasoning scope.** SWRL rules are generated only for conditionally applicable norms. Unconditional norms are fully declared in the ABox. Reasoner compatibility is verified with Pellet; other SWRL-capable reasoners may require adaptation of the OWL/XML serialisation.

**SWRL expressivity.** Rule bodies currently encode boolean condition values (true/false gateway branches). Numeric comparisons, date ranges, and other complex condition types are not yet supported.

**Annotation coverage.** The EU AI Act example covers six process fragments. Full regulatory coverage would require annotation of the complete Act, which is ongoing work outside the scope of this resource.

**No automated extraction.** NORMA is a structured annotation framework, not an NLP-based extraction system. Legal experts annotate BPMN diagrams manually. This ensures precision and controlled vocabulary compliance but requires domain expertise.

**Reasoner not bundled.** The SWRL rules and ABox are standard and load into any OWL 2 reasoner, but no reasoner is bundled with the web application. The SPARQL interface and Evaluate panel operate over asserted triples only; SWRL-inferred triples require an external reasoner.

---

## Requirements

| Component | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Core engine and web backend |
| Node.js | 20+ | Frontend (development and Docker build) |
| Camunda Modeler | 8.x | Annotation (optional — only for creating new diagrams) |

**Core engine** (`norma_engine`): no third-party runtime dependencies — stdlib only (`xml.etree`, `difflib`, `re`, `json`, `pathlib`).

**Web backend** (`web-app/backend/requirements.txt`): `fastapi`, `uvicorn`, `python-multipart`, `pyoxigraph`, `pydantic`, `jinja2`.

**Frontend** (`web-app/frontend/package.json`): `react`, `vite`, `d3`.

---

## Testing

The test suite covers parsing, rule extraction, ABox construction, entity normalisation, SWRL export, and end-to-end SWRL evaluation. All 97 tests pass against the current codebase.

```bash
pip install -e .[dev]
pytest
```

| Module | Tests | Coverage |
|---|---|---|
| `test_parsing.py` | 9 | BPMN parsing, reduced graph construction, gateway indexing |
| `test_rules.py` | 19 | Path enumeration (DFS), RuleIR construction, condition handling |
| `test_kg.py` | 24 | ABox Turtle output, individual minting, provenance, deduplication |
| `test_normalizer.py` | 12 | Fuzzy matching, alias resolution, override application, warning generation |
| `test_exporters.py` | 12 | SWRL OWL/XML serialisation, head compactness, unconditional exclusion |
| `test_swrl_case_runner.py` | 3 | End-to-end SWRL evaluation against 5 EU AI Act scenarios |
| `test_sparql_presets.py` | 1 | SPARQL preset catalogue validation |
| `test_web_app_storage.py` | 3 | Pack storage isolation, uploaded vs. official pack workspaces |
| `test_web_evaluator.py` | 12 | SWRL norm determination, evaluator parity against reference cases |
| `test_web_pipeline.py` | 2 | Norm review deduplication across BPMN files |

End-to-end SWRL test cases are defined in `tests/eu_ai_act_cases.json`. Each case provides a set of boolean condition values and asserts which norms should be activated:

| Case | Conditions | Expected norm |
|---|---|---|
| `high_risk_biometric_not_tested` | biometric=true, tested=false | `OBL_Respect_high_risk_obligations` |
| `high_risk_biometric_tested` | biometric=true, tested=true | `OBL_ADD_testing_obligations` + high-risk |
| `biometric_law_enforcement_with_safeguards` | 6 conditions incl. safeguards=true | `OBL_Respect_prescribed_obligations` |
| `biometric_law_enforcement_without_safeguards` | same minus safeguards | `PRH_Respect_real_time_biometric_identification_ban` |
| `certified_cybersecurity_case` | cybersecurity_certified=true | `REC_NOT_Respect_cybersecurity_exemption` |

---

## Contributing

Contributions are welcome from two communities:

**Legal experts and annotators**: contribute by annotating new BPMN process models for regulations not yet covered, reviewing or correcting existing annotations in `regulations/`, improving controlled vocabulary definitions, or providing feedback on whether the ontology correctly captures legal distinctions in your domain.

**Ontology engineers and researchers**: contribute by extending the TBox with new classes or properties, improving alignments with external vocabularies (ELI, PROV-O, SKOS), proposing new SPARQL query presets, filing issues for modelling inconsistencies, or adapting the pipeline for new annotation tools beyond Camunda.

Please open an issue or pull request at [github.com/anaigmo/norma-semantic-toolkit](https://github.com/anaigmo/norma-semantic-toolkit) to get started.

---

## Citation

If you use the **NORMA Semantic Toolkit** (pipeline, web application, or annotation methodology), please cite:

```bibtex
@software{leyvaSanchez2026normaToolkit,
  title        = {{NORMA} Semantic Toolkit},
  author       = {Leyva-S{\'a}nchez, Sheyla},
  year         = {2026},
  url          = {https://github.com/anaigmo/norma-semantic-toolkit},
  note         = {Software components released under Apache-2.0; ontology and research artifacts released under CC BY 4.0.}
}
```

If you use the **NORMA-O ontology** specifically, please also cite:

```bibtex
@misc{leyvaSanchez2026norma,
  title        = {{NORMA-O}: The {NORMA} Ontology for Legal Norm Annotations},
  author       = {Leyva-S{\'a}nchez, Sheyla},
  year         = {2026},
  doi          = {10.5281/zenodo.19765302},
  url          = {https://doi.org/10.5281/zenodo.19765302},
  note         = {OWL 2 DL ontology for machine-readable legal norm annotation. CC BY 4.0.}
}
```

---

## License

This repository uses split licensing by artifact type.

- Source code in `norma_engine/`, `web-app/`, `tests/`, and deployment/build files is released under the **Apache License 2.0**. See [LICENSE](LICENSE).
- The ontology, ontology documentation, annotation template, BPMN examples, diagrams, and other research artifacts are released under the **Creative Commons Attribution 4.0 International License (CC BY 4.0)**. See [LICENSE-CC-BY](LICENSE-CC-BY).

This keeps the software under a standard open-source software license while preserving an attribution-oriented license for the ontology and scholarly content.
