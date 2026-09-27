# Ownership and on-call

| Component | Squad | Pager rotation |
|---|---|---|
| payments-api | payments-core | payments-oncall |
| refund-worker | payments-core | payments-oncall |
| processor-gateway | payments-integrations | payments-integrations-oncall |
| ledger-service | ledger | ledger-oncall |
| reconciliation-job | ledger | ledger-oncall |

The payments team lead (payments-leads group) approves changes to refund limits and ledger
account mappings.
