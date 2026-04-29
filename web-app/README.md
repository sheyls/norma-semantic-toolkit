# NORMA Web App

This folder is the application layer of the NORMA monorepo.

The repository is organised as two clean layers:

- root-level core assets and engine:
  `norma_engine/`, `regulations/`, `ontology/`, `camunda-template/`
- `web-app/`:
  React frontend, FastAPI backend, and app runtime data

The intended dependency direction is:

- `web-app` may depend on the core layer
- the core layer should not depend on `web-app`

## Required Configuration

Copy `.env.example` to `.env` if you want local overrides.

Important variables:

- `NORMA_DATA_DIR`
- `NORMA_CORE_ROOT`
- `NORMA_REGULATIONS_DIR`
- `NORMA_ONTOLOGY_PATH`
- `NORMA_CAMUNDA_TEMPLATE_PATH`
- `VITE_PROXY_TARGET`
- `VITE_API_BASE`

In the monorepo, the default behavior already resolves:

- `norma_engine/` from the repository root
- `regulations/` from the repository root
- `ontology/norma-o-v1.ttl` from the repository root
- `camunda-template/camunda8-compliance-template.json` from the repository root

You only need environment variables if you intentionally move those locations.

Example override setup:

```env
NORMA_CORE_ROOT=/absolute/path/to/core-repo
NORMA_REGULATIONS_DIR=/absolute/path/to/core-repo/regulations
NORMA_ONTOLOGY_PATH=/absolute/path/to/core-repo/ontology/norma-o-v1.ttl
NORMA_CAMUNDA_TEMPLATE_PATH=/absolute/path/to/core-repo/camunda-template/camunda8-compliance-template.json
NORMA_DATA_DIR=./backend/data
VITE_PROXY_TARGET=http://localhost:8000
```

## Backend Setup

Install Python dependencies:

```bash
cd web-app
pip install -r backend/requirements.txt
```

Run the API from the `web-app/` directory:

```bash
uvicorn backend.main:app --reload --app-dir .
```

## Frontend Setup

Install frontend dependencies:

```bash
cd web-app/frontend
npm install
```

Run the frontend:

```bash
npm run dev
```

By default, the Vite dev server proxies `/api` to `http://localhost:8000`.

## Source Data vs Runtime Data

The monorepo keeps canonical source assets at the repository root:

- `regulations/`
- `ontology/`
- `camunda-template/`
- `norma_engine/`

`web-app/backend/data/` is different: it is runtime state created by the app, not the source of truth for legal packs.

## What Not To Commit

This app creates local runtime state in `web-app/backend/data/`:

- SQLite database
- graph store files
- uploaded packs

Those files are ignored by `web-app/.gitignore`.
