---
type: Functional Requirement
title: Images and diagrams
description: Images and diagrams in sources are described and read with a multimodal model, for sources that opt in.
area: Knowledge
tags:
- requirement
- functional
- knowledge
status: draft
priority: could
implementation: planned
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: change
  resource: ../../changes/CH-0008.md
  title: CH-0008 Workflow platform design baseline
---

# Statement

The system shall make the content of images and diagrams in opted-in sources searchable, citing where each image is.

# Acceptance criteria

- Only sources that opt in send images to the model, and the output is cached by content hash.
- Image chunks cite the document that contains the image and where the image is in it.
- Images in sources that have not opted in are skipped and counted in the ingest report.
