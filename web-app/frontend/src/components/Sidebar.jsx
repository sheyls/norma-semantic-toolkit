import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import normaLogo from "../assets/logos/norma-logo.png";

/* Minimal inline SVG icon — Feather-style, 24-unit grid */
function NavIcon({ d, children, ...rest }) {
  return (
    <svg
      className="sidebar__icon"
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {d ? <path d={d} /> : children}
    </svg>
  );
}

const ICONS = {
  home: (
    <>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </>
  ),
  overview: (
    <>
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </>
  ),
  evaluator: (
    <>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </>
  ),
  artifacts: (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </>
  ),
  rules: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </>
  ),
  sparql: (
    <>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </>
  ),
  ontology: (
    <>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </>
  ),
  norms: (
    <>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  graph: (
    <>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </>
  ),
  pack: (
    <>
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <line x1="10" y1="12" x2="14" y2="12" />
    </>
  ),
  folder: (
    <>
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </>
  ),
};

const CORE_ITEMS = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "evaluator", label: "Norm Determination", icon: "evaluator" },
];

const SEMANTIC_ITEMS = [
  { id: "artifacts", label: "Knowledge Base", icon: "artifacts" },
  { id: "rules", label: "Rules", icon: "rules" },
  { id: "sparql", label: "SPARQL", icon: "sparql" },
  { id: "ontology", label: "Ontology", icon: "ontology" },
];

const VISUAL_ITEMS = [
  { id: "norms", label: "Norm Review", icon: "norms" },
  { id: "graph", label: "KG Visualisation", icon: "graph" },
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
  isOpen,
  onClose,
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

  function MenuItem({ item }) {
    return (
      <button
        key={item.id}
        type="button"
        className={`sidebar__menu-item ${activeView === item.id ? "is-active" : ""}`}
        onClick={() => { onSelectView(item.id); onClose?.(); }}
      >
        <NavIcon>{ICONS[item.icon]}</NavIcon>
        {item.label}
      </button>
    );
  }

  return (
    <aside className={`sidebar${isOpen ? " is-mobile-open" : ""}`}>
      {/* Brand */}
      <div className="sidebar__brand">
        <img className="sidebar__logo" src={normaLogo} alt="NORMA logo" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <strong>NORMA</strong>
          <p>Semantic toolkit</p>
        </div>
        {onClose && (
          <button type="button" className="sidebar__mobile-close" onClick={onClose} aria-label="Close menu">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>

      {/* Top navigation */}
      <nav className="sidebar__nav">
        <NavLink to="/" className="sidebar__link">
          <NavIcon>{ICONS.home}</NavIcon>
          Home
        </NavLink>
        <NavLink to="/dashboard" className="sidebar__link">
          <NavIcon>{ICONS.dashboard}</NavIcon>
          Dashboard
        </NavLink>
      </nav>

      <div className="sidebar__divider" />

      {/* Core Workflow */}
      <div className="sidebar__section">
        <h3>Core Workflow</h3>
        <div className="sidebar__menu">
          {CORE_ITEMS.map((item) => (
            <MenuItem key={item.id} item={item} />
          ))}
        </div>
      </div>

      {/* Semantic Artifacts */}
      <div className="sidebar__section">
        <h3>Semantic Artifacts</h3>
        <div className="sidebar__menu">
          {SEMANTIC_ITEMS.map((item) => (
            <MenuItem key={item.id} item={item} />
          ))}
        </div>
      </div>

      {/* Visual Exploration */}
      <div className="sidebar__section">
        <h3>Visual Exploration</h3>
        <div className="sidebar__menu">
          {VISUAL_ITEMS.map((item) => (
            <MenuItem key={item.id} item={item} />
          ))}
        </div>
      </div>

      <div className="sidebar__divider" />

      {/* Pack Management */}
      <div className="sidebar__section">
        <h3>Pack Management</h3>
        <div className="sidebar__pack-workspace">
          <label>
            <span className="sidebar__field-label">Selected pack</span>
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
              <span
                style={{
                  color: selectedPackMeta.can_rebuild
                    ? "rgba(26,122,74,0.9)"
                    : "rgba(180,83,9,0.9)",
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                {selectedPackMeta.can_rebuild ? "● Official" : "● Temporary"}
              </span>
            </div>
          ) : null}

          <p className="sidebar__pack-helper">
            Choose one path: create a new temporary pack, or add a BPMN into the selected pack.
          </p>

          <div className="sidebar__pack-actions">
            <button
              type="button"
              className="sidebar__menu-item sidebar__menu-item--accent"
              onClick={onOpenPackCreator}
            >
              <NavIcon>{ICONS.pack}</NavIcon>
              Open BPMN actions
            </button>
            <label className="sidebar__upload">
              <input type="file" accept=".bpmn" onChange={onUploadFile} disabled={isUploading} />
              <span className="sidebar__upload-copy">
                <strong>{isUploading ? "Uploading..." : "Create new temporary pack"}</strong>
                <small>Build a separate temporary pack from one BPMN file</small>
              </span>
            </label>
            <label className={`sidebar__upload ${!selectedPack ? "is-disabled" : ""}`}>
              <input
                type="file"
                accept=".bpmn"
                onChange={onAppendFile}
                disabled={isUploading || !selectedPack}
              />
              <span className="sidebar__upload-copy">
                <strong>
                  {isUploading
                    ? "Uploading..."
                    : selectedPackMeta?.can_rebuild
                      ? "Add BPMN to selected official pack"
                      : "Add BPMN to selected temporary pack"}
                </strong>
                <small>
                  {selectedPackMeta?.can_rebuild
                    ? "Creates a new temporary workspace copied from the official pack"
                    : "Extends the currently selected temporary pack"}
                </small>
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Regulation Packs */}
      <div className="sidebar__section">
        <h3>Regulation Packs</h3>
        <div className="sidebar__pack-filters">
          {[
            { id: "all", label: "All", count: packs.length },
            { id: "official", label: "Official", count: officialCount },
            { id: "temporary", label: "Temp", count: temporaryCount },
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              className={`sidebar__chip ${packFilter === f.id ? "is-active" : ""}`}
              onClick={() => setPackFilter(f.id)}
            >
              {f.label}
              <small>{f.count}</small>
            </button>
          ))}
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
          {packs.length > 0 && filteredPacks.length === 0 ? (
            <p className="muted">No packs match this filter.</p>
          ) : null}
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

      {/* Footer scope note */}
      <div className="sidebar__section" style={{ marginTop: "auto" }}>
        <div className="sidebar__divider" style={{ margin: "0 0 12px" }} />
        <p className="muted" style={{ fontSize: "0.72rem", lineHeight: 1.6, padding: "0 4px" }}>
          Inspect artifacts, query the graph, and determine applicable norms for the selected pack.
        </p>
      </div>
    </aside>
  );
}
