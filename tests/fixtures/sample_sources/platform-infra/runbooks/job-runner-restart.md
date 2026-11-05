# Restarting job-runner safely

1. `jobctl drain --all` stops workers from taking new work and waits for in-flight jobs.
2. Check that every worker using an in-memory cache has `persistent_cache: true`; otherwise
   its cache (for example idempotency keys) is lost.
3. Restart with `jobctl restart`, then `jobctl resume --all`.
4. Watch the job error-rate dashboard for 15 minutes.
