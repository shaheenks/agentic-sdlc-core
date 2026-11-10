---
name: webapp-api-lens
description: Goldfish review lens (webapp team). API contract and data model clarity - endpoints, schemas, migrations and authorization in a design or change.
---

# Lens: API and data model (webapp)

Read the document as a backend reviewer who knows FastAPI, SQLModel and Alembic but nothing
about this conversation. Judge only what the document says.

- **Endpoints:** is every new or changed endpoint listed with method, path, request and response
  schema, and status codes for errors? Could a frontend developer build against it from the
  document alone?
- **Compatibility:** does it say whether existing responses or clients break, and how the
  generated frontend client changes?
- **Data model:** are new tables, columns, indexes and constraints named, with nullability and
  defaults? Is there a migration plan, including existing rows and a way back?
- **Authorization:** for each endpoint, who may call it and whose data it can read or change
  (owner, superuser, anyone signed in)?
- **Validation and limits:** input rules, pagination and size limits stated where lists or
  uploads appear.
- **Missing section:** a design that changes the API or the data model without an
  "API changes" or "Data model and migration" section is itself a finding.

Severity: blocker = an endpoint without an authorization rule, or a breaking change or
destructive migration not called out; major = a missing schema, status code, migration or
rollback step; nit = wording.
