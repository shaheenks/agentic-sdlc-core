resource "google_service_account" "component" {
  for_each     = local.components
  account_id   = each.value
  display_name = "${each.key} (${var.env})"
  description  = "Service identity of ${each.key}; holds only the roles that component needs."
  depends_on   = [google_project_service.apis]
}

# Every component writes structured logs, traces and metrics (NFR-OBS-001, NFR-AUD-002).
locals {
  telemetry_roles = ["roles/logging.logWriter", "roles/cloudtrace.agent", "roles/monitoring.metricWriter"]
  telemetry = {
    for pair in setproduct(keys(local.components), local.telemetry_roles) :
    "${pair[0]}/${pair[1]}" => { component = pair[0], role = pair[1] }
  }
}

resource "google_project_iam_member" "telemetry" {
  for_each = local.telemetry
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.component[each.value.component].email}"
}
