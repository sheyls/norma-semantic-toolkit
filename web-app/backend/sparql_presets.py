SPARQL_PRESETS = [
    {
        "id": "norms-by-agent",
        "label": "Norms by agent",
        "question": "Which norms apply to a given legal agent?",
        "description": "Returns all norm types grouped by their linked legal agent. Add or edit the commented FILTER to focus on one agent.",
        "vocabulary": [
            "norma:Obligation",
            "norma:Prohibition",
            "norma:Permission",
            "norma:Recommendation",
            "norma:NegativeRecommendation",
            "norma:ConstitutiveRule",
            "norma:hasLegalAgent",
            "norma:deonticId",
            "norma:fromRegulation",
            "norma:fromArticle",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?type ?agentLabel ?deonticId ?label ?regulation ?article ?paragraph
WHERE {
  VALUES ?type {
    norma:Obligation
    norma:Prohibition
    norma:Permission
    norma:Recommendation
    norma:NegativeRecommendation
    norma:ConstitutiveRule
  }
  ?norm a ?type ;
        norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasLegalAgent ?agent .
  ?agent rdfs:label ?agentLabel .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
  # FILTER(LCASE(STR(?agentLabel)) = "ai provider")
}
ORDER BY ?agentLabel ?type ?deonticId""",
    },
    {
        "id": "norms-by-object",
        "label": "Norms by object",
        "question": "Which norms concern a given legal object?",
        "description": "Returns all norm types grouped by their linked legal object. Add or edit the commented FILTER to focus on one object.",
        "vocabulary": [
            "norma:Obligation",
            "norma:Prohibition",
            "norma:Permission",
            "norma:Recommendation",
            "norma:NegativeRecommendation",
            "norma:ConstitutiveRule",
            "norma:hasLegalObject",
            "norma:deonticId",
            "norma:fromRegulation",
            "norma:fromArticle",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?type ?objectLabel ?deonticId ?label ?regulation ?article ?paragraph
WHERE {
  VALUES ?type {
    norma:Obligation
    norma:Prohibition
    norma:Permission
    norma:Recommendation
    norma:NegativeRecommendation
    norma:ConstitutiveRule
  }
  ?norm a ?type ;
        norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasLegalObject ?object .
  ?object rdfs:label ?objectLabel .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
  # FILTER(LCASE(STR(?objectLabel)) = "ai system")
}
ORDER BY ?objectLabel ?type ?deonticId""",
    },
    {
        "id": "norms-by-action",
        "label": "Norms by action",
        "question": "Which norms are attached to a given legal action?",
        "description": "Returns all norm types grouped by their linked legal action. Add or edit the commented FILTER to focus on one action.",
        "vocabulary": [
            "norma:Obligation",
            "norma:Prohibition",
            "norma:Permission",
            "norma:Recommendation",
            "norma:NegativeRecommendation",
            "norma:ConstitutiveRule",
            "norma:hasLegalAction",
            "norma:deonticId",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?type ?actionLabel ?deonticId ?label ?regulation ?article ?paragraph
WHERE {
  VALUES ?type {
    norma:Obligation
    norma:Prohibition
    norma:Permission
    norma:Recommendation
    norma:NegativeRecommendation
    norma:ConstitutiveRule
  }
  ?norm a ?type ;
        norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasLegalAction ?action .
  ?action rdfs:label ?actionLabel .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
  # FILTER(CONTAINS(LCASE(STR(?actionLabel)), "report"))
}
ORDER BY ?actionLabel ?type ?deonticId""",
    },
    {
        "id": "norms-by-source-anchor",
        "label": "Norms by source",
        "question": "Which norms originate from a given regulation, article, or paragraph?",
        "description": "Lists norms with their regulation, article, and paragraph anchor. Add or edit the commented FILTER to narrow to one source.",
        "vocabulary": [
            "norma:fromRegulation",
            "norma:fromArticle",
            "norma:fromParagraph",
            "norma:hasLegalSource",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?type ?deonticId ?label ?regulation ?article ?paragraph
WHERE {
  VALUES ?type {
    norma:Obligation
    norma:Prohibition
    norma:Permission
    norma:Recommendation
    norma:NegativeRecommendation
    norma:ConstitutiveRule
  }
  ?norm a ?type ;
        norma:deonticId ?deonticId ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
  OPTIONAL { ?norm norma:fromParagraph ?paragraph . }
  # FILTER(?regulation = "EU AI Act" && ?article = "50")
}
ORDER BY ?regulation ?article ?paragraph ?deonticId""",
    },
    {
        "id": "source-text-by-norm",
        "label": "Stored legal text",
        "question": "Which source text snippets are stored on the legal source linked to a given norm?",
        "description": "Traverses from each norm to its linked legal source and returns the source text snippets stored there.",
        "vocabulary": [
            "norma:hasLegalSource",
            "norma:LegalSource",
            "norma:originalText",
            "norma:deonticId",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?deonticId ?label ?source ?originalText
WHERE {
  ?norm norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasLegalSource ?source .
  ?source a norma:LegalSource ;
          norma:originalText ?originalText .
  # FILTER(?deonticId = "OBL_Respect_high_risk_obligations")
}
ORDER BY ?deonticId""",
    },
    {
        "id": "shared-legal-sources",
        "label": "Shared legal sources",
        "question": "Which norms share the same legal source?",
        "description": "Finds legal sources referenced by more than one generated norm in the current pack.",
        "vocabulary": [
            "norma:hasLegalSource",
            "norma:regulationName",
            "norma:articleNumber",
            "norma:paragraphNumber",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>

SELECT ?source ?regulationName ?articleNumber ?paragraphNumber (COUNT(DISTINCT ?norm) AS ?normCount)
WHERE {
  ?norm norma:hasLegalSource ?source .
  OPTIONAL { ?source norma:regulationName ?regulationName . }
  OPTIONAL { ?source norma:articleNumber ?articleNumber . }
  OPTIONAL { ?source norma:paragraphNumber ?paragraphNumber . }
}
GROUP BY ?source ?regulationName ?articleNumber ?paragraphNumber
HAVING (COUNT(DISTINCT ?norm) > 1)
ORDER BY DESC(?normCount) ?regulationName ?articleNumber""",
    },
    {
        "id": "annotation-provenance",
        "label": "Annotation provenance",
        "question": "Which annotator, annotation activity, extraction method, and confidence score are recorded for each norm?",
        "description": "Combines provenance, extraction, and confidence metadata in one view.",
        "vocabulary": [
            "norma:wasGeneratedByAnnotationActivity",
            "norma:wasAttributedToAnnotator",
            "norma:wasAssociatedWithAnnotator",
            "norma:hasExtractionMethod",
            "norma:confidenceScore",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?deonticId ?label ?annotatorLabel ?activity ?activityAnnotatorLabel ?annotationDate ?confidenceScore ?extractionMethod
WHERE {
  ?norm norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:wasGeneratedByAnnotationActivity ?activity .
  OPTIONAL {
    ?norm norma:wasAttributedToAnnotator ?annotator .
    ?annotator rdfs:label ?annotatorLabel .
  }
  OPTIONAL {
    ?activity norma:wasAssociatedWithAnnotator ?activityAnnotator .
    ?activityAnnotator rdfs:label ?activityAnnotatorLabel .
  }
  OPTIONAL { ?activity norma:annotationDate ?annotationDate . }
  OPTIONAL { ?activity norma:confidenceScore ?confidenceScore . }
  OPTIONAL { ?norm norma:hasExtractionMethod ?extractionMethod . }
}
ORDER BY ?deonticId""",
    },
    {
        "id": "norms-by-review-status",
        "label": "Norms by review status",
        "question": "Which norms have each legal review status?",
        "description": "Lists norms together with their review status so you can inspect what has been approved, left pending, or not reviewed.",
        "vocabulary": [
            "norma:hasReviewStatus",
            "norma:deonticId",
            "norma:lastReviewDate",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?deonticId ?label ?reviewStatus ?lastReviewDate
WHERE {
  ?norm norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasReviewStatus ?reviewStatus .
  OPTIONAL { ?norm norma:lastReviewDate ?lastReviewDate . }
}
ORDER BY ?reviewStatus ?deonticId""",
    },
    {
        "id": "status-and-binding-force",
        "label": "Status and binding force",
        "question": "Which norms are active, and which binding force and compliance criticality values do they carry?",
        "description": "Summarises lifecycle and compliance metadata attached to norms in the current graph.",
        "vocabulary": [
            "norma:hasNormStatus",
            "norma:hasBindingForce",
            "norma:hasComplianceCriticality",
            "norma:Active",
            "norma:HardLaw",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?deonticId ?label ?status ?bindingForce ?criticality
WHERE {
  ?norm norma:deonticId ?deonticId ;
        rdfs:label ?label .
  OPTIONAL { ?norm norma:hasNormStatus ?status . }
  OPTIONAL { ?norm norma:hasBindingForce ?bindingForce . }
  OPTIONAL { ?norm norma:hasComplianceCriticality ?criticality . }
}
ORDER BY ?status ?bindingForce ?criticality ?deonticId""",
    },
    {
        "id": "high-priority-norms",
        "label": "High-priority norms",
        "question": "Which norms have a compliance criticality of Critical or High?",
        "description": "Returns the norms classified as the highest compliance priorities, regardless of modality.",
        "vocabulary": [
            "norma:Obligation",
            "norma:Prohibition",
            "norma:Permission",
            "norma:Recommendation",
            "norma:NegativeRecommendation",
            "norma:ConstitutiveRule",
            "norma:hasComplianceCriticality",
            "norma:Critical",
            "norma:High",
        ],
        "query": """PREFIX norma: <https://w3id.org/def/norma-o#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?type ?deonticId ?label ?criticality ?regulation ?article
WHERE {
  VALUES ?type {
    norma:Obligation
    norma:Prohibition
    norma:Permission
    norma:Recommendation
    norma:NegativeRecommendation
    norma:ConstitutiveRule
  }
  ?norm a ?type ;
        norma:deonticId ?deonticId ;
        rdfs:label ?label ;
        norma:hasComplianceCriticality ?criticality .
  VALUES ?criticality { norma:Critical norma:High }
  OPTIONAL { ?norm norma:fromRegulation ?regulation . }
  OPTIONAL { ?norm norma:fromArticle ?article . }
}
ORDER BY ?criticality ?type ?deonticId""",
    },
]
