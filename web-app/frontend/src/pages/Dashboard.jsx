import { useEffect, useMemo, useState } from "react";
import {
  evaluatePack,
  getAboxDownloadUrl,
  getAboxRdfDownloadUrl,
  getPackAbox,
  getPackConditions,
  getPackEntities,
  getPackGraph,
  getPackNorms,
  getPacks,
  getPackRules,
  getPackSwrl,
  getSparqlPresets,
  getSwrlDownloadUrl,
  rebuildPack,
  runSparql,
  appendBpmnToPack,
  uploadBpmn,
} from "../api/api";
import GraphForce from "../components/GraphForce";
import Sidebar from "../components/Sidebar";

const VIEW_LABELS = {
  overview: "Overview",
  evaluator: "Norm Determination",
  artifacts: "Knowledge Base",
  rules: "Rules",
  sparql: "SPARQL",
  entities: "Entity Review",
  graph: "KG Visualisation",
  norms: "Norm Review",
  ontology: "Ontology",
};

const ONTOLOGY_ITEMS = [
  "NormativeContent covers Obligation, Prohibition, Permission, Recommendation, NegativeRecommendation, and ConstitutiveRule",
  "LegalCondition and TriggerEvent model branch-sensitive norm activation",
  "ConditionOutcome captures evaluated branches such as TrueOutcome and FalseOutcome",
  "LegalAgent, LegalAction, LegalObject, and LegalSource capture who acts, on what, and under which source",
  "AnnotationActivity, BindingForce, and ComplianceCriticality support provenance and legal classification",
];

const ONTOLOGY_DOCS_URL = "https://w3id.org/def/norma-o";

const EXTERNAL_ONTOLOGIES = [
  {
    name: "PROV O",
    prefix: "prov:",
    url: "http://www.w3.org/ns/prov#",
    note: "Used for provenance modeling, especially annotation activities and annotator relations.",
  },
  {
    name: "ELI",
    prefix: "eli:",
    url: "http://data.europa.eu/eli/ontology#",
    note: "Used for legal resources and source alignment.",
  },
  {
    name: "SKOS",
    prefix: "skos:",
    url: "http://www.w3.org/2004/02/skos/core#",
    note: "Used for deontic notations such as OBL, PRH, PER, and REC.",
  },
  {
    name: "LKIF-Core",
    prefix: "lkif:",
    url: "https://github.com/RinkeHoekstra/lkif-core",
    note: "Used as an informative alignment layer through mapping relations rather than direct ontology import.",
  },
  {
    name: "Dublin Core Terms",
    prefix: "dcterms:",
    url: "http://purl.org/dc/terms/",
    note: "Used for ontology metadata such as title, dates, license, and citation.",
  },
  {
    name: "FOAF",
    prefix: "foaf:",
    url: "http://xmlns.com/foaf/0.1/",
    note: "Used mainly for agent-oriented instance metadata such as people, organizations, names, and logo metadata.",
  },
  {
    name: "BIBO",
    prefix: "bibo:",
    url: "http://purl.org/ontology/bibo/",
    note: "Used for bibliographic publication metadata such as DOI and status.",
  },
  {
    name: "VANN",
    prefix: "vann:",
    url: "http://purl.org/vocab/vann/",
    note: "Used for preferred namespace metadata.",
  },
];

const NORM_SECTIONS = [
  {
    id: "content",
    label: "Norm Content",
    fields: [
      { key: "norm_statement", label: "Norm statement", type: "textarea" },
      { key: "agent", label: "Agent (Who)" },
      { key: "action", label: "Legal action (What)" },
      { key: "object", label: "Legal object (On what)" },
      { key: "fact_statement", label: "Constitutive rule / Fact", type: "textarea" },
      { key: "binding_force", label: "Binding force" },
      { key: "risk_level", label: "Compliance criticality" },
    ],
  },
  {
    id: "condition",
    label: "Legal Condition",
    fields: [
      { key: "gw_condition_statement", label: "Condition statement" },
      { key: "gw_true_branch", label: "True branch label" },
      { key: "gw_false_branch", label: "False branch label" },
    ],
  },
  {
    id: "source",
    label: "Legal Source",
    fields: [
      { key: "regulation", label: "Regulation" },
      { key: "article", label: "Article / Section" },
      { key: "paragraph", label: "Paragraph / Subsection" },
      { key: "original_text", label: "Original legal text", type: "textarea" },
      { key: "regulation_uri", label: "Regulation URI" },
    ],
  },
  {
    id: "scope",
    label: "Scope and Time",
    fields: [
      { key: "trigger_condition", label: "Trigger condition" },
      { key: "jurisdiction", label: "Jurisdiction" },
      { key: "effective_date", label: "Effective date" },
      { key: "deadline", label: "Deadline / Sunset date" },
      { key: "status", label: "Norm status" },
    ],
  },
  {
    id: "consequences",
    label: "Consequences & Exceptions",
    fields: [
      { key: "exception", label: "Exception", type: "textarea" },
      { key: "sanction", label: "Sanction / Consequence", type: "textarea" },
    ],
  },
  {
    id: "metadata",
    label: "Annotation Metadata",
    fields: [
      { key: "extraction_method", label: "Extraction method" },
      { key: "confidence", label: "Confidence score" },
      { key: "legal_review", label: "Legal review status" },
      { key: "annotator", label: "Annotator" },
      { key: "annotation_date", label: "Annotation date" },
      { key: "last_review_date", label: "Last reviewed date" },
    ],
  },
];

const ONTOLOGY_PREFIXES = [
  ["https://w3id.org/def/norma-o#", "norma:"],
  ["https://w3id.org/norma-abox/", "abox:"],
  ["http://www.w3.org/2001/XMLSchema#", "xsd:"],
  ["http://www.w3.org/2000/01/rdf-schema#", "rdfs:"],
  ["http://www.w3.org/2002/07/owl#", "owl:"],
];

function shortenUri(uri) {
  for (const [full, prefix] of ONTOLOGY_PREFIXES) {
    if (uri.startsWith(full)) return prefix + uri.slice(full.length);
  }
  return uri;
}

function slugify(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
}

