# Observability

Metrics are scraped by Prometheus and alerts are routed by Alertmanager to each team's pager
rotation. Every tier-1 service has an SLO:

- error rate below 1% over 5 minutes
- p99 latency below 800 ms

The deploy pipeline's canary check uses these SLOs. Dashboards live in Grafana under the service
name.
