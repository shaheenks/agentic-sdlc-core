# samples

Synthetic content for local development and tests. **No real data.**

`sources/` holds the sample corpus that `config/sources/*.yaml` points at (Stage 5):

| Folder | Source id | Classification | Access |
|---|---|---|---|
| `payments-api/` | `payments-code` | internal | payments team, admin |
| `platform-infra/` | `platform-infra` | internal | platform team, admin |
| `eng-standards/` | `eng-standards` | public | all engineers (`eng-all`) |
| `payments-incidents/` | `payments-incidents` | confidential | payments team (leads and above by classification), admin |

The files are written with cross-references (services, workers, owners, alerts, runbooks,
incidents), so some questions need facts from several files; the retrieval eval
(`tests/evals/`) relies on them. Keep new files consistent with the existing names.