function humanizeUnderscoredText(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function humanizeNormId(value) {
  return humanizeUnderscoredText(String(value || "").replace(/^(OBL|PROH|PERM|REC|NEGREC|FACT|GW)_/i, ""));
}

function titleCaseLabel(value) {
  const text = humanizeUnderscoredText(value);
  if (!text) {
    return "";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function normalizeDeonticType(value, fallback = "gateway") {
  const raw = String(value || fallback).trim().toLowerCase();
  if (raw === "negativerecommendation") {
    return "recommendation_not";
  }
  if (raw === "constitutiverule") {
    return "fact";
  }
  return raw || fallback;
}

function formatDeonticTypeLabel(value, fallback = "gateway") {
  const raw = normalizeDeonticType(value, fallback);
  if (raw === "recommendation_not") {
    return "Negative recommendation";
  }
  if (raw === "gateway") {
    return "Gateways";
  }
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

function deonticKeyword(value) {
  const raw = normalizeDeonticType(value, "");
  if (raw === "obligation") {
    return "MUST";
  }
  if (raw === "prohibition") {
    return "MUST NOT";
  }
  if (raw === "permission") {
    return "MAY";
  }
  if (raw === "recommendation") {
    return "SHOULD";
  }
  if (raw === "recommendation_not") {
    return "SHOULD NOT";
  }
  if (raw === "fact") {
    return "IS";
  }
  return "";
}

function getReadableNormLabel(norm) {
  return titleCaseLabel(norm.norm_statement || norm.gw_condition_statement || humanizeNormId(norm.norm_id));
}

function getReadableNormClause(norm) {
  if (isGatewayNorm(norm)) {
    return getReadableNormLabel(norm);
  }

  const keyword = deonticKeyword(norm.deontic_type);
  const agent = titleCaseLabel(norm.agent);
  const action = humanizeUnderscoredText(norm.action);
  const object = humanizeUnderscoredText(norm.object);
  const fallback = titleCaseLabel(norm.norm_statement || humanizeNormId(norm.norm_id));

  if (!keyword) {
    return fallback || "Not provided";
  }

  const tail = [action, object].filter(Boolean).join(" ");
  if (agent && tail) {
    return `${agent} ${keyword} ${tail}`;
  }
  if (agent) {
    return `${agent} ${keyword}`;
  }
  if (tail) {
    return `${keyword} ${tail}`;
  }
  if (fallback) {
    return `${keyword} ${fallback}`;
  }
  return "Not provided";
}

function isGatewayNorm(norm) {
  return (
    Boolean(norm.gw_condition_statement) ||
    String(norm.element_type || "").toLowerCase().includes("gateway") ||
    String(norm.deontic_type || "").toLowerCase() === "gateway"
  );
}

export default function Dashboard() {
  const [packs, setPacks] = useState([]);
  const [selectedPack, setSelectedPack] = useState("");
  const [activeView, setActiveView] = useState("overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [evalTypeFilter, setEvalTypeFilter] = useState("all");
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingPack, setIsLoadingPack] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [isRunningEval, setIsRunningEval] = useState(false);
  const [isRunningSparql, setIsRunningSparql] = useState(false);
  const [focusedNormId, setFocusedNormId] = useState("");

  const [rules, setRules] = useState([]);
  const [norms, setNorms] = useState([]);
  const [conditions, setConditions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [evaluation, setEvaluation] = useState([]);
  const [entities, setEntities] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [sparqlQuery, setSparqlQuery] = useState("");
  const [sparqlResult, setSparqlResult] = useState(null);
  const [normSearch, setNormSearch] = useState("");
  const [normTypeFilter, setNormTypeFilter] = useState("all");
  const [artifactText, setArtifactText] = useState("");
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [swrlText, setSwrlText] = useState("");
  const [swrlLoading, setSwrlLoading] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [graphSearch, setGraphSearch] = useState("");
  const [showGraphProvenance, setShowGraphProvenance] = useState(false);
  const [pasteName, setPasteName] = useState("uploaded pack");
  const [pasteXml, setPasteXml] = useState("");

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [packData, presetData] = await Promise.all([getPacks(), getSparqlPresets()]);
        setPacks(packData);
        setPresets(presetData.presets || []);
        if (presetData.presets?.[0]?.query) {
          setSelectedPresetId(presetData.presets[0].id || "");
          setSparqlQuery(presetData.presets[0].query);
        }
        if (packData[0]?.name) {
          setSelectedPack(packData[0].name);
        }
      } catch (err) {
        setError(err.message);
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    if (!selectedPack) {
      setRules([]);
      setNorms([]);
      setConditions([]);
      setEntities(null);
      setGraph({ nodes: [], edges: [] });
      setEvaluation([]);
      setAnswers({});
      setArtifactText("");
      return;
    }

    async function loadPackData() {
      setIsLoadingPack(true);
      try {
        setError("");
        setNotice("");
        const [rulesData, normsData, conditionsData, entitiesData, graphData] = await Promise.all([
          getPackRules(selectedPack),
          getPackNorms(selectedPack),
          getPackConditions(selectedPack),
          getPackEntities(selectedPack),
          getPackGraph(selectedPack),
        ]);

        setRules(rulesData.rules || []);
        setNorms(normsData.norms || []);
        setConditions(conditionsData.conditions || []);
        setEntities(entitiesData);
        setGraph(graphData);
        setEvaluation([]);
        setAnswers({});
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoadingPack(false);
      }
    }

    loadPackData();
  }, [selectedPack, reloadToken]);

  useEffect(() => {
    if (!selectedPack) {
      return;
    }

    async function loadArtifact() {
      setArtifactLoading(true);
      try {
        const text = await getPackAbox(selectedPack);
        setArtifactText(text);
      } catch (err) {
        setArtifactText(`Unable to load ABox content.\n\n${err.message}`);
      } finally {
        setArtifactLoading(false);
      }
    }

    loadArtifact();
  }, [selectedPack, reloadToken]);

  useEffect(() => {
    if (!selectedPack) {
      setSwrlText("");
      return;
    }

    async function loadSwrl() {
      setSwrlLoading(true);
      try {
        const text = await getPackSwrl(selectedPack);
        setSwrlText(text);
      } catch (err) {
        setSwrlText(`Unable to load SWRL OWL/XML content.\n\n${err.message}`);
      } finally {
        setSwrlLoading(false);
      }
    }

    loadSwrl();
  }, [selectedPack]);

  const selectedPackSummary = useMemo(
    () => packs.find((pack) => pack.name === selectedPack) || null,
    [packs, selectedPack],
  );

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) || presets[0] || null,
    [presets, selectedPresetId],
  );

  const answeredCount = Object.keys(answers).length;

  const filteredNorms = useMemo(() => {
    const query = normSearch.trim().toLowerCase();
    return norms.filter((norm) => {
      const type = normalizeDeonticType(norm.deontic_type, "");
      const gatewayNorm = isGatewayNorm(norm);

      if (normTypeFilter === "gateway") {
        if (!gatewayNorm) {
          return false;
        }
      } else if (normTypeFilter !== "all") {
        if (type !== normTypeFilter) {
          return false;
        }
      }

      if (!query) {
        return true;
      }

      const haystack = [
        norm.norm_id,
        norm.action,
        norm.agent,
        norm.object,
        norm.regulation,
        norm.article,
        norm.norm_statement,
        norm.annotator,
        norm.gw_condition_statement,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [norms, normSearch, normTypeFilter]);

  const legalNormCount = useMemo(
    () => norms.filter((norm) => !isGatewayNorm(norm)).length,
    [norms],
  );

  const filteredGraph = useMemo(() => {
    const hiddenTypes = new Set(["AnnotationActivity", "AnnotatorAgent"]);
    const visibleNodesBase = showGraphProvenance
      ? graph.nodes
      : graph.nodes.filter((node) => !hiddenTypes.has(node.type));
    const visibleNodeIdsBase = new Set(visibleNodesBase.map((node) => node.id));
    const visibleEdgesBase = showGraphProvenance
      ? graph.edges
      : graph.edges.filter(
          (edge) => visibleNodeIdsBase.has(edge.source) && visibleNodeIdsBase.has(edge.target),
        );

    const query = graphSearch.trim().toLowerCase();
    if (!query) {
      return { nodes: visibleNodesBase, edges: visibleEdgesBase };
    }

    const normalizeSearch = (value) =>
      String(value || "")
        .toLowerCase()
        .replace(/\bia\b/g, "ai")
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const queryTokens = normalizeSearch(query).split(" ").filter(Boolean);

    const matchesNode = (node) => {
      const haystack = normalizeSearch(
        [
          node.id,
          node.label,
          node.type,
          node.regulation,
          node.article,
          node.paragraph,
          node.source,
          node.deontic_id,
          node.norm_statement,
          node.condition_statement,
          node.trigger_condition,
          node.agent,
          node.action,
          node.object,
          node.outcome,
          node.true_branch,
          node.false_branch,
          node.bpmn_source,
          node.original_text,
        ]
          .filter(Boolean)
          .join(" "),
      );
      return queryTokens.every((token) => haystack.includes(token));
    };

    const matchedIds = new Set(visibleNodesBase.filter(matchesNode).map((node) => node.id));
    const edgeMatchedIds = new Set();
    const matchedEdges = visibleEdgesBase.filter((edge) => {
      const edgeText = normalizeSearch(`${edge.label || ""} ${edge.source} ${edge.target}`);
      const edgeMatches = queryTokens.every((token) => edgeText.includes(token));
      if (edgeMatches) {
        edgeMatchedIds.add(edge.source);
        edgeMatchedIds.add(edge.target);
        return true;
      }
      return matchedIds.has(edge.source) && matchedIds.has(edge.target);
    });

    const visibleIds = new Set([...matchedIds, ...edgeMatchedIds]);

    return {
      nodes: visibleNodesBase.filter((node) => visibleIds.has(node.id)),
      edges: matchedEdges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)),
    };
  }, [graph.nodes, graph.edges, graphSearch, showGraphProvenance]);

  const filteredGraphNodes = filteredGraph.nodes;
  const filteredGraphEdges = filteredGraph.edges;
  const filteredGraphComponentCount = useMemo(() => {
    if (!filteredGraphNodes.length) return 0;

    const adjacency = new Map(filteredGraphNodes.map((node) => [node.id, new Set()]));
    filteredGraphEdges.forEach((edge) => {
      if (adjacency.has(edge.source) && adjacency.has(edge.target)) {
        adjacency.get(edge.source).add(edge.target);
        adjacency.get(edge.target).add(edge.source);
      }
    });

    const visited = new Set();
    let componentCount = 0;

    filteredGraphNodes.forEach((node) => {
      if (visited.has(node.id)) return;
      componentCount += 1;
      const stack = [node.id];
      visited.add(node.id);

      while (stack.length) {
        const current = stack.pop();
        for (const neighbor of adjacency.get(current) || []) {
          if (visited.has(neighbor)) continue;
          visited.add(neighbor);
          stack.push(neighbor);
        }
      }
    });

    return componentCount;
  }, [filteredGraphNodes, filteredGraphEdges]);

  const filteredEvaluation = useMemo(() => {
    if (evalTypeFilter === "all") return evaluation;
    return evaluation.filter(
      (item) => normalizeDeonticType(item.deontic_type, "other") === evalTypeFilter,
    );
  }, [evaluation, evalTypeFilter]);

  const quickEntityCandidates = useMemo(() => {
    return (entities?.warnings || []).map((warning, index) => ({
      id: `${warning.field}-${index}`,
      field: warning.field,
      labelA: warning.labels?.[0] || "",
      labelB: warning.labels?.[1] || "",
      message: warning.message,
    }));
  }, [entities]);

  const normDuplicateCandidates = useMemo(() => entities?.norm_duplicates || [], [entities]);

  async function refreshPacks(nextSelectedPack = selectedPack) {
    const packData = await getPacks();
    setPacks(packData);
    if (nextSelectedPack && packData.some((pack) => pack.name === nextSelectedPack)) {
      setSelectedPack(nextSelectedPack);
    } else if (packData[0]?.name) {
      setSelectedPack(packData[0].name);
    }
  }

  async function processUpload(file, mode = "new") {
    setIsUploading(true);
    setError("");
    setNotice("");
    try {
      const uploaded =
        mode === "append" && selectedPack ? await appendBpmnToPack(selectedPack, file) : await uploadBpmn(file);
      await refreshPacks(uploaded.pack);
      setActiveView("overview");
      if (mode === "append" && selectedPack) {
        const samePack = uploaded.pack === selectedPack;
        setNotice(
          samePack
            ? `Added "${uploaded.added_bpmn || file.name}" to pack "${uploaded.pack}".`
            : `Created temporary pack "${uploaded.pack}" from "${selectedPack}" and added "${uploaded.added_bpmn || file.name}".`,
        );
      } else {
        setNotice(`Pack "${uploaded.pack}" processed successfully.`);
      }
      if (pasteXml.trim()) {
        setPasteXml("");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await processUpload(file, "new");
    event.target.value = "";
  }

  async function handleAppendUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await processUpload(file, "append");
    event.target.value = "";
  }

  function openPackCreator() {
    setActiveView("overview");
  }

  async function handlePasteUpload() {
    const xml = pasteXml.trim();
    if (!xml) {
      setError("Paste BPMN XML before uploading.");
      return;
    }
    const filename = `${slugify(pasteName || "pasted pack") || "pasted-pack"}.bpmn`;
    const file = new File([xml], filename, { type: "application/xml" });
    await processUpload(file);
  }

  async function handleRunEvaluation() {
    if (!selectedPack) {
      return;
    }
    setIsRunningEval(true);
    setError("");
    try {
      const result = await evaluatePack(selectedPack, answers);
      setEvaluation(result.matched_rules || []);
      setEvalTypeFilter("all");
    } catch (err) {
      setError(err.message);
    } finally {
      setIsRunningEval(false);
    }
  }

  async function handleRunSparql() {
    if (!selectedPack || !sparqlQuery.trim()) {
      return;
    }
    setIsRunningSparql(true);
    setError("");
    try {
      const result = await runSparql(selectedPack, sparqlQuery);
      setSparqlResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsRunningSparql(false);
    }
  }

  function applySparqlPreset(preset) {
    setSelectedPresetId(preset.id);
    setSparqlQuery(preset.query);
    setSparqlResult(null);
  }

  async function handleRebuildPack() {
    if (!selectedPack) {
      return;
    }
    setIsRebuilding(true);
    setError("");
    setNotice("");
    try {
      const result = await rebuildPack(selectedPack);
      await refreshPacks(selectedPack);
      setReloadToken((current) => current + 1);
      setNotice(`Pack "${result.pack}" rebuilt successfully from ${result.rebuild_source}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsRebuilding(false);
    }
  }

  function jumpToNorm(normId) {
    setFocusedNormId(normId);
    setActiveView("norms");
  }

  function renderOverview() {
    return (
      <div className="workspace-grid workspace-grid--overview">
        <section className="panel panel--soft pack-create-panel">
          <div className="section-intro">
            <p className="eyebrow">Selected pack</p>
            <h2>{selectedPack || "Select a regulation pack from the left sidebar"}</h2>
            <p className="section-copy">
              Choose a pack, inspect the generated knowledge artifacts, review extracted norms, and
              query the graph when deeper semantic inspection is needed.
            </p>
          </div>
          <div className="stat-grid">
            <div className="stat-card">
              <span className="stat-card__label">Norms</span>
              <span className="stat-card__value">{legalNormCount}</span>
              <span className="stat-card__sub">legal norms</span>
            </div>
            <div className="stat-card">
              <span className="stat-card__label">Conditions</span>
              <span className="stat-card__value">{conditions.length}</span>
              <span className="stat-card__sub">gateway conditions</span>
            </div>
            <div className="stat-card">
              <span className="stat-card__label">Rules</span>
              <span className="stat-card__value">{selectedPackSummary?.rule_count || 0}</span>
              <span className="stat-card__sub">extracted path rules</span>
            </div>
          </div>
          <div className="summary-list">
            <div className="summary-list__row">
              <span>Loaded packs</span>
              <strong>{packs.length}</strong>
            </div>
            <div className="summary-list__row">
              <span>Applicable norms (last eval)</span>
              <strong>{evaluation.length || "—"}</strong>
            </div>
            <div className="summary-list__row">
              <span>Regeneration</span>
              <strong>{selectedPackSummary?.can_rebuild ? "Available" : "Upload only"}</strong>
            </div>
          </div>
          {selectedPackSummary?.can_rebuild ? (
            <div className="section-actions">
              <button className="button button--ghost" type="button" onClick={handleRebuildPack} disabled={isRebuilding}>
                {isRebuilding ? "Rebuilding..." : "Regenerate selected pack"}
              </button>
            </div>
          ) : null}
        </section>

        <section className="panel panel--soft">
          <div className="section-intro">
            <div className="overview-pack-kicker">
              Create new pack
            </div>
            <h2>Create a new regulation pack for exploration</h2>
            <p className="section-copy">
              Create a temporary regulation pack by uploading a BPMN file or by pasting BPMN XML.
              The generated artifacts can then be inspected like any other pack.
            </p>
          </div>
          <div
            className="dropzone"
            onDragOver={(event) => {
              event.preventDefault();
              event.currentTarget.classList.add("is-over");
            }}
            onDragLeave={(event) => {
              event.currentTarget.classList.remove("is-over");
            }}
            onDrop={(event) => {
              event.preventDefault();
              event.currentTarget.classList.remove("is-over");
              const file = event.dataTransfer.files?.[0];
              if (file) {
                processUpload(file, "new");
              }
            }}
          >
            <strong>Drop a BPMN file here</strong>
            <span>or import a BPMN file from the sidebar</span>
          </div>
          <div className="form-grid pack-create-panel__grid">
            <label className="pack-create-panel__field">
              <span>New pack name</span>
              <input value={pasteName} onChange={(event) => setPasteName(event.target.value)} />
            </label>
            <div className="upload-actions pack-create-panel__actions">
              <button className="button button--primary" type="button" onClick={handlePasteUpload} disabled={isUploading}>
                {isUploading ? "Processing..." : "Create pack from pasted BPMN"}
              </button>
            </div>
          </div>
          <textarea
            className="editor editor--small"
            value={pasteXml}
            onChange={(event) => setPasteXml(event.target.value)}
            placeholder="Paste BPMN XML here to create a temporary regulation pack."
          />
        </section>
      </div>
    );
  }

  function renderArtifacts() {
    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Knowledge Base</p>
            <h2>Pack ABox</h2>
            <p className="section-copy">
              This section shows the generated ABox for the selected pack. It is the RDF
              instantiation produced from the annotated BPMN and the NORMA ontology.
            </p>
          </div>
        </div>
        <div className="action-grid">
          <a className="action-card" href={selectedPack ? getAboxDownloadUrl(selectedPack) : "#"}>
            <strong>Download ABox Turtle</strong>
            <span>Turtle serialization of the generated ABox.</span>
          </a>
          <a className="action-card" href={selectedPack ? getAboxRdfDownloadUrl(selectedPack) : "#"}>
            <strong>Download ABox RDF/XML</strong>
            <span>RDF XML serialization for tools that need that format.</span>
          </a>
        </div>
        <pre className="result-box">{artifactLoading ? "Loading knowledge base..." : artifactText || "No ABox content loaded."}</pre>
      </section>
    );
  }

  function renderRules() {
    const humanReadableText = rules.length
      ? rules
          .map((rule, index) => {
            const fallbackId = `rule-${index + 1}`;
            const formula = String(rule.human_readable_compact || rule.human_readable || "No readable rule text available.")
              .replace(/^r\d+:\s*/, "");
            return `${rule.rid || fallbackId}\n${formula}`;
          })
          .join("\n\n")
      : "No rules available for this pack.";

    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Rules</p>
            <h2>Readable rules and OWL syntax</h2>
            <p className="section-copy">
              This section shows the generated rule layer in two forms: a readable explanation and
              the formal OWL XML serialization of the SWRL rules.
            </p>
          </div>
        </div>
        <div className="action-grid">
          <div className="action-card action-card--static">
            <strong>Readable rules</strong>
            <span>Compact rule paths for quick inspection of the selected pack.</span>
          </div>
          <a className="action-card" href={selectedPack ? getSwrlDownloadUrl(selectedPack) : "#"}>
            <strong>Download SWRL</strong>
            <span>OWL XML serialization for the generated SWRL rules.</span>
          </a>
        </div>
        <div className="rules-grid rules-grid--stacked">
          <section className="list-card rules-panel">
            <div className="result-box result-box--tall rules-readable-text">{humanReadableText}</div>
          </section>

          <section className="list-card rules-panel">
            <div className="rules-panel__head">
              <strong>OWL syntax</strong>
            </div>
            <pre className="result-box result-box--tall rules-code">
              {swrlLoading ? "Loading SWRL OWL/XML..." : swrlText || "No SWRL content loaded."}
            </pre>
          </section>
        </div>
      </section>
    );
  }

  function renderEvaluator() {
    const typeCounts = evaluation.reduce((acc, item) => {
      const key = normalizeDeonticType(item.deontic_type, "other");
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    const evalTypeTabs = [
      { id: "all", label: "All", count: evaluation.length },
      { id: "obligation", label: "Obligations", count: typeCounts.obligation || 0 },
      { id: "prohibition", label: "Prohibitions", count: typeCounts.prohibition || 0 },
      { id: "permission", label: "Permissions", count: typeCounts.permission || 0 },
      { id: "recommendation", label: "Recommendations", count: typeCounts.recommendation || 0 },
      { id: "recommendation_not", label: "Negative recommendations", count: typeCounts.recommendation_not || 0 },
    ].filter((tab) => tab.id === "all" || tab.count > 0);

    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Evaluator</p>
            <h2>Condition based norm determination</h2>
          </div>
          <div className="pill-row">
            <button className="button button--cta" type="button" onClick={handleRunEvaluation} disabled={isRunningEval}>
              {isRunningEval ? "Evaluating..." : "Determine applicable norms"}
            </button>
            {answeredCount > 0 && (
              <button
                className="pill"
                type="button"
                onClick={() => { setAnswers({}); setEvaluation([]); setEvalTypeFilter("all"); }}
              >
                Reset
              </button>
            )}
          </div>
        </div>

        <div className="progress-card">
          <div className="progress-card__head">
            <strong>Question progress</strong>
            <span>
              {answeredCount} / {conditions.length}
            </span>
          </div>
          <div className="progress-bar">
            <span style={{ width: `${conditions.length ? (answeredCount / conditions.length) * 100 : 0}%` }} />
          </div>
        </div>

        <div className="qa-grid">
          {conditions.map((condition, index) => (
            <div className={`question-card ${answers[condition.predicate] !== undefined ? "is-done" : ""}`} key={condition.predicate}>
              <div className="question-card__meta">Condition {index + 1} of {conditions.length}</div>
              <strong>{condition.label}</strong>
              <small>{condition.predicate}</small>
              <div className="pill-row">
                <button
                  type="button"
                  className={`pill ${answers[condition.predicate] === true ? "is-selected" : ""}`}
                  onClick={() => setAnswers((current) => ({ ...current, [condition.predicate]: true }))}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className={`pill ${answers[condition.predicate] === false ? "is-selected" : ""}`}
                  onClick={() => setAnswers((current) => ({ ...current, [condition.predicate]: false }))}
                >
                  No
                </button>
                {answers[condition.predicate] !== undefined && (
                  <button
                    type="button"
                    className="pill"
                    onClick={() =>
                      setAnswers((current) => {
                        const next = { ...current };
                        delete next[condition.predicate];
                        return next;
                      })
                    }
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {evaluation.length > 0 && (
          <div className="eval-type-tabs">
            {evalTypeTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`pill ${evalTypeFilter === tab.id ? "is-selected" : ""}`}
                onClick={() => setEvalTypeFilter(tab.id)}
              >
                {tab.label}
                <span className="tab-count">{tab.count}</span>
              </button>
            ))}
          </div>
        )}

        <div className="stack-list">
          {filteredEvaluation.map((item) => (
            <article className="list-card" key={`${item.rule_id}-${item.norm_id}`}>
              <div className="list-card__head">
                <strong>{getReadableNormLabel(item)}</strong>
                <span className={`deontic-badge deontic-badge--${normalizeDeonticType(item.deontic_type, "norm")}`}>
                  {formatDeonticTypeLabel(item.deontic_type || "norm", "norm")}
                </span>
              </div>
              <p className="norm-clause">{getReadableNormClause(item)}</p>
              <div className="norm-pills">
                {item.binding_force && <span className="norm-pill">{humanizeUnderscoredText(item.binding_force)}</span>}
                {item.risk_level && <span className="norm-pill">{humanizeUnderscoredText(item.risk_level)}</span>}
                {item.regulation && <span className="norm-pill">{item.regulation}</span>}
                {item.article && <span className="norm-pill">Art. {item.article}</span>}
                {item.paragraph && <span className="norm-pill">§ {item.paragraph}</span>}
                {item.source_uri && (
                  <a href={item.source_uri} target="_blank" rel="noopener noreferrer" className="norm-pill law-link">
                    Open legislation
                  </a>
                )}
              </div>
              {item.conditions?.length > 0 && (
                <div className="triggered-by">
                  <span className="triggered-by__label">Triggered by:</span>
                  {item.conditions.map((c) => (
                  <span key={c.predicate} className={`cond-chip cond-chip--${c.value ? "yes" : "no"}`}>
                      {humanizeUnderscoredText(c.predicate)} = {c.value ? "Yes" : "No"}
                    </span>
                  ))}
                </div>
              )}
              <div className="inline-meta">
                <span />
                <button className="pill" type="button" onClick={() => jumpToNorm(item.norm_id)}>
                  View annotation
                </button>
              </div>
            </article>
          ))}
          {filteredEvaluation.length === 0 && evaluation.length > 0 ? (
            <div className="table__empty">
              No {evalTypeFilter === "all" ? "norms" : formatDeonticTypeLabel(evalTypeFilter).toLowerCase()} matched.
            </div>
          ) : null}
          {evaluation.length === 0 ? (
            <div className="table__empty">Answer the conditions and run the evaluator to see applicable norms.</div>
          ) : null}
        </div>
      </section>
    );
  }

  function renderSparqlResults() {
    if (!sparqlResult) return <p className="muted" style={{ marginTop: 12 }}>No query run yet.</p>;

    // ASK query
    if (typeof sparqlResult === "object" && "boolean" in sparqlResult) {
      return (
        <div className={`sparql-ask ${sparqlResult.boolean ? "is-true" : "is-false"}`}>
          ASK result: <strong>{sparqlResult.boolean ? "true" : "false"}</strong>
        </div>
      );
    }

    // SELECT query
    if (sparqlResult?.head?.vars && sparqlResult?.results?.bindings) {
      const vars = sparqlResult.head.vars;
      const rows = sparqlResult.results.bindings;
      return (
        <div className="sparql-result-wrap">
          <p className="sparql-count">{rows.length} result{rows.length !== 1 ? "s" : ""}</p>
          <div className="sparql-table-scroll">
            <table className="sparql-table">
              <thead>
                <tr>{vars.map((v) => <th key={v}>{v}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {vars.map((v) => {
                      const cell = row[v];
                      if (!cell) return <td key={v} />;
                      if (cell.type === "uri") {
                        const short = shortenUri(cell.value);
                        return (
                          <td key={v}>
                            <span className="sq-uri" title={cell.value}>{short}</span>
                          </td>
                        );
                      }
                      return (
                        <td key={v}>
                          <span className="sq-lit">{cell.value}</span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    // CONSTRUCT, DESCRIBE, or raw text
    return <pre className="result-box">{typeof sparqlResult === "string" ? sparqlResult : JSON.stringify(sparqlResult, null, 2)}</pre>;
  }

  function renderSparql() {
    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">SPARQL</p>
            <h2>Query the selected knowledge graph</h2>
            <p className="section-copy">
              Each preset is framed as a competency question and paired with a runnable SPARQL query
              that uses the NORMA vocabulary generated by the toolkit.
            </p>
          </div>
          <div className="pill-row">
            <button className="button button--primary" type="button" onClick={handleRunSparql} disabled={isRunningSparql}>
              {isRunningSparql ? "Running…" : "Run query"}
            </button>
            {sparqlResult && (
              <button className="pill" type="button" onClick={() => setSparqlResult(null)}>
                Clear
              </button>
            )}
          </div>
        </div>
        <div className="preset-row">
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`pill ${selectedPreset?.id === preset.id ? "is-selected" : ""}`}
              title={preset.question || preset.description}
              onClick={() => applySparqlPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
        </div>
        {selectedPreset && (
          <article className="sparql-competency">
            <p className="sparql-competency__eyebrow">What this query answers</p>
            <h3>{selectedPreset.question}</h3>
            {selectedPreset.description && <p>{selectedPreset.description}</p>}
            {selectedPreset.vocabulary?.length ? (
              <div className="sparql-competency__terms">
                {selectedPreset.vocabulary.map((term) => (
                  <span className="norm-pill" key={term}>{term}</span>
                ))}
              </div>
            ) : null}
          </article>
        )}
        <textarea
          className="editor"
          value={sparqlQuery}
          onChange={(event) => setSparqlQuery(event.target.value)}
          placeholder="Write a SPARQL 1.1 query..."
        />
        {renderSparqlResults()}
      </section>
    );
  }

  function renderNorms() {
    function renderFieldValue(norm, field) {
      const value = norm[field.key];
      if (!value) {
        return <div className="norm-readonly__empty">Not provided</div>;
      }
      if (field.type === "textarea") {
        return <div className="norm-readonly norm-readonly--long">{value}</div>;
      }
      return <div className="norm-readonly">{value}</div>;
    }

    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Visual Exploration</p>
            <h2>Norm exploration</h2>
            <p className="section-copy">
              This view presents the extracted norm and condition annotations for the selected
              pack. It is designed for inspection, traceability, and navigation.
            </p>
          </div>
          <span className="muted" style={{ fontSize: "0.85rem", alignSelf: "center" }}>
            {filteredNorms.length} of {norms.length}
          </span>
        </div>

        <div className="norm-toolbar">
          <input
            className="norm-search"
            value={normSearch}
            onChange={(event) => setNormSearch(event.target.value)}
            placeholder="Search ID, action, agent, regulation, or article..."
          />
          <div className="pill-row">
            {["all", "obligation", "prohibition", "permission", "recommendation", "recommendation_not", "fact", "gateway"].map((t) => (
              <button
                key={t}
                type="button"
                className={`pill ${normTypeFilter === t ? "is-selected" : ""}`}
                onClick={() => setNormTypeFilter(t)}
              >
                {t === "all" ? "All" : formatDeonticTypeLabel(t)}
              </button>
            ))}
          </div>
        </div>

        <div className="stack-list">
          {filteredNorms.map((norm) => {
            const gatewayNorm = isGatewayNorm(norm);
            const visibleSections = gatewayNorm
              ? NORM_SECTIONS.filter((section) => section.id === "condition")
              : NORM_SECTIONS.filter((section) => section.id !== "condition");

            return (
              <article
                className={`list-card norm-card ${focusedNormId === norm.norm_id ? "is-focused" : ""}`}
                key={norm.norm_id}
                ref={(el) => {
                  if (focusedNormId === norm.norm_id && el) {
                    el.scrollIntoView({ behavior: "smooth", block: "start" });
                  }
                }}
              >
                <div className="list-card__head">
                  <strong>{getReadableNormLabel(norm)}</strong>
                  <span className={`deontic-badge deontic-badge--${normalizeDeonticType(norm.deontic_type, "fact")}`}>
                    {formatDeonticTypeLabel(norm.deontic_type || norm.element_type || "gateway")}
                  </span>
                </div>
                <p className="norm-clause">{getReadableNormClause(norm)}</p>
                <div className="norm-meta-grid">
                  <span>{norm.bpmn_source || "unknown source"}</span>
                  <span>{norm.regulation || "Not provided"}</span>
                  <span>{norm.article ? `Art. ${norm.article}` : "Not provided"}</span>
                  <span>
                    {norm.conditions?.length ? (
                      norm.conditions.map((c) => (
                        <span key={c.predicate} className={`cond-chip cond-chip--${c.value ? "yes" : "no"}`}>
                          {humanizeUnderscoredText(c.label || c.predicate)} = {c.value ? "Yes" : "No"}
                        </span>
                      ))
                    ) : (
                      "unconditional"
                    )}
                  </span>
                </div>

                {visibleSections.map((section) => (
                  <details className="norm-section" key={section.id}>
                    <summary className="norm-section__header">{section.label}</summary>
                    <div className="form-grid form-grid--wide norm-section__body">
                      {section.fields.map((field) => (
                        <label key={field.key}>
                          <span>{field.label}</span>
                          {renderFieldValue(norm, field)}
                        </label>
                      ))}
                    </div>
                  </details>
                ))}
              </article>
            );
          })}
          {filteredNorms.length === 0 ? (
            <div className="table__empty">No norms match the current search and filter.</div>
          ) : null}
        </div>
      </section>
    );
  }

  function renderEntitiesPanel() {
    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Entities</p>
            <h2>Entity review</h2>
            <p className="section-copy">
              This view summarizes entity and KG consistency checks. Merge decisions and canonical
              maintenance should belong to a separate legal KG maintenance application, not to the
              public exploration interface.
            </p>
          </div>
        </div>

        <div className="workspace-grid">
          <article className="list-card">
            <strong>Potential duplicate norms</strong>
            <div className="stack-list stack-list--compact">
              {normDuplicateCandidates.map((candidate, index) => (
                <div className="decision-card" key={`${candidate.left_norm_id}-${candidate.right_norm_id}-${index}`}>
                  <div className="inline-meta">
                    <span className={`deontic-badge deontic-badge--${normalizeDeonticType(candidate.deontic_type, "fact")}`}>
                      {formatDeonticTypeLabel(candidate.deontic_type || "fact", "fact")}
                    </span>
                    <span className="sim-score">score {Math.round((candidate.score || 0) * 100)}%</span>
                  </div>
                  <strong>{titleCaseLabel(candidate.left_label || candidate.left_norm_id)}</strong>
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>vs</span>
                  <strong>{titleCaseLabel(candidate.right_label || candidate.right_norm_id)}</strong>
                  <p className="decision-card__text">
                    {[candidate.regulation, candidate.article ? `Art. ${candidate.article}` : "", candidate.left_source, candidate.right_source]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <p className="decision-card__text">{(candidate.reasons || []).join(" · ")}</p>
                  <div className="inline-meta" style={{ marginTop: 10 }}>
                    <button className="pill" type="button" onClick={() => jumpToNorm(candidate.left_norm_id)}>
                      Open first norm
                    </button>
                    <button className="pill" type="button" onClick={() => jumpToNorm(candidate.right_norm_id)}>
                      Open second norm
                    </button>
                  </div>
                </div>
              ))}
              {normDuplicateCandidates.length === 0 ? (
                <div className="table__empty">No duplicate norm candidates detected right now.</div>
              ) : null}
            </div>
          </article>

          <article className="list-card">
            <strong>Flagged similar labels</strong>
            <p className="decision-card__text">
              These labels look close enough to deserve review, but users cannot merge them from
              this application.
            </p>
            <div className="stack-list stack-list--compact">
              {quickEntityCandidates.map((candidate) => (
                <div className="decision-card" key={candidate.id}>
                  <div className="inline-meta">
                    <span className={`field-badge field-badge--${candidate.field}`}>{candidate.field}</span>
                    <span className="sim-score">{candidate.message.match(/\d+%/)?.[0] || ""}</span>
                  </div>
                  <strong>{candidate.labelA}</strong>
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>vs</span>
                  <strong>{candidate.labelB}</strong>
                  <p className="decision-card__text">{candidate.message}</p>
                </div>
              ))}
              {quickEntityCandidates.length === 0 ? <div className="table__empty">No similar label warnings right now.</div> : null}
            </div>
          </article>
        </div>

        <div className="workspace-grid">
          <article className="list-card">
            <strong>Canonicalization summary</strong>
            <p className="decision-card__text">
              These are the automatic normalization decisions currently applied during pack regeneration.
            </p>
            <div className="stack-list stack-list--compact">
              {(entities?.decisions || []).map((decision, index) => (
                <div className="decision-card" key={`${decision.field}-${index}`}>
                  <div className="inline-meta">
                    <span className={`field-badge field-badge--${decision.field}`}>{decision.field}</span>
                    <span className="sim-score">{decision.reason}</span>
                  </div>
                  <strong>{decision.raw_labels?.[0] || decision.winner}</strong>
                  {decision.raw_labels?.slice(1).map((label) => (
                    <p className="decision-card__text" key={label}>
                      {label} resolves to {decision.winner}
                    </p>
                  ))}
                </div>
              ))}
              {(entities?.decisions || []).length === 0 ? <div className="table__empty">No canonicalization decisions recorded for this pack.</div> : null}
            </div>
          </article>
          <article className="list-card">
            <strong>Maintenance boundary</strong>
            <p className="decision-card__text">
              This open source interface is intended for browsing, checking, and reviewing the legal
              knowledge graph. Direct merge actions are intentionally outside this user interface.
            </p>
            <div className="stack-list stack-list--compact">
              <div className="decision-card">
                <strong>Main user app</strong>
                <p className="decision-card__text">
                  Review packs, inspect duplicate warnings, open norms, run norm determination, and
                  explore the semantic graph.
                </p>
              </div>
              <div className="decision-card">
                <strong>Separate KG maintenance app</strong>
                <p className="decision-card__text">
                  Handle canonical merges, override decisions, provenance aware reconciliation, and
                  legal knowledge base maintenance with stronger access control.
                </p>
              </div>
            </div>
          </article>
        </div>
      </section>
    );
  }

  function renderGraphPanel() {
    return (
      <section className="panel">
        <div className="panel__head">
          <div>
            <p className="eyebrow">Graph</p>
            <h2>Visual knowledge graph</h2>
            <p className="section-copy">
              This visual representation comes from the RDF store for the selected pack. It shows
              ABox instances and the relations materialized in the KG. Hover a node to inspect its
              details or click it to keep the details panel open.
            </p>
          </div>
        </div>

        <div className="form-grid graph-controls">
          <label className="graph-controls__search">
            <span>Search graph</span>
            <input value={graphSearch} onChange={(event) => setGraphSearch(event.target.value)} placeholder="Search IRIs, labels, or semantic types" />
          </label>
          <label className="graph-controls__provenance">
            <span>Provenance</span>
            <div className="graph-controls__provenance-row">
              <button
                type="button"
                className={`graph-switch ${showGraphProvenance ? "is-on" : ""}`}
                onClick={() => setShowGraphProvenance((value) => !value)}
                aria-pressed={showGraphProvenance}
              >
                <span className="graph-switch__track">
                  <span className="graph-switch__thumb" />
                </span>
                <span className="graph-switch__label">
                  {showGraphProvenance ? "On" : "Off"}
                </span>
              </button>
              <small className="graph-controls__provenance-note">
                {showGraphProvenance
                  ? "Shows annotation activities and annotator agents."
                  : "Hides annotation activities and annotator agents."}
              </small>
            </div>
          </label>
        </div>

        <div className="graph-board">
          {filteredGraphNodes.length === 0 ? (
            <div className="table__empty" style={{ padding: 40 }}>
              No graph data is available for this pack, or the search returned no matches.
            </div>
          ) : (
            <GraphForce nodes={filteredGraphNodes} edges={filteredGraphEdges} />
          )}
        </div>

        <article className="graph-summary">
          <div className="graph-summary__item">
            <span>Visible nodes</span>
            <strong>{filteredGraphNodes.length}</strong>
          </div>
          <div className="graph-summary__item">
            <span>Visible links</span>
            <strong>{filteredGraphEdges.length}</strong>
          </div>
          <div className="graph-summary__item">
            <span>Connected groups</span>
            <strong>{filteredGraphComponentCount}</strong>
          </div>
        </article>
      </section>
    );
  }

  function renderOntology() {
    return (
      <section className="panel ontology-panel">
        <div className="panel__head">
          <div className="ontology-panel__intro">
            <p className="eyebrow">Ontology</p>
            <h2>TBox reference</h2>
            <p className="section-copy">
              Review the core NORMA modeling layer used by the rules, ABox, and visual KG.
              This tab is a compact orientation view for the current ontology used by the toolkit.
            </p>
          </div>
          <div className="ontology-panel__actions" />
        </div>
        <div className="ontology-panel__meta">
          <a
            className="ontology-panel__meta-item ontology-panel__meta-item--doc"
            href={ONTOLOGY_DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span>Ontology documentation</span>
            <strong>{ONTOLOGY_DOCS_URL}</strong>
          </a>
          <div className="ontology-panel__meta-item">
            <span>Primary namespace</span>
            <strong>`norma:` for NORMA classes and properties</strong>
          </div>
          <div className="ontology-panel__meta-item">
            <span>Core alignments</span>
            <strong>PROV O, ELI, and SKOS, with LKIF-Core mappings and FOAF instance metadata</strong>
          </div>
        </div>
        <div className="ontology-panel__sections">
          <section className="ontology-panel__section">
            <div className="ontology-panel__section-head">
              <strong>Core NORMA classes</strong>
            </div>
            <p className="ontology-panel__section-copy">
              These are the main categories currently exposed across the rules, ABox, graph, and review views.
            </p>
            <div className="ontology-panel__row-list">
              {ONTOLOGY_ITEMS.map((item) => (
                <div className="ontology-panel__row" key={item}>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="ontology-panel__section">
            <div className="ontology-panel__section-head">
              <strong>Core modeling pattern</strong>
            </div>
            <div className="ontology-panel__row-list">
              <div className="ontology-panel__row">
                <span>
                  NORMA does not link a legal condition directly to a branch outcome in the TBox. Instead, a <code>norma:LegalCondition</code> points to a <code>norma:TriggerEvent</code> with <code>norma:hasTrigger</code>.
                </span>
              </div>
              <div className="ontology-panel__row">
                <span>
                  The trigger event records the evaluated branch with <code>norma:hasOutcome</code> and activates the relevant norm with <code>norma:activatesNorm</code>.
                </span>
              </div>
              <div className="ontology-panel__row">
                <span>
                  The shortcut property <code>norma:triggersNorm</code> is derived from that pattern, but clients that need the true or false branch should inspect the trigger event and its outcome.
                </span>
              </div>
            </div>
          </section>

          <section className="ontology-panel__section">
            <div className="ontology-panel__section-head">
              <strong>External standards and vocabularies</strong>
              <span className="ontology-panel__count">{EXTERNAL_ONTOLOGIES.length}</span>
            </div>
            <p className="ontology-panel__section-copy">
              PROV O and ELI provide the main semantic alignments. SKOS supports controlled
              vocabularies, LKIF-Core appears as an informative mapping layer, and Dublin Core,
              BIBO, VANN, and FOAF are mainly used for ontology and instance metadata.
            </p>
            <div className="ontology-panel__table">
              {EXTERNAL_ONTOLOGIES.map((item) => (
                <article className="ontology-panel__table-row" key={item.url}>
                  <div className="ontology-panel__table-main">
                    <strong>{item.name}</strong>
                    <span>{item.prefix}</span>
                  </div>
                  <code>{item.url}</code>
                  <p>{item.note}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="ontology-panel__section">
            <div className="ontology-panel__section-head">
              <strong>How to read this notation</strong>
            </div>
            <div className="ontology-panel__row-list">
              <div className="ontology-panel__row">
                <span>
                  Prefixes such as <code>norma:</code>, <code>prov:</code>, and <code>xsd:</code> are compact labels used in RDF and OWL files instead of repeating full URIs every time.
                </span>
              </div>
              <div className="ontology-panel__row">
                <span>
                  Use this tab as a quick reference to check whether the ABox, SWRL rules, graph view, and ontology are aligned semantically.
                </span>
              </div>
              <div className="ontology-panel__row">
                <span>
                  If you see <code>Obligation</code>, <code>Prohibition</code>, or <code>Recommendation</code> in the app, they are ABox individuals typed with these ontology classes rather than separate ontologies or ad hoc UI categories.
                </span>
              </div>
            </div>
          </section>
        </div>
      </section>
    );
  }

  function renderActiveView() {
    switch (activeView) {
      case "evaluator":
        return renderEvaluator();
      case "norms":
        return renderNorms();
      case "artifacts":
        return renderArtifacts();
      case "rules":
        return renderRules();
      case "sparql":
        return renderSparql();
      case "entities":
        return renderEntitiesPanel();
      case "graph":
        return renderGraphPanel();
      case "ontology":
        return renderOntology();
      default:
        return renderOverview();
    }
  }

  return (
    <div className="dashboard">
      <Sidebar
        packs={packs}
        selectedPack={selectedPack}
        onSelectPack={(pack) => { setSelectedPack(pack); setSidebarOpen(false); }}
        activeView={activeView}
        onSelectView={(view) => { setActiveView(view); setSidebarOpen(false); }}
        onOpenPackCreator={() => { openPackCreator(); setSidebarOpen(false); }}
        onUploadFile={handleUpload}
        onAppendFile={handleAppendUpload}
        isUploading={isUploading}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="dashboard__content">
        {/* Mobile header — only visible on small screens via CSS */}
        <header className="mobile-header">
          <div className="mobile-header__brand">
            <span className="mobile-header__logo">N</span>
            <div>
              <div>NORMA</div>
              <div className="mobile-header__view">{VIEW_LABELS[activeView] || "Overview"}</div>
            </div>
          </div>
          <div className="mobile-header__actions">
            <button type="button" className="hamburger" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
              <span />
              <span />
              <span />
            </button>
          </div>
        </header>

        {/* Desktop topbar */}
        <div className="topbar">
          <div className="topbar__breadcrumb">
            <span className="topbar__root">NORMA</span>
            {selectedPack && (
              <>
                <span className="topbar__sep">›</span>
                <span className="topbar__pack">{selectedPack}</span>
              </>
            )}
            <span className="topbar__sep">›</span>
            <span className="topbar__view">{VIEW_LABELS[activeView] || "Overview"}</span>
          </div>
          <div className="topbar__right">
            {selectedPackSummary ? (
              <>
                <span
                  className={`topbar__badge ${selectedPackSummary.can_rebuild ? "topbar__badge--official" : "topbar__badge--temporary"}`}
                >
                  {selectedPackSummary.can_rebuild ? "Official" : "Temporary"}
                </span>
                <span className="topbar__badge topbar__badge--rules">
                  {selectedPackSummary.rule_count} rules
                </span>
              </>
            ) : null}
          </div>
        </div>

        {error ? <div className="alert alert--error">{error}</div> : null}
        {notice ? <div className="alert alert--info">{notice}</div> : null}

        {isLoadingPack ? (
          <div className="loading-row">
            <span className="spinner" />
            Loading pack data…
          </div>
        ) : !selectedPack && activeView !== "overview" ? (
          <div className="no-pack-banner">
            <div className="no-pack-banner__icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="21 8 21 21 3 21 3 8" />
                <rect x="1" y="3" width="22" height="5" />
                <line x1="10" y1="12" x2="14" y2="12" />
              </svg>
            </div>
            <h3>No pack selected</h3>
            <p>Select a regulation pack from the sidebar or create a new one from the Overview page to start exploring.</p>
          </div>
        ) : (
          renderActiveView()
        )}
      </main>
    </div>
  );
}
