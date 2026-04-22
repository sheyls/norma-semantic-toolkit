import { Link } from "react-router-dom";
import ccByLogo from "../assets/logos/cc-by-logo.png";
import oegUpmLogo from "../assets/logos/oeg-upm-logo.png";

const OUTPUT_LINKS = [
  {
    title: "Knowledge base",
    description: "Inspect the generated ABox and the regulation-backed semantic material.",
    href: "/dashboard",
    meta: "ABox, RDF, reusable entities",
  },
  {
    title: "Rules",
    description: "Review the legal rules in both human-readable form and OWL/SWRL-oriented output.",
    href: "/dashboard",
    meta: "Norm logic, traceability, formal syntax",
  },
  {
    title: "Semantic graph",
    description: "Explore the semantic knowledge graph with clearer visual structure and node details.",
    href: "/dashboard",
    meta: "Instances, relations, ontology-backed graph",
  },
  {
    title: "SPARQL workspace",
    description: "Query the generated knowledge graph directly when you need deeper semantic inspection.",
    href: "/dashboard",
    meta: "Reusable presets and custom queries",
  },
];

const REFERENCE_LINKS = [
  {
    label: "Web app repository",
    href: "https://github.com/sheyls/deontic-rule-bpmn",
  },
  {
    label: "NORMA ontology repository",
    href: "https://github.com/norma-project/norma-ontology",
  },
  {
    label: "CC BY 4.0 licence",
    href: "https://creativecommons.org/licenses/by/4.0/",
  },
  {
    label: "Ontology IRI",
    href: "https://w3id.org/norma-ontology",
  },
];

export default function Home() {
  return (
    <main className="home">
      <section className="home__frame">
        <div className="home__hero">
          <div className="home__hero-copy">
            <p className="eyebrow">NORMA Workspace</p>
            <h1>NORMA: From Annotated BPMN to Normative Knowledge Graphs.</h1>
            <p className="home__lead">
              NORMA transforms legally annotated BPMN into semantic, linked normative knowledge. It
              supports compliance analysis, but its main purpose is the conversion of annotated
              process models into ontology-backed knowledge graphs, reusable rules, and queryable
              semantic artifacts.
            </p>

            <div className="hero__actions">
              <Link to="/dashboard" className="button button--hero-primary">
                <span>Open workspace</span>
                <strong>Start exploring NORMA</strong>
              </Link>
              <a
                href="https://github.com/norma-project/norma-ontology"
                className="button button--hero-secondary"
                target="_blank"
                rel="noreferrer"
              >
                <span>Ontology reference</span>
                <strong>View ontology</strong>
              </a>
            </div>

            <div className="home__ribbon">
              <span>Compliance review</span>
              <span>Semantic knowledge graph</span>
              <span>Open-source research tooling</span>
            </div>
          </div>

          <div className="home__hero-panel">
            <div className="home__signal">
              <span>Core workflow</span>
              <strong>Annotated BPMN, ontology-backed conversion, rule extraction, graph inspection</strong>
            </div>
            <div className="home__signal">
              <span>Semantic outputs</span>
              <strong>Knowledge base, rules, graph visualisation, ontology, SPARQL</strong>
            </div>
            <div className="home__signal">
              <span>Design principle</span>
              <strong>One focused section at a time, with a consistent left-hand navigation</strong>
            </div>
          </div>
        </div>

        <section className="home__section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Outputs</p>
              <h2>Everything the workspace produces, linked from one place</h2>
            </div>
            <p className="section-copy">
              The homepage now works as a stable project entry point, so users can understand the
              semantic outputs before moving into the dashboard.
            </p>
          </div>

          <div className="home__link-grid">
            {OUTPUT_LINKS.map((item) => (
              <Link key={item.title} to={item.href} className="home__link-card">
                <span>{item.meta}</span>
                <strong>{item.title}</strong>
                <p>{item.description}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="home__section home__section--about" id="about">
          <div className="section-heading">
            <div>
              <p className="eyebrow">About Us</p>
              <h2>NORMA is an open research workspace for legal BPMN annotations and semantic compliance assets.</h2>
            </div>
            <p className="section-copy">
              This project brings together BPMN-based legal annotation, ontology engineering, and
              semantic knowledge graph generation in a single workflow-oriented interface.
            </p>
          </div>

          <div className="home__about-grid">
            <article className="home__about-card home__about-card--primary">
              <div className="affiliation-mark">
                <img src={oegUpmLogo} alt="Ontology Engineering Group UPM logo" />
              </div>
              <div className="home__about-copy">
                <p className="eyebrow">Affiliation</p>
                <h3>Ontology Engineering Group, Universidad Politécnica de Madrid</h3>
                <p>
                  The interface is intended for users working with legal knowledge graphs, ontology
                  engineering, and regulation-driven compliance workflows.
                </p>
              </div>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Maintainer</p>
              <h3>Project authorship</h3>
              <p>
                Sheyla Leyva-Sánchez is listed in the ontology metadata as creator, with NORMA
                project contributors acknowledged as contributors.
              </p>
              <div className="home__contact-list">
                <a
                  href="https://github.com/sheyls/deontic-rule-bpmn"
                  target="_blank"
                  rel="noreferrer"
                >
                  Source repository
                </a>
                <a
                  href="https://github.com/sheyls"
                  target="_blank"
                  rel="noreferrer"
                >
                  Author GitHub profile
                </a>
                <span>Email address can be added once you choose the public contact to display.</span>
              </div>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Licence</p>
              <h3>CC BY 4.0</h3>
              <p>
                The repository and ontology metadata point to a Creative Commons Attribution 4.0
                licence, making the project easy to reuse with attribution.
              </p>
              <a
                href="https://creativecommons.org/licenses/by/4.0/"
                className="license-badge"
                target="_blank"
                rel="noreferrer"
              >
                <img src={ccByLogo} alt="Creative Commons BY 4.0 licence logo" className="license-badge__logo" />
                <span className="license-badge__text">CC BY 4.0</span>
              </a>
            </article>

            <article className="home__about-card">
              <p className="eyebrow">Project Links</p>
              <h3>References</h3>
              <div className="home__reference-list">
                {REFERENCE_LINKS.map((item) => (
                  <a key={item.label} href={item.href} target="_blank" rel="noreferrer">
                    {item.label}
                  </a>
                ))}
              </div>
            </article>
          </div>
        </section>
      </section>
    </main>
  );
}
