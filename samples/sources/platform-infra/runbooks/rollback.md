# Rolling back a deployment

When the canary breaches the SLO the pipeline rolls back automatically. To roll back by hand:

1. `deployctl rollback --service <name> --to previous` restores the last healthy revision.
2. Confirm traffic is 100% on the previous revision in the dashboard.
3. Open an incident if customer impact lasted more than five minutes.

Terraform changes are rolled back by reverting the commit and re-applying the plan; never edit
state by hand.
