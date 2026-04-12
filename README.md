# NORMA — Normative Ontology for Regulatory Machine-readable Annotations

NORMA transforms BPMN processes annotated with legal norms into a semantic knowledge graph (OWL 2 + SWRL) and machine-readable rule formats (DDL, LegalRuleML).

Given a set of annotated BPMN files, NORMA determines **which obligations, prohibitions, and permissions apply to a given legal role under a given set of conditions**. It is a **norm determination engine** — not a compliance verifier.

---

## Requirements

- Python 3.10+
- [Camunda Modeler 8](https://camunda.com/platform/modeler/) (to annotate BPMN files)

---

## Repository structure

```
norma_build.py                 ← CLI: KG pipeline (recommended entry point)
norma_rules.py                 ← CLI: rule extraction (DDL + SWRL + LegalRuleML)
kg_builder.py                  ← BPMN → JSON + Turtle ABox
kg_normalizer.py               ← Entity label normalization
src/
  main.py                      ← BPMN → DDL + SWRL + LegalRuleML (rule extraction)
  utils.py
  transformations/
    bpmn_parser.py             ← BPMN XML → reduced directed graph
    path_extractor.py          ← DFS path enumeration → RuleIR
    rule_ir.py                 ← Rule intermediate representation
  exporters/
    ddl_exporter.py            ← RuleIR → Defeasible Logic (DDL)
    swrl_exporter.py           ← RuleIR → SWRL/OWL XML
    legalruleml_exporter.py    ← RuleIR → LegalRuleML XML
regulations/
  eu-ai-act/
    bpmn/                      ← *.bpmn files go here
    eu-ai-act.abox.ttl         ← generated ABox (after running the pipeline)
camunda-template/
  camunda8-compliance-template.json   ← Camunda Modeler element template
```

---

## Step 1 — Install the Camunda element template

Copy `camunda-template/camunda8-compliance-template.json` to:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/camunda-modeler/resources/element-templates/` |
| Windows | `%APPDATA%\camunda-modeler\resources\element-templates\` |
| Linux | `~/.config/camunda-modeler/resources/element-templates/` |

Create the folder if it does not exist, then restart Camunda Modeler. The template will appear in the **Properties Panel** when you select a task or exclusive gateway.

---

## Step 2 — Annotate a BPMN process

Open or create a BPMN file in Camunda Modeler. For each task or exclusive gateway that carries a legal norm:

1. Select the element.
2. In the Properties Panel, choose **NORMA Compliance** from the template dropdown.
3. Fill in the fields (deontic type, agent, action, object, regulation, article, …).

Save the file inside a `bpmn/` subfolder of your regulation pack, e.g.:

```
regulations/eu-ai-act/bpmn/art50-art95.bpmn
```

---

## Step 3 — Build the knowledge graph (ABox)

Run the main orchestrator from the project root:

```bash
# Build a regulation pack → generates .json + .abox.ttl
python norma_build.py regulations/eu-ai-act/

# Skip entity label normalization
python norma_build.py regulations/eu-ai-act/ --no-normalize

# Generate a normalization override template first, then apply it
python norma_build.py regulations/eu-ai-act/ --template overrides.json
python norma_build.py regulations/eu-ai-act/ --override overrides.json

# Build an organization's internal policies
python norma_build.py organizations/acme-corp/internal/ --org --reg-base regulations/
```

**Outputs** (written into the same folder as the BPMN files):

| File | Description |
|------|-------------|
| `<pack>.json` | JSON intermediate (one record per annotated element) |
| `<pack>.abox.ttl` | Turtle ABox — imports `norma-ontology-v1.ttl` |

---

## Step 4 — Extract rules (DDL / SWRL / LegalRuleML)

The rule extractor enumerates all start→end execution paths through the reduced BPMN graph and builds one rule per path.

```bash
# Run from project root
python -m src.main regulations/eu-ai-act/bpmn/art50-art95.bpmn outputs/rules_DDL.txt
```

**Outputs** (siblings of the DDL file):

| File | Description |
|------|-------------|
| `rules_DDL.txt` | Defeasible Logic rules |
| `rules_DDL.swrl.owl` | SWRL rules embedded in OWL/XML |
| `rules_DDL.legalruleml.xml` | LegalRuleML (OASIS standard) |

---

## Normalization

When the same regulation or agent is written inconsistently across files ("IA Act", "ia act", "EU AI Act"), the normalizer resolves them to a single canonical label before generating the ABox.

```bash
# Standalone normalizer on an existing JSON intermediate
python kg_normalizer.py pack.json --template overrides.json
python kg_normalizer.py pack.json --override overrides.json --out pack_normalized.json
```

Fuzzy similarity threshold is configurable (default `0.82`):

```bash
python norma_build.py regulations/eu-ai-act/ --threshold 0.90
```

---

## Example — EU AI Act Art. 50 / Art. 95

A ready-to-use example is in `regulations/eu-ai-act/bpmn/art50-art95.bpmn`.

```bash
python norma_build.py regulations/eu-ai-act/
python -m src.main regulations/eu-ai-act/bpmn/art50-art95.bpmn outputs/rules_DDL.txt
```

The BPMN models the following norms:

| ID | Type | Agent | Article |
|----|------|-------|---------|
| OBL_1 | Obligation | AI owner | Art. 50 §2 |
| REC_1 | Recommendation | AI owner | Art. 95 §2 |

---

## Ontology

The TBox (`norma-ontology-v1.ttl`) is at `https://w3id.org/norma-ontology`.

Key classes:

| Class | Role |
|-------|------|
| `norma:Obligation` | MUST norms |
| `norma:Prohibition` | MUST NOT norms |
| `norma:Permission` | MAY norms |
| `norma:Recommendation` | SHOULD norms |
| `norma:NegativeRecommendation` | SHOULD NOT norms |
| `norma:ConstitutiveRule` | Definitional facts (IS) |
| `norma:LegalCondition` | Exclusive gateway conditions |
| `norma:Agent` | Who the norm applies to |
| `norma:LegalObject` | What the norm acts on |
| `norma:LegalSource` | Regulation / article reference |

---

## Licence

CC BY 4.0 — Sheyla Leyva-Sánchez et al.
