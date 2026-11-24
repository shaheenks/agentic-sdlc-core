---
type: Functional Requirement
title: "Team context"
description: "A user who belongs to several teams chooses which team a run is for."
tags: [requirement, teams]
status: draft
x-area: TEAM
x-priority: must
x-implementation: planned
---

# Statement

The system shall let a user choose the team a run is for, or none for a personal run.

# Acceptance criteria

- A run records its team context, or none.
- Only teams the user belongs to can be chosen.
- The team context selects the workflows, skills and data declared for that team.
- A team run may use only what both the starter may use and the team (or everyone) is granted; anything denied to the starter personally stays denied in the run.
