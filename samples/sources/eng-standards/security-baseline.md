# Security baseline

- Authenticate every request; authorize deny-by-default.
- Secrets come from the secret manager, never from code or config files.
- Log security events without sensitive data; keep audit logs for one year.
