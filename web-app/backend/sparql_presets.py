SPARQL_PRESETS = [
    {
        "id": "all-norms",
        "label": "All norms",
        "description": "Every norm with binding force, risk level, and article reference.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?type ?bindingForce ?riskLevel ?article
WHERE {
  VALUES ?type {
    norma:Obligation norma:Prohibition norma:Permission
    norma:Recommendation norma:NegativeRecommendation
  }
  ?norm a ?type ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:hasBindingForce ?bindingForce . }
  OPTIONAL { ?norm norma:hasComplianceCriticality ?riskLevel . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
}
ORDER BY ?norm""",
    },
    {
        "id": "agents",
        "label": "Agents per norm",
        "description": "Which agents are bound by each norm.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?agent ?agentLabel ?norm ?normLabel ?bindingForce
WHERE {
  ?norm norma:hasLegalAgent ?agent ;
        rdfs:label ?normLabel .
  ?agent rdfs:label ?agentLabel .
  OPTIONAL { ?norm norma:hasBindingForce ?bindingForce . }
}
ORDER BY ?agent""",
    },
    {
        "id": "conditions",
        "label": "Gateway conditions",
        "description": "All legal conditions and their branch labels.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?cond ?statement ?yes ?no
WHERE {
  ?cond a norma:LegalCondition ;
        norma:conditionStatement ?statement ;
        norma:trueBranchLabel ?yes ;
        norma:falseBranchLabel ?no .
}""",
    },
    {
        "id": "hard-law",
        "label": "Hard-law obligations",
        "description": "Obligations classified as hard law.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?regulation ?article ?paragraph
WHERE {
  ?norm a norma:Obligation ;
        rdfs:label ?label ;
        norma:hasBindingForce norma:HardLaw ;
        norma:fromRegulation ?regulation ;
        norma:fromArticle ?article .
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
}
ORDER BY ?regulation ?article""",
    },
    {
        "id": "critical-risks",
        "label": "Critical-risk norms",
        "description": "Norms marked as critical or high risk.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?type ?riskLevel ?regulation ?article
WHERE {
  VALUES ?riskLevel { norma:Critical norma:High }
  VALUES ?type {
    norma:Obligation norma:Prohibition norma:Permission
    norma:Recommendation norma:NegativeRecommendation
  }
  ?norm a ?type ;
        rdfs:label ?label ;
        norma:hasComplianceCriticality ?riskLevel .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
}
ORDER BY ?riskLevel ?norm""",
    },
    {
        "id": "prohibitions",
        "label": "Prohibitions",
        "description": "All Prohibition norms with action, object, and risk level.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?norm ?label ?agent ?action ?object ?riskLevel
WHERE {
  ?norm a norma:Prohibition ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:agentText ?agent . }
  OPTIONAL { ?norm norma:actionText ?action . }
  OPTIONAL { ?norm norma:objectText ?object . }
  OPTIONAL { ?norm norma:hasComplianceCriticality ?riskLevel . }
}
ORDER BY ?norm""",
    },
    {
        "id": "by-regulation",
        "label": "Norms by regulation",
        "description": "All norms grouped by the regulation they derive from.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?regulation ?norm ?type ?article
WHERE {
  VALUES ?type {
    norma:Obligation norma:Prohibition norma:Permission
    norma:Recommendation norma:NegativeRecommendation
  }
  ?norm a ?type ;
        norma:fromRegulation ?regulation .
  OPTIONAL { ?norm norma:fromArticle ?article . }
}
ORDER BY ?regulation ?article""",
    },
    {
        "id": "count-by-type",
        "label": "Count by type",
        "description": "Summary count of each deontic modality.",
        "query": """PREFIX norma: <https://w3id.org/norma-ontology#>

SELECT ?type (COUNT(?norm) AS ?count)
WHERE {
  VALUES ?type {
    norma:Obligation norma:Prohibition norma:Permission
    norma:Recommendation norma:NegativeRecommendation norma:ConstitutiveRule
  }
  ?norm a ?type .
}
GROUP BY ?type
ORDER BY DESC(?count)""",
    },
]
