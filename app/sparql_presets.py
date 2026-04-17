"""
NORMA SPARQL preset queries
============================
Curated queries shown in the workspace SPARQL panel.
Add, edit, or reorder entries here — the UI loads them via GET /api/sparql-presets.

Schema for each entry
---------------------
{
  "id":          str   — unique key used in the dropdown selector
  "label":       str   — human-readable name shown in the UI
  "description": str   — short tooltip / explanation
  "query":       str   — SPARQL 1.1 SELECT / CONSTRUCT / ASK string
}
"""

SPARQL_PRESETS: list = [
    {
        "id": "all-norms",
        "label": "All norms",
        "description": "Every norm (Obligation / Prohibition / Permission / Recommendation) with its binding force, risk level and article reference.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?type ?bindingForce ?riskLevel ?article
WHERE {
  VALUES ?type {
    norma:Obligation        norma:Prohibition
    norma:Permission        norma:Recommendation
    norma:NegativeRecommendation
  }
  ?norm a ?type ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:hasBindingForce          ?bindingForce . }
  OPTIONAL { ?norm norma:hasComplianceCriticality ?riskLevel . }
  OPTIONAL { ?norm norma:fromArticle              ?article . }
}
ORDER BY ?norm""",
    },
    {
        "id": "agents",
        "label": "Agents per norm",
        "description": "Which agents (roles / actors) are bound by each norm, and the norm's binding force.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent ?agentLabel ?norm ?normLabel ?bindingForce
WHERE {
  ?norm norma:hasLegalAgent  ?agent ;
        rdfs:label             ?normLabel ;
        norma:hasBindingForce  ?bindingForce .
  ?agent rdfs:label ?agentLabel .
}
ORDER BY ?agent""",
    },
    {
        "id": "conditions",
        "label": "Gateway conditions",
        "description": "All LegalCondition individuals with their condition statement and true/false branch labels.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?cond ?statement ?yes ?no
WHERE {
  ?cond a norma:LegalCondition ;
        norma:conditionStatement ?statement ;
        norma:trueBranchLabel    ?yes ;
        norma:falseBranchLabel   ?no .
}""",
    },
    {
        "id": "hard-law",
        "label": "Hard-law obligations",
        "description": "Obligations classified as HardLaw, with their regulation, article, and paragraph provenance.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?regulation ?article ?paragraph
WHERE {
  ?norm a norma:Obligation ;
        rdfs:label              ?label ;
        norma:hasBindingForce   norma:HardLaw ;
        norma:fromRegulation    ?regulation ;
        norma:fromArticle       ?article .
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
}
ORDER BY ?regulation ?article""",
    },
    {
        "id": "prohibitions",
        "label": "Prohibitions",
        "description": "All Prohibition norms with their action, object, and risk level.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?action ?object ?riskLevel
WHERE {
  ?norm a norma:Prohibition ;
        rdfs:label                     ?label ;
        norma:hasComplianceCriticality ?riskLevel .
  OPTIONAL { ?norm norma:actionText ?action . }
  OPTIONAL { ?norm norma:objectText ?object . }
}
ORDER BY ?riskLevel""",
    },
    {
        "id": "by-regulation",
        "label": "Norms by regulation",
        "description": "Group all norms by the regulation they derive from, showing article references.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?regulation ?article ?norm ?label ?type
WHERE {
  VALUES ?type {
    norma:Obligation        norma:Prohibition
    norma:Permission        norma:Recommendation
    norma:NegativeRecommendation
  }
  ?norm a ?type ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle    ?article . }
}
ORDER BY ?regulation ?article""",
    },
    {
        "id": "critical-risks",
        "label": "Critical-risk norms",
        "description": "Norms marked as Critical or High risk — prioritise these during compliance review.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?type ?riskLevel ?regulation ?article
WHERE {
  VALUES ?riskLevel { norma:Critical norma:High }
  VALUES ?type {
    norma:Obligation        norma:Prohibition
    norma:Permission        norma:Recommendation
    norma:NegativeRecommendation
  }
  ?norm a ?type ;
        rdfs:label                     ?label ;
        norma:hasComplianceCriticality ?riskLevel .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle    ?article . }
}
ORDER BY ?riskLevel ?norm""",
    },
    {
        "id": "count-by-type",
        "label": "Count norms by type",
        "description": "Summary: how many Obligations, Prohibitions, Permissions, and Recommendations exist in this pack.",
        "query": """\
PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?type (COUNT(?norm) AS ?count)
WHERE {
  VALUES ?type {
    norma:Obligation        norma:Prohibition
    norma:Permission        norma:Recommendation
    norma:NegativeRecommendation norma:ConstitutiveRule
  }
  ?norm a ?type .
}
GROUP BY ?type
ORDER BY DESC(?count)""",
    },
]
