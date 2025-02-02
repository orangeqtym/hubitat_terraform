resource "google_cloud_scheduler_job" "trigger_weather_api" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name        = "trigger-${each.value}-api"
  description = "Triggers the ${each.value} API Function"
  schedule    = "0 * * * *"
  time_zone   = "America/New_York"
  project     = var.project_id
  region      = var.region

  pubsub_target {
    topic_name = google_pubsub_topic.hub_topic[each.key].id
    data       = base64encode("{}")
  }
}