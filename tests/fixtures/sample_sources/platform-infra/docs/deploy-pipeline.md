# Deploy pipeline

1. A merge to `main` builds the container image and pushes it to the registry.
2. The pipeline deploys to **dev**, runs smoke tests, then waits for approval.
3. **Staging** runs the full integration suite; **prod** uses a canary: 10% of traffic for 15
   minutes, then 100% if error rate and latency stay inside the SLO.
