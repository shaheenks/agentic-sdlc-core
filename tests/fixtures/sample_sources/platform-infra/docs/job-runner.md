# job-runner

Shared platform service that runs background workers and scheduled jobs for product teams
(for example the refund-worker and the reconciliation-job). Owned by the platform team.

- Workers are restarted on every job-runner deploy and when a node is drained.
- Worker-local caches are in memory and are **lost on restart** unless the job sets
  `persistent_cache: true`, which stores the cache in the shared `jobstate-redis` instance.
- Scheduled jobs are defined in `jobs.yaml`; the schedule uses the cluster time zone (UTC).
