import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

const CORE_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "evaluator", label: "Compliance Check" },
];

const SEMANTIC_ITEMS = [
  { id: "artifacts", label: "Knowledge Base" },
  { id: "rules", label: "Rules" },
  { id: "sparql", label: "SPARQL" },
  { id: "ontology", label: "Ontology" },
];

const VISUAL_ITEMS = [
  { id: "norms", label: "Norm Review" },
  { id: "graph", label: "Graph Visualisation" },
];

export default function Sidebar({
  packs,
  selectedPack,
  onSelectPack,
  activeView,
  onSelectView,
  onOpenPackCreator,
  onUploadFile,
  onAppendFile,
  isUploading,
}) {
  const [packQuery, setPackQuery] = useState("");
  const [packFilter, setPackFilter] = useState("all");
  const selectedPackMeta = packs.find((pack) => pack.name === selectedPack) || null;
  const filteredPacks = useMemo(() => {
    const query = packQuery.trim().toLowerCase();
    return packs.filter((pack) => {
      const isOfficial = Boolean(pack.can_rebuild);
      if (packFilter === "official" && !isOfficial) return false;
      if (packFilter === "temporary" && isOfficial) return false;
      if (!query) return true;
      return `${pack.name} ${pack.rule_count}`.toLowerCase().includes(query);
    });
  }, [packs, packFilter, packQuery]);

  const officialCount = packs.filter((pack) => pack.can_rebuild).length;
  const temporaryCount = packs.length - officialCount;

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__logo">N</span>
        <div>
          <strong>NORMA</strong>
          <p>Compliance workspace</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        <NavLink to="/" className="sidebar__link">
          Home
        </NavLink>
        <NavLink to="/dashboard" className="sidebar__link">
          Dashboard
        </NavLink>
      </nav>

      <div className="sidebar__section">
        <h3>Core Workflow</h3>
        <div className="sidebar__menu">
          {CORE_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar__menu-item ${activeView === item.id ? "is-active" : ""}`}
              onClick={() => onSelectView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar__section">
        <h3>Semantic Artifacts</h3>
        <div className="sidebar__menu">
          {SEMANTIC_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar__menu-item ${activeView === item.id ? "is-active" : ""}`}
              onClick={() => onSelectView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar__section">
        <h3>Visual Exploration</h3>
        <div className="sidebar__menu">
          {VISUAL_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar__menu-item ${activeView === item.id ? "is-active" : ""}`}
              onClick={() => onSelectView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar__section">
        <h3>Pack Workspace</h3>
        <div className="sidebar__pack-workspace">
          <label>
            <span className="sidebar__field-label">Current pack</span>
            <select
              className="sidebar__select"
              value={selectedPack}
              onChange={(event) => onSelectPack(event.target.value)}
              disabled={packs.length === 0}
            >
              {packs.length === 0 ? <option value="">No packs available</option> : null}
              {packs.map((pack) => (
                <option key={pack.name} value={pack.name}>
                  {pack.name}
                </option>
              ))}
            </select>
          </label>

          {selectedPackMeta ? (
            <div className="sidebar__pack-summary">
              <strong>{selectedPackMeta.name}</strong>
              <span>{selectedPackMeta.rule_count} rules indexed</span>
              <span>{selectedPackMeta.can_rebuild ? "Official curated pack" : "Temporary test pack"}</span>
            </div>
          ) : null}

          <div className="sidebar__pack-actions">
            <button type="button" className="sidebar__menu-item sidebar__menu-item--accent" onClick={onOpenPackCreator}>
              + Create new pack
            </button>
            <label className="sidebar__upload">
              <input type="file" accept=".bpmn" onChange={onUploadFile} disabled={isUploading} />
              <span>{isUploading ? "Uploading..." : "Import BPMN as new pack"}</span>
            </label>
            <label className={`sidebar__upload ${!selectedPack ? "is-disabled" : ""}`}>
              <input
                type="file"
                accept=".bpmn"
                onChange={onAppendFile}
                disabled={isUploading || !selectedPack}
              />
              <span>
                {isUploading
                  ? "Uploading..."
                  : selectedPackMeta?.can_rebuild
                    ? "Add BPMN to temporary workspace"
                    : "Add BPMN to selected pack"}
              </span>
            </label>
          </div>
        </div>
      </div>

      <div className="sidebar__section">
        <h3>Regulation Packs</h3>
        <div className="sidebar__pack-filters">
          <button
            type="button"
            className={`sidebar__chip ${packFilter === "all" ? "is-active" : ""}`}
            onClick={() => setPackFilter("all")}
          >
            All
            <small>{packs.length}</small>
          </button>
          <button
            type="button"
            className={`sidebar__chip ${packFilter === "official" ? "is-active" : ""}`}
            onClick={() => setPackFilter("official")}
          >
            Official
            <small>{officialCount}</small>
          </button>
          <button
            type="button"
            className={`sidebar__chip ${packFilter === "temporary" ? "is-active" : ""}`}
            onClick={() => setPackFilter("temporary")}
          >
            Temporary
            <small>{temporaryCount}</small>
          </button>
        </div>
        <label className="sidebar__pack-search">
          <span className="sidebar__field-label">Find a pack</span>
          <input
            type="text"
            value={packQuery}
            onChange={(event) => setPackQuery(event.target.value)}
            placeholder="Search by pack name"
          />
        </label>
        <div className="sidebar__packs">
          {packs.length === 0 ? <p className="muted">No packs loaded yet.</p> : null}
          {packs.length > 0 && filteredPacks.length === 0 ? <p className="muted">No packs match this filter.</p> : null}
          {filteredPacks.map((pack) => (
            <button
              key={pack.name}
              type="button"
              className={`sidebar__pack ${selectedPack === pack.name ? "is-active" : ""}`}
              onClick={() => onSelectPack(pack.name)}
            >
              <span className="sidebar__pack-main">
                <strong>{pack.name}</strong>
                <em>{pack.can_rebuild ? "Official" : "Temporary"}</em>
              </span>
              <small>{pack.rule_count} rules</small>
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar__section">
        <h3>Workspace Scope</h3>
        <p className="muted">
          Use the left navigation to move between workflow review, entity review, and the semantic
          knowledge views instead of scanning one very long page.
        </p>
      </div>
    </aside>
  );
}
