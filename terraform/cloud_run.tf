resource "google_cloudfunctions2_function" "function" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name     = "${each.key}-api-function"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = var.python_version
    entry_point = "print_${each.key}"
    source {
      repo_source {
        project_id  = var.project_id
        repo_name   = "qtymothy-hubitat_terraform"
        branch_name = "main"
        dir         = "${each.key}/"
      }
    }
  }

  service_config {
    service_account_email          = google_service_account.cloudbuild_sa.email
    available_memory               = var.python_memory
    ingress_settings               = "ALLOW_ALL"
    timeout_seconds                = var.python_timeout
    all_traffic_on_latest_revision = true
  }

  event_trigger {
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    trigger_region = var.region
    pubsub_topic   = google_pubsub_topic.hub_topic[each.key].id
  }
}