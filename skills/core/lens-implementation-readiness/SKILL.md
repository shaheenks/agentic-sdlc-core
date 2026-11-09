---
name: lens-implementation-readiness
description: Goldfish review lens. Implementing engineer - is every step actionable without design decisions left open?
---

# Lens: implementation readiness

Read it as the engineer who must build it tomorrow. Ask: "Do I know exactly what to change,
where, and how to check it?"

- **Open decisions:** choices left to the implementer (data store, API shape, error handling,
  naming, limits). Each should be decided in the document.
- **Vague steps:** "update the service" instead of what changes in which component.
- **Interfaces and data:** inputs, outputs, schemas, migrations, compatibility with existing
  clients and data.
- **Rollout:** order of steps, feature flags, rollback, who runs what.
- **Done:** tests and exit criteria that prove each step works.

For user stories: each story has a user, a goal, a reason, and testable acceptance criteria.

Severity: blocker = cannot start without a decision; major = a step needs guessing; nit = a
detail to add.
