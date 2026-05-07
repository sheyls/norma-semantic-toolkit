import * as d3 from "d3";
import { useEffect, useMemo, useRef, useState } from "react";

const NODE_COLORS = {
  Obligation: "#c25b2a",
  Prohibition: "#b42318",
  Permission: "#0f766e",
  Recommendation: "#2563eb",
  NegativeRecommendation: "#8b5cf6",
  ConstitutiveRule: "#15803d",
  LegalAgent: "#1d4ed8",
  OrganizationalLegalAgent: "#1e3a8a",
  LegalAction: "#0891b2",
  LegalObject: "#7c3f8c",
  LegalCondition: "#d97706",
  TriggerEvent: "#475569",
  TrueOutcome: "#15803d",
  FalseOutcome: "#b91c1c",
  LegalSource: "#7c2d12",
  LegalSourceExpression: "#a16207",
  AnnotationActivity: "#64748b",
  AnnotatorAgent: "#334155",
  BindingForce: "#0f4c81",
  ComplianceCriticality: "#be123c",
  NormStatus: "#4b5563",
  Resource: "#6b7280",
};

const LEGEND_ORDER = [
  "Obligation",
  "Prohibition",
  "Permission",
  "Recommendation",
  "NegativeRecommendation",
  "ConstitutiveRule",
  "LegalCondition",
  "LegalAgent",
  "OrganizationalLegalAgent",
  "LegalAction",
  "LegalObject",
  "LegalSource",
  "LegalSourceExpression",
  "AnnotationActivity",
  "AnnotatorAgent",
  "BindingForce",
  "ComplianceCriticality",
  "NormStatus",
  "Resource",
];

function nodeColor(type) {
  return NODE_COLORS[type] || "#225c63";
}

