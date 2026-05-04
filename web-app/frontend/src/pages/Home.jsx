import { Link } from "react-router-dom";
import ccByLogo from "../assets/logos/cc-by-logo.png";
import normaLogo from "../assets/logos/norma-logo.png";
import oegUpmLogo from "../assets/logos/oeg-upm-logo.png";

const FEATURES = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
      </svg>
    ),
    title: "Knowledge Base",
    description: "ABox instances generated from annotated BPMN and serialised as Turtle or RDF/XML.",
    tag: "ABox · RDF",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
    title: "Rules",
    description: "Human-readable rule paths and formal SWRL OWL/XML output for norm logic traceability.",
    tag: "SWRL · OWL 2",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
      </svg>
    ),
    title: "Generated Graph",
    description: "Interactive D3 force graph of ABox instances, relations, and ontology alignments.",
    tag: "Graph · SPARQL",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
      </svg>
    ),
    title: "SPARQL Queries",
    description: "Query the generated graph directly with curated presets or custom queries.",
    tag: "SPARQL 1.1",
  },
];

const STACK = [
  { label: "Compliance review" },
  { label: "OWL 2 + SWRL" },
  { label: "PROV-O · ELI · FOAF" },
  { label: "Open source research" },
];


export default function Home() {
  return (
    <main className="home">
      <section className="home__frame">

        {/* ── Hero ── */}
        <div className="home__hero">
          <div className="home__hero-copy">
            <div className="home__brand-mark" aria-hidden="true">
              <img src={normaLogo} alt="" className="home__brand-mark__logo" />
              <span>NORMA Semantic toolkit</span>
            </div>
            <h1>From annotated BPMN to semantic artifacts.</h1>
            <p className="home__lead">
              NORMA converts legally annotated process models into semantic, linked normative
              knowledge, producing OWL 2 ABoxes, SWRL rules, and queryable RDF graphs
            </p>

            <div className="hero__actions">
              <Link to="/dashboard" className="button button--hero-primary">
                <span>Interactive workspace</span>
                <strong>Open toolkit →</strong>
              </Link>
            </div>

            <div className="home__ribbon">
              {STACK.map((s) => <span key={s.label}>{s.label}</span>)}
            </div>
          </div>

          <div className="home__hero-panel">
            <div className="home__signal">
              <span>Input</span>
              <strong>Annotated BPMN with legal metadata (Camunda element templates)</strong>
            </div>
            <div className="home__signal">
              <span>Pipeline</span>
              <strong>ABox builder → SWRL extractor → RDF store → SPARQL endpoint</strong>
            </div>
            <div className="home__signal">
              <span>Standards alignment</span>
              <strong>OWL 2, SWRL, PROV-O, ELI, FOAF, SKOS — all open W3C vocabularies</strong>
            </div>
          </div>
        </div>

        {/* ── Features ── */}
        <section className="home__section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Outputs</p>
              <h2>Generated semantic artifacts in one workspace</h2>
            </div>
            <p className="section-copy">
              Every artifact is derived from the annotated BPMN and can be inspected, downloaded,
              or queried directly from the dashboard.
            </p>
          </div>

          <div className="home__link-grid">
            {FEATURES.map((item) => (
              <Link key={item.title} to="/dashboard" className="home__link-card">
                <div className="home__link-card__icon">{item.icon}</div>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.description}</p>
                </div>
                <span className="home__link-card__tag">{item.tag}</span>
              </Link>
            ))}
          </div>
        </section>

        {/* ── About ── */}
        <section className="home__section home__section--about" id="about">
          <div className="section-heading">
            <div>
              <p className="eyebrow">About</p>
              <h2>Open research toolkit for legal BPMN annotations</h2>
            </div>
          </div>

          <div className="home__about-grid">
            <article className="home__about-card home__about-card--primary">
              <div className="affiliation-mark">
                <img src={oegUpmLogo} alt="Ontology Engineering Group UPM logo" />
              </div>
              <div className="home__about-copy">
                <p className="eyebrow" style={{ color: "rgba(147,197,253,0.82)" }}>Affiliation</p>
                <h3 style={{ color: "white" }}>Ontology Engineering Group — UPM</h3>
                <p style={{ color: "rgba(226,232,240,0.8)" }}>
                  The toolkit targets users working with legal graphs, ontology
                  engineering, and regulation-based semantic workflows.
                </p>
              </div>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Maintainer</p>
              <div className="home__person-row">
                <h3>Sheyla Leyva-Sánchez</h3>
                <a href="https://github.com/sheyls" target="_blank" rel="noreferrer" className="home__inline-link">
                  GitHub ↗
                </a>
              </div>
              <p>Creator and primary contributor — Ontology Engineering Group, UPM.</p>
              <a href="https://github.com/sheyls/norma-semantic-toolkit" target="_blank" rel="noreferrer" className="home__repo-link">
                Source repository ↗
              </a>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Contributors</p>
              <div className="home__contributor-columns">
                <div>
                  <p className="home__contributor-subheading">Ontology Engineering</p>
                  <ul className="home__contributor-list">
                    <li>
                      <strong>María Poveda-Villalón</strong>
                      <span>Ontology Engineering Group, UPM</span>
                    </li>
                    <li>
                      <strong>Víctor Rodríguez-Doncel</strong>
                      <span>Ontology Engineering Group, UPM</span>
                    </li>
                  </ul>
                </div>
                <div>
                  <p className="home__contributor-subheading">Legal Experts</p>
                  <ul className="home__contributor-list">
                    <li>
                      <strong>Ilaria Angela Amantea</strong>
                      <span>University of Turin</span>
                    </li>
                    <li>
                      <strong>Marinella Quaranta</strong>
                      <span>University of Bologna</span>
                    </li>
                  </ul>
                </div>
              </div>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Licence</p>
              <h3>CC BY 4.0</h3>
              <p>
                Repository and ontology metadata reference a Creative Commons Attribution 4.0
                licence, supporting reuse with appropriate attribution.
              </p>
              <a
                href="https://creativecommons.org/licenses/by/4.0/"
                className="license-badge"
                target="_blank"
                rel="noreferrer"
              >
                <img src={ccByLogo} alt="CC BY 4.0" className="license-badge__logo" />
                <span className="license-badge__text">CC BY 4.0</span>
              </a>
            </article>

          </div>
        </section>

      </section>
    </main>
  );
}
