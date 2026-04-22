# Web-App Runtime Data

This folder contains local runtime state for `web-app/backend/`.

Typical contents:

- `norma.sqlite3`: metadata database
- `graph-stores/`: persisted Oxigraph stores
- `uploads/`: user-created workspace packs

These files are runtime artifacts, not source assets. They should generally stay out of version control.

Canonical source packs and assets live at the repository root:

- `regulations/`
- `ontology/`
- `camunda-template/`
