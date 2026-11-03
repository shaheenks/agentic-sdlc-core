# Code review guidelines

- Every change needs one approving review; changes to shared libraries need two.
- Reviewers check correctness, tests, security (authorization, secrets, input validation) and
  operability (logging, metrics, rollback).
- Keep pull requests under 400 changed lines where possible; split refactors from behaviour.
- Authors resolve every comment before merging; "nit" comments are optional.
