---
name: infra-change-review
description: Review an infrastructure or CI change for blast radius, rollback and safety (platform team).
---

# Infrastructure change review (platform team)

Use this skill for changes to infrastructure-as-code, CI pipelines, networking or shared platform services.

## Checklist
1. **Blast radius:** which environments and services are affected; is the change staged
   (dev -> staging -> prod)?
2. **Plan output:** a reviewed `plan`/diff exists; no unexpected destroys or replacements.
3. **Rollback:** a tested way back and how long it takes.
4. **Security:** least-privilege IAM, no public exposure by default, secrets from the secret manager.
5. **Observability:** alerts or dashboards cover the change; what signals success or failure.
6. **Timing:** change window and who is on call.

Report a verdict and the blocking items first.
