# NORMA-O: The NORMA Ontology for Legal Norm Annotations

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.19765302-blue)](https://doi.org/10.5281/zenodo.19765302)
[![OWL 2 DL](https://img.shields.io/badge/Ontology-OWL%202%20DL-orange)](https://www.w3.org/TR/owl2-overview/)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Docs](https://img.shields.io/badge/Documentation-w3id.org%2Fdef%2Fnorma--o-navy)](https://w3id.org/def/norma-o)
[![Zenodo Community](https://img.shields.io/badge/Zenodo-NORMA%20Community-blue?logo=zenodo)](https://zenodo.org/communities/norma)

**NORMA-O** is an OWL 2 DL ontology for the formal semantic representation of machine-readable legal norm annotations. It provides a structured vocabulary for publishing, integrating, and reusing annotations derived from regulatory texts, while preserving full traceability to the legal source and accountability for the annotation process.

> **IRI:** `https://w3id.org/def/norma-o`  
> **Version IRI:** `https://w3id.org/def/norma-o/1.0`  
> **Preferred prefix:** `norma`  
> **HTML Documentation:** [https://w3id.org/def/norma-o](https://w3id.org/def/norma-o)

This ontology is the TBox component of the **NORMA Semantic Toolkit** — see [`sheyls/norma-semantic-toolkit`](https://github.com/sheyls/norma-semantic-toolkit) for the full toolkit including the BPMN annotation methodology, knowledge graph construction pipeline, SWRL rule engine, and REST API.

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Methodology: LOT](#methodology-lot)
- [Competency Questions](#competency-questions)
- [Ontology Diagram](#ontology-diagram)
- [Scope](#scope)
- [Principal Classes](#principal-classes)
- [Statistics](#statistics)
- [Alignments](#alignments)
- [Downloads](#downloads)
- [Rights (ODRS)](#rights-odrs)
- [Citation](#citation)
- [License](#license)

---

## Overview

Regulatory requirements are increasingly expected to be machine-readable: traceable to their legal source, classifiable by type and binding force, and queryable in automated compliance pipelines. NORMA-O provides the semantic backbone for this, enabling legal knowledge engineers and developers to publish normative content as structured, interoperable knowledge graph resources.

The ontology models normative content together with the legal context needed to interpret it. It distinguishes between regulative norms (obligations, prohibitions, permissions, recommendations, negative recommendations) and constitutive rules (definitional or classificatory statements), and represents each legal element — agent, action, object, condition, source — as a distinct entity rather than a free-text blob.

Three design principles shape the model:

1. **Explicit conditional applicability** — a `norma:TriggerEvent` links a specific condition outcome to the normative content it activates, following the W3C n-ary relation pattern. This makes branch-sensitive activation queryable rather than buried in unstructured text.
2. **Reuse of established standards** — PROV-O for annotation provenance, ELI for legal resource references, FOAF for agent metadata, and SKOS for controlled classification values.
3. **First-class provenance** — the ontology records not only what a norm says, but who produced the annotation, by what method, and with what review status.

---

## Repository Structure

```
NORMA-O/
├── README.md
├── LICENSE-CC-BY
├── CITATION.cff
│
├── development/
│   └── norma-ontology-v1.ttl          # Working source file (edit here)
│
└── release/
    └── 1.0.0/
        ├── ontology.ttl               # Frozen serialisations
        ├── ontology.owl
        ├── ontology.nt
        ├── ontology.json
        ├── index-en.html              # WIDOCO HTML documentation
        ├── .htaccess                  # Content negotiation (Apache)
        ├── 406.html
        ├── norma-o.svg                # Ontology diagram snapshot
        ├── sections/
        │   ├── abstract-en.html
        │   ├── introduction-en.html
        │   ├── overview-en.html
        │   ├── description-en.html
        │   ├── crossref-en.html
        │   ├── changelog-en.html
        │   └── references-en.html
        ├── provenance/
        │   ├── provenance-en.html
        │   └── provenance-en.ttl
        ├── resources/                 # CSS/JS assets for HTML docs
        └── webvowl/                   # Interactive visualisation
```

**Workflow per release:**

1. Edit `development/norma-ontology-v1.ttl`
2. Run WIDOCO to generate documentation → output goes to `release/1.0.0/`
3. Copy the frozen serialisations (`ontology.ttl`, `.owl`, `.nt`, `.json`) into `release/1.0.0/`
4. Create a GitHub Release tagged `v1.0.0` and attach the serialisation files
5. Update the w3id.org redirect so `https://w3id.org/def/norma-o/1.0` resolves to `release/1.0.0/`

When v2 arrives, add `release/2.0.0/` alongside `1.0.0/` — old version remains permanently accessible.

---

## Methodology: LOT

NORMA-O was developed following the **LOT (Linked Open Terms) methodology** for ontology engineering. LOT is an industrial ontology development process that provides a systematic workflow for building OWL ontologies aligned with Linked Data best practices.

| LOT Activity | Output in NORMA-O |
|---|---|
| Requirements specification | Competency questions (see below) |
| Conceptualisation | Conceptual model — classes, relations, controlled vocabularies |
| Implementation | OWL 2 DL axiomatisation in Turtle and RDF/XML |
| Publication | Persistent IRI (`w3id.org/def/norma-o`), WIDOCO HTML documentation, Zenodo release |
| Evaluation | SPARQL-based CQ evaluation against the EU AI Act ABox |

> **Reference:** Poveda-Villalón, M., Gómez-Pérez, A., & Suárez-Figueroa, M. C. (2022). LOT: An industrial oriented ontology engineering framework. *Engineering Applications of Artificial Intelligence*, 111, 104755. https://doi.org/10.1016/j.engappai.2022.104755

---

## Competency Questions

The following competency questions (CQs) guided the ontology design and serve as evaluation criteria. Each CQ can be answered by a SPARQL query over an ABox that instantiates NORMA-O.

| ID | Competency Question |
|---|---|
| CQ1 | What type of normative content does a given annotation represent — a regulative norm (obligation, prohibition, permission, recommendation, or negative recommendation) or a constitutive rule? |
| CQ2 | Under which conditions does a norm apply, and which specific condition outcome activates it? |
| CQ3 | Who is the legal agent bearing the obligation, right, or restriction stated by a norm? |
| CQ4 | What action is required, prohibited, or permitted under the norm? |
| CQ5 | What legal object does the regulated action concern? |
| CQ6 | From which legal source (regulation, directive, article, paragraph) does the norm derive? |
| CQ7 | Who produced the annotation, by which method (manual, automated, semi-automated), and under what review status? |
| CQ8 | What is the binding force (hard law, soft law) and compliance criticality (high, medium, low) of a norm? |
| CQ9 | What is the current lifecycle status of a norm (active, superseded, repealed)? |
| CQ10 | Which normative statements are activated when a given condition outcome holds? |

---

## Ontology Diagram

The diagram below shows the principal classes and object properties of NORMA-O.

![NORMA-O ontology diagram](norma-o.svg)

*Diagram generated with [diagrams.net](https://www.diagrams.net/).*

---

## Scope

The ontology covers the following aspects of legal norm annotations:

- **Regulative norms** — obligations, prohibitions, permissions, recommendations, and negative recommendations
- **Constitutive rules** — statements that define statuses, classifications, or institutional facts
- **Legal conditions and their evaluated outcomes** — including branch-sensitive activation via the `norma:TriggerEvent` n-ary relation pattern
- **Legal agents, actions, objects, and sources**
- **Provenance and annotation metadata** — extraction method, review status, lifecycle status, and source traceability

The ontology does not model procedural or institutional rules beyond what is necessary to contextualise normative content, nor does it encode substantive regulatory knowledge — that is the role of the ABox.

---

## Principal Classes

| Class | Description |
|---|---|
| `norma:NormativeContent` | Abstract superclass for all machine-readable legal content extracted from a legal source |
| `norma:RegulativeNorm` | A normative statement governing conduct |
| `norma:Obligation` | A regulative norm requiring an action |
| `norma:Prohibition` | A regulative norm forbidding an action |
| `norma:Permission` | A regulative norm allowing an action |
| `norma:Recommendation` | A regulative norm recommending an action (soft norm) |
| `norma:NegativeRecommendation` | A regulative norm advising against an action (soft norm) |
| `norma:ConstitutiveRule` | A statement that defines or qualifies a legal or institutional situation |
| `norma:LegalCondition` | A condition or criterion relevant to the applicability of a norm |
| `norma:ConditionOutcome` | An evaluated branch of a legal condition (e.g., true / false) |
| `norma:TriggerEvent` | Reification of the relation between a condition outcome and the norm it activates |
| `norma:LegalAgent` | An agent (person, organisation, or role) mentioned in a norm |
| `norma:LegalAction` | An action regulated by a norm |
| `norma:LegalObject` | An entity that is the object of the regulated action |
| `norma:LegalSource` | Work-level reference to a legal document (aligned with ELI) |
| `norma:LegalSourceExpression` | Expression-level reference to a specific version of a legal document |
| `norma:AnnotationActivity` | The activity that produced an annotation (aligned with PROV-O `Activity`) |
| `norma:AnnotatorAgent` | The agent responsible for an annotation activity |
| `norma:BindingForce` | SKOS concept class for binding force (hard law, soft law, …) |
| `norma:ComplianceCriticality` | SKOS concept class for criticality levels (high, medium, low) |
| `norma:NormStatus` | SKOS concept class for lifecycle status (active, superseded, repealed) |
| `norma:ReviewStatus` | SKOS concept class for review state (pending review, reviewed, …) |
| `norma:ExtractionMethod` | SKOS concept class for annotation method (manual, automated, semi-automated) |

---

## Statistics

| Element | Count |
|---|---|
| Classes | 23 |
| Object properties | 33 |
| Datatype properties | 24 |
| Named individuals (TBox controlled vocabulary) | 23 |
| OWL profile | OWL 2 DL |

---

## Alignments

NORMA-O imports and aligns with the following established vocabularies:

| Vocabulary | Alignment type | Role in NORMA-O |
|---|---|---|
| [PROV-O](http://www.w3.org/ns/prov#) | `owl:imports` | Provenance of annotation activities and annotator agents |
| [ELI](http://data.europa.eu/eli/ontology) | `owl:imports` | Work-level and expression-level references to legal sources |
| [FOAF](http://xmlns.com/foaf/0.1/) | `owl:imports` | Agent and project metadata |
| [SKOS](http://www.w3.org/2004/02/skos/core#) | Structural reuse | Controlled vocabulary classes and concept schemes |
| [LKIF-Core](http://www.estrellaproject.org/lkif-core/) | Informative (`skos:closeMatch`, `skos:broadMatch`) | Semantic alignment with legal knowledge interchange format |

---

## Downloads

| Format | File | Description |
|---|---|---|
| Turtle (preferred) | [`norma-ontology-v1.ttl`](norma-ontology-v1.ttl) | Primary source file, OWL 2 DL |
| RDF/XML | [`norma-ontology-v1.rdf`](norma-ontology-v1.rdf) | Equivalent serialisation in RDF/XML |
| OWL/XML | via [WIDOCO docs](https://w3id.org/def/norma-o) | Auto-generated |
| JSON-LD | via [WIDOCO docs](https://w3id.org/def/norma-o) | Auto-generated |
| N-Triples | via [WIDOCO docs](https://w3id.org/def/norma-o) | Auto-generated |

Content negotiation is supported at `https://w3id.org/def/norma-o`:

```bash
# Turtle
curl -L -H "Accept: text/turtle" https://w3id.org/def/norma-o

# RDF/XML
curl -L -H "Accept: application/rdf+xml" https://w3id.org/def/norma-o
```

---

## Rights (ODRS)

The following rights statement is provided following the [Open Data Rights Statement (ODRS) vocabulary](http://schema.theodi.org/odrs):

```turtle
@prefix odrs: <http://schema.theodi.org/odrs#> .
@prefix norma: <https://w3id.org/def/norma-o#> .
@prefix cc: <https://creativecommons.org/ns#> .
@prefix dct: <http://purl.org/dc/terms/> .

<https://w3id.org/def/norma-o>
    odrs:license <https://creativecommons.org/licenses/by/4.0/> ;
    odrs:attributionText "NORMA-O: The NORMA Ontology for Legal Norm Annotations. Sheyla Leyva-Sánchez, Ontology Engineering Group – UPM, 2026." ;
    odrs:attributionURL <https://github.com/sheyls/NORMA-O> ;
    odrs:copyrightNotice "Copyright © 2026 Sheyla Leyva-Sánchez and contributors." ;
    odrs:reuseGuidelines <https://creativecommons.org/licenses/by/4.0/> .
```

---

## Citation

If you use NORMA-O in your research, please cite:

```bibtex
@misc{leyvaSanchez2026normaO,
  title        = {{NORMA-O}: The {NORMA} Ontology for Legal Norm Annotations},
  author       = {Leyva-Sánchez, Sheyla and Poveda-Villalón, María and Rodríguez-Doncel, Víctor},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.19765302},
  url          = {https://doi.org/10.5281/zenodo.19765302}
}
```

---

## License

This ontology is released under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) licence.

Copyright © 2026 Sheyla Leyva-Sánchez and contributors. Ontology Engineering Group, Universidad Politécnica de Madrid.

You are free to share and adapt this material for any purpose, including commercially, as long as you give appropriate credit, provide a link to the licence, and indicate if changes were made.

---

## Part of the NORMA Ecosystem

NORMA-O is the TBox component of a broader open resource for legal knowledge engineering:

| Resource | Description |
|---|---|
| [`sheyls/NORMA-O`](https://github.com/sheyls/NORMA-O) | This repository — ontology TBox only |
| [`sheyls/norma-semantic-toolkit`](https://github.com/sheyls/norma-semantic-toolkit) | Full toolkit: annotation methodology, KG construction pipeline, SWRL engine, REST API, web app |
| [WIDOCO documentation](https://w3id.org/def/norma-o) | Full HTML documentation with cross-reference of all terms |
| [Zenodo community](https://zenodo.org/communities/norma) | All releases, datasets, and supplementary materials |
