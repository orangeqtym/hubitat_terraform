resource "google_cloudbuild_trigger" "trigger" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name = "${each.key}-cloud-functions-trigger"
  github {
    owner = "qtymothy"
    name  = "hubitat_terraform"
    push {
      branch = "main"
    }
  }

  build {
    step {
      name = "gcr.io/cloud-builders/gcloud"
      args = [
        "builds", "submit",
        "--substitutions",
        "FUNCTION=${each.key},",
        "ENTRY_POINT=${google_cloudfunctions2_function.function[each.key].name},",
        "TRIGGER_TOPIC=${google_pubsub_topic.hub_topic[each.key].name},",
        "SERVICE_ACCOUNT_EMAIL=${google_service_account.project_sa.email},",
        "MEMORY=${var.python_memory},",
        "TIMEOUT=${var.python_timeout},REGION=${var.region},PROJECT_ID=${var.project_id}",
        "."
      ]
    }
  }
}
