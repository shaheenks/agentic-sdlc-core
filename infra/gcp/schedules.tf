# Scheduled jobs (version-02 N1 ingest, N3 reconcile). Off unless ingest_schedule /
# reconcile_schedule are set: then Cloud Scheduler starts the Cloud Run job through the Run Admin
# API, as the scheduler service account, which may start these jobs and nothing else.

locals {
  schedules = {
    for name, s in {
      ingest    = { cron = var.ingest_schedule, job = google_cloud_run_v2_job.ingest.name }
      reconcile = { cron = var.reconcile_schedule, job = google_cloud_run_v2_job.reconcile.name }
    } : name => s if s.cron != ""
  }
  any_schedule = var.ingest_schedule != "" || var.reconcile_schedule != ""
}

resource "google_project_service" "scheduler" {
  count              = local.any_schedule ? 1 : 0
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_run_v2_job_iam_member" "scheduler" {
  for_each = local.schedules
  location = var.region
  name     = each.value.job
  role     = "roles/run.invoker" # includes run.jobs.run
  member   = google_service_account.scheduler[0].member
}

resource "google_cloud_scheduler_job" "run" {
  for_each         = local.schedules
  name             = "sdlc-${each.key}-${var.env}"
  region           = var.region
  schedule         = each.value.cron
  time_zone        = var.schedule_time_zone
  attempt_deadline = "60s" # starting the job; the job itself has its own timeout

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${each.value.job}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_project_service.scheduler, google_cloud_run_v2_job_iam_member.scheduler]
}