function shortenLabel(value, limit = 18) {
  const text = String(value || "");
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1)}…`;
}

function shortenUri(value) {
  const text = String(value || "");
  if (!text) return "";
  if (text.includes("#")) return text.split("#").pop() || text;
  return text.split("/").pop() || text;
}

function labelLines(value, lineLength = 12, maxLines = 3) {
  const words = String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean);

  if (!words.length) {
    return [];
  }

  const lines = [];
  let current = words[0];

  for (let i = 1; i < words.length; i += 1) {
    const next = words[i];
    if (`${current} ${next}`.length <= lineLength) {
      current = `${current} ${next}`;
    } else {
      lines.push(current);
      current = next;
      if (lines.length === maxLines - 1) {
        break;
      }
    }
  }

  if (lines.length < maxLines) {
    const remainingWords = words.slice(lines.join(" ").split(" ").filter(Boolean).length);
    const remaining = remainingWords.join(" ").trim();
    if (remaining) {
      lines.push(remaining);
    }
  }

  return lines
    .filter(Boolean)
    .slice(0, maxLines)
    .map((line, index, arr) => {
      if (index === arr.length - 1 && arr.length === maxLines && line.length > lineLength + 4) {
        return `${line.slice(0, lineLength)}…`;
      }
      return line;
    });
}

function hexToRgb(hex) {
  const value = String(hex || "").replace("#", "");
  if (value.length !== 6) return { r: 34, g: 92, b: 99 };
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function textColorForFill(fill) {
  const { r, g, b } = hexToRgb(fill);
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return luminance > 0.58 ? "#10222f" : "#ffffff";
}

function nodeDetailRows(node) {
  const rows = [
    { label: "URI", value: node.id, tone: "code" },
    { label: "Label", value: node.label || shortenUri(node.id) },
    { label: "Type", value: node.type },
  ];

  if (node.deontic_id) {
    rows.push({ label: "Deontic ID", value: node.deontic_id });
  }

  if (node.norm_statement) {
    rows.push({ label: "Norm statement", value: node.norm_statement });
  }

  if (node.condition_statement) {
    rows.push({ label: "Condition statement", value: node.condition_statement });
  }

  if (node.regulation) {
    rows.push({
      label: "Regulation",
      value: `${node.regulation}${node.article ? ` · Art. ${node.article}` : ""}${node.paragraph ? ` · § ${node.paragraph}` : ""}`,
    });
  }

  if (node.agent) {
    rows.push({ label: "Legal agent", value: node.agent });
  }

  if (node.action) {
    rows.push({ label: "Legal action", value: node.action });
  }

  if (node.object) {
    rows.push({ label: "Legal object", value: node.object });
  }

  if (node.trigger_condition) {
    rows.push({ label: "Trigger condition", value: node.trigger_condition });
  }

  if (node.outcome) {
    rows.push({ label: "Outcome", value: node.outcome });
  }


  if (node.source) {
    rows.push({ label: "Linked source", value: node.source, tone: "code" });
  }

  if (node.annotation_date) {
    rows.push({ label: "Annotation date", value: node.annotation_date });
  }

  if (node.confidence) {
    rows.push({ label: "Confidence", value: node.confidence });
  }

  if (node.bpmn_source) {
    rows.push({ label: "BPMN source", value: node.bpmn_source });
  }

  if (node.original_text) {
    rows.push({ label: "Original text", value: node.original_text });
  }

  return rows;
}

export default function GraphForce({ nodes, edges }) {
  const svgRef = useRef(null);
  const zoomRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const pinnedNodesRef = useRef(new Set());
  const legendTypes = useMemo(() => {
    const presentTypes = new Set(nodes.map((node) => node.type).filter(Boolean));
    return [...presentTypes].sort((left, right) => {
      const leftIndex = LEGEND_ORDER.indexOf(left);
      const rightIndex = LEGEND_ORDER.indexOf(right);
      const safeLeft = leftIndex === -1 ? LEGEND_ORDER.length : leftIndex;
      const safeRight = rightIndex === -1 ? LEGEND_ORDER.length : rightIndex;
      if (safeLeft !== safeRight) {
        return safeLeft - safeRight;
      }
      return left.localeCompare(right);
    });
  }, [nodes]);

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    if (!nodes.length) return;

    const width = svgEl.clientWidth || 900;
    const height = 580;

    // Deep-copy so D3 can add x/y/vx/vy without mutating React state
    const nodesCopy = nodes.map((n) => ({ ...n }));
    const edgesCopy = edges.map((e) => ({ source: e.source, target: e.target, label: e.label || "" }));
    const linkedNodeIds = new Map();

    for (const edge of edgesCopy) {
      if (!linkedNodeIds.has(edge.source)) linkedNodeIds.set(edge.source, new Set());
      if (!linkedNodeIds.has(edge.target)) linkedNodeIds.set(edge.target, new Set());
      linkedNodeIds.get(edge.source).add(edge.target);
      linkedNodeIds.get(edge.target).add(edge.source);
    }

    const componentByNodeId = new Map();
    const components = [];
    const unvisited = new Set(nodesCopy.map((node) => node.id));

    while (unvisited.size > 0) {
      const [startId] = unvisited;
      const stack = [startId];
      const component = [];
      unvisited.delete(startId);

      while (stack.length > 0) {
        const nodeId = stack.pop();
        component.push(nodeId);
        const neighbors = linkedNodeIds.get(nodeId) || new Set();
        for (const neighborId of neighbors) {
          if (!unvisited.has(neighborId)) continue;
          unvisited.delete(neighborId);
          stack.push(neighborId);
        }
      }

      components.push(component);
    }

    const componentColumns = Math.max(1, Math.ceil(Math.sqrt(components.length || 1)));
    const componentRows = Math.max(1, Math.ceil((components.length || 1) / componentColumns));
    const componentAnchors = new Map();

    components.forEach((component, index) => {
      const column = index % componentColumns;
      const row = Math.floor(index / componentColumns);
      const anchor = {
        x: ((column + 0.5) / componentColumns) * width,
        y: ((row + 0.5) / componentRows) * height,
      };
      component.forEach((nodeId) => {
        componentByNodeId.set(nodeId, index);
        componentAnchors.set(nodeId, anchor);
      });
    });

    svg.append("defs")
      .append("marker")
      .attr("id", "norma-arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 42)
      .attr("refY", 0)
      .attr("markerWidth", 8)
      .attr("markerHeight", 8)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "rgba(13,59,102,0.7)");

    const g = svg.append("g");

    const zoom = d3.zoom()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => g.attr("transform", event.transform));

    svg.call(zoom);
    zoomRef.current = { zoom, svg };

    const simulation = d3
      .forceSimulation(nodesCopy)
      .force(
        "link",
        d3.forceLink(edgesCopy).id((d) => d.id).distance(156).strength(0.64),
      )
      .force("charge", d3.forceManyBody().strength(-290))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(52))
      .force("componentX", d3.forceX((d) => componentAnchors.get(d.id)?.x ?? width / 2).strength(0.14))
      .force("componentY", d3.forceY((d) => componentAnchors.get(d.id)?.y ?? height / 2).strength(0.14));

    const componentHull = g
      .append("g")
      .attr("class", "component-hulls")
      .selectAll("rect")
      .data(components.filter((component) => component.length > 1))
      .join("rect")
      .attr("rx", 26)
      .attr("ry", 26)
      .attr("fill", "#f3f8fb")
      .attr("stroke", "#d4e4ef")
      .attr("stroke-width", 1);

    const link = g
      .append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(edgesCopy)
      .join("line")
      .attr("stroke", "rgba(13,59,102,0.18)")
      .attr("stroke-width", 1.25)
      .attr("marker-end", "url(#norma-arrow)");

    const linkLabel = g
      .append("g")
      .attr("class", "link-labels")
      .selectAll("text")
      .data(edgesCopy)
      .join("text")
      .text((d) => shortenLabel(d.label, 16))
      .attr("font-size", 10)
      .attr("font-weight", 700)
      .attr("fill", "#253237")
      .attr("text-anchor", "middle")
      .attr("opacity", 0)
      .attr("pointer-events", "none");

    const node = g
      .append("g")
      .attr("class", "nodes")
      .selectAll("g")
      .data(nodesCopy)
      .join("g")
      .attr("cursor", "grab")
      .call(
        d3.drag()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            if (d.fx == null || d.fy == null) {
              d.fx = d.x;
              d.fy = d.y;
            }
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            if (!pinnedNodesRef.current.has(d.id)) {
              d.fx = null;
              d.fy = null;
            }
          }),
      );

    node
      .append("circle")
      .attr("r", 38)
      .attr("fill", "#ffffff")
      .attr("stroke", "rgba(80,125,188,0.34)")
      .attr("stroke-width", 1.5);

    node
      .append("circle")
      .attr("r", 30)
      .attr("fill", (d) => nodeColor(d.type))
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 3);

    const label = node
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("font-size", 10.5)
      .attr("font-weight", 800)
      .attr("fill", (d) => textColorForFill(nodeColor(d.type)))
      .attr("paint-order", "stroke")
      .attr("stroke", "rgba(4,8,15,0.18)")
      .attr("stroke-width", 2.2)
      .attr("stroke-linejoin", "round")
      .attr("pointer-events", "none");

    label
      .selectAll("tspan")
      .data((d) => {
        const baseLabel = d.label || shortenUri(d.id);
        const lines = labelLines(baseLabel, 12, 3);
        return lines.length ? lines : [shortenLabel(baseLabel, 14)];
      })
      .join("tspan")
      .attr("x", 0)
      .attr("dy", (_, index, arr) => (index === 0 ? `${-((arr.length - 1) * 0.62)}em` : "1.08em"))
      .text((line) => line);

    node
      .append("text")
      .text((d) => shortenLabel(d.type, 16))
      .attr("text-anchor", "middle")
      .attr("y", -48)
      .attr("font-size", 10)
      .attr("font-weight", 800)
      .attr("fill", "#0d3b66")
      .attr("paint-order", "stroke")
      .attr("stroke", "rgba(255,255,255,0.94)")
      .attr("stroke-width", 4)
      .attr("stroke-linejoin", "round")
      .attr("pointer-events", "none");

    function applyFocusState(focusId = null) {
      if (!focusId) {
        node.attr("opacity", 1);
        link
          .attr("opacity", 0.86)
          .attr("stroke", "rgba(13,59,102,0.18)")
          .attr("stroke-width", 1.25);
        linkLabel.attr("opacity", 0);
        return;
      }

      const neighborIds = linkedNodeIds.get(focusId) || new Set();

      node.attr("opacity", 1);
      link
        .attr("opacity", (d) => (d.source.id === focusId || d.target.id === focusId ? 1 : 0.4))
        .attr("stroke", (d) => (d.source.id === focusId || d.target.id === focusId ? "rgba(13,59,102,0.48)" : "rgba(13,59,102,0.16)"))
        .attr("stroke-width", (d) => (d.source.id === focusId || d.target.id === focusId ? 2.2 : 1));
      linkLabel.attr("opacity", (d) => (d.source.id === focusId || d.target.id === focusId ? 0.92 : 0));
    }

    applyFocusState(selectedNode?.id || null);

    node
      .on("mouseenter", (event, d) => {
        const rect = svgEl.getBoundingClientRect();
        setHoveredNode(d);
        applyFocusState(selectedNode?.id || d.id);
        setTooltip({
          x: event.clientX - rect.left + 12,
          y: event.clientY - rect.top - 8,
          node: d,
        });
      })
      .on("mousemove", (event, d) => {
        const rect = svgEl.getBoundingClientRect();
        setHoveredNode(d);
        applyFocusState(selectedNode?.id || d.id);
        setTooltip({
          x: event.clientX - rect.left + 14,
          y: event.clientY - rect.top - 10,
          node: d,
        });
      })
      .on("mouseleave", () => {
        setTooltip(null);
        setHoveredNode(null);
        applyFocusState(selectedNode?.id || null);
      })
      .on("click", (_, d) => {
        setSelectedNode(d);
        applyFocusState(d.id);
      })
      .on("dblclick", (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        if (pinnedNodesRef.current.has(d.id)) {
          pinnedNodesRef.current.delete(d.id);
          d.fx = null;
          d.fy = null;
        } else {
          pinnedNodesRef.current.add(d.id);
          d.fx = d.x;
          d.fy = d.y;
        }
        simulation.alpha(0.2).restart();
      });

    simulation.on("tick", () => {
      componentHull.each(function updateHull(component) {
        const componentIndex = componentByNodeId.get(component[0]);
        const members = nodesCopy.filter((node) => componentByNodeId.get(node.id) === componentIndex);
        if (!members.length) return;
        const xs = members.map((node) => node.x ?? 0);
        const ys = members.map((node) => node.y ?? 0);
        const minX = Math.min(...xs) - 68;
        const maxX = Math.max(...xs) + 68;
        const minY = Math.min(...ys) - 76;
        const maxY = Math.max(...ys) + 76;
        d3.select(this)
          .attr("x", minX)
          .attr("y", minY)
          .attr("width", Math.max(0, maxX - minX))
          .attr("height", Math.max(0, maxY - minY));
      });

      link
        .attr("x1", (d) => d.source.x ?? 0)
        .attr("y1", (d) => d.source.y ?? 0)
        .attr("x2", (d) => d.target.x ?? 0)
        .attr("y2", (d) => d.target.y ?? 0);

      linkLabel
        .attr("x", (d) => ((d.source.x ?? 0) + (d.target.x ?? 0)) / 2)
        .attr("y", (d) => ((d.source.y ?? 0) + (d.target.y ?? 0)) / 2 - 7);

      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => simulation.stop();
  }, [nodes, edges, selectedNode?.id]);

  function resetView() {
    if (zoomRef.current) {
      zoomRef.current.svg
        .transition()
        .duration(400)
        .call(zoomRef.current.zoom.transform, d3.zoomIdentity);
    }
  }

  const inspectorNode = hoveredNode || selectedNode;
  const inspectorTitle = hoveredNode ? "Node details" : selectedNode ? "Selected node" : "Details";

  return (
    <div className="graph-explorer">
      <div className="graph-explorer__canvas">
        <div className="graph-explorer__actions">
          <button
            type="button"
            className="pill graph-reset-btn"
            onClick={resetView}
          >
            Reset view
          </button>
        </div>
        <svg
          ref={svgRef}
          style={{ width: "100%", height: "580px", display: "block" }}
          aria-label="Generated graph layout"
        />
      </div>
      <aside className="graph-details graph-details--side">
        <div className="graph-details__head">
          <strong>{inspectorTitle}</strong>
          {selectedNode ? (
            <button type="button" className="pill graph-pin-btn" onClick={() => setSelectedNode(null)}>
              Clear selection
            </button>
          ) : (
            <span>{inspectorNode ? inspectorNode.type : "Hover a node"}</span>
          )}
        </div>
        <div className="graph-legend">
          <strong className="graph-legend__title">Legend</strong>
          <div className="graph-legend__list">
            {legendTypes.map((type) => (
              <div key={type} className="graph-legend__item">
                <span className="graph-legend__swatch" style={{ backgroundColor: nodeColor(type) }} />
                <span>{type}</span>
              </div>
            ))}
          </div>
        </div>
        {inspectorNode ? (
          <>
            <div className="graph-details__hero">
              <strong>{inspectorNode.label || shortenUri(inspectorNode.id)}</strong>
              <span>{inspectorNode.type}</span>
            </div>
            <div className="graph-details__rows">
              {nodeDetailRows(inspectorNode).map((row) => (
                <div key={row.label} className="graph-details__row">
                  <span>{row.label}</span>
                  {row.tone === "code" ? <code>{row.value}</code> : <strong>{row.value}</strong>}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="graph-details__empty">
            <strong>No node selected</strong>
            <p>
              Hover a node to inspect its semantic details, or click one to keep it selected while you
              explore the graph.
            </p>
          </div>
        )}
      </aside>
      {tooltip && (
        <div className="graph-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
          <strong>{tooltip.node.type}</strong>
          {nodeDetailRows(tooltip.node).map((row) => (
            <div key={row.label} className="graph-tooltip__row">
              <span>{row.label}</span>
              {row.tone === "code" ? <code>{row.value}</code> : <b>{row.value}</b>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
