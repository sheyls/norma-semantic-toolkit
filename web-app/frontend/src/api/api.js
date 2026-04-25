const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json") || contentType.includes("sparql-results+json")) {
    return response.json();
  }
  return response.text();
}

function downloadUrl(path) {
  return `${API_BASE}${path}`;
}

export function getHealth() {
  return request("/api/health");
}

export function getPacks() {
  return request("/api/packs");
}

export function getPackNorms(pack) {
  return request(`/api/pack/${pack}/norms`);
}

export function getPackRules(pack) {
  return request(`/api/pack/${pack}/rules`);
}

export function rebuildPack(pack) {
  return request(`/api/pack/${pack}/rebuild`, {
    method: "POST",
  });
}

export function getPackAbox(pack) {
  return request(`/api/pack/${pack}/abox`);
}

export function getPackSwrl(pack) {
  return request(`/api/pack/${pack}/swrl`);
}

export function getPackConditions(pack) {
  return request(`/api/pack/${pack}/conditions`);
}

export function evaluatePack(pack, answers) {
  return request(`/api/pack/${pack}/evaluate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(answers),
  });
}

export function getPackEntities(pack) {
  return request(`/api/pack/${pack}/entities`);
}

export function updatePackEntities(pack, payload) {
  return request(`/api/pack/${pack}/entities`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function getSparqlPresets() {
  return request("/api/sparql-presets");
}

export function runSparql(pack, query) {
  return request(`/api/sparql/${pack}`, {
    method: "POST",
    headers: {
      "Content-Type": "text/plain",
    },
    body: query,
  });
}

export function getPackGraph(pack) {
  return request(`/api/pack/${pack}/graph`);
}

export function updateNorm(pack, normId, payload) {
  return request(`/api/pack/${pack}/norm/${encodeURIComponent(normId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function getAboxDownloadUrl(pack) {
  return downloadUrl(`/api/pack/${pack}/download/abox`);
}

export function getAboxRdfDownloadUrl(pack) {
  return downloadUrl(`/api/pack/${pack}/download/abox-rdf`);
}

export function getSwrlDownloadUrl(pack) {
  return downloadUrl(`/api/pack/${pack}/download/swrl`);
}

export function getTemplateDownloadUrl() {
  return downloadUrl("/api/download/template");
}

export function uploadBpmn(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/upload", {
    method: "POST",
    body: form,
  });
}

export function appendBpmnToPack(pack, file) {
  const form = new FormData();
  form.append("file", file);
  return request(`/api/pack/${pack}/append`, {
    method: "POST",
    body: form,
  });
}
