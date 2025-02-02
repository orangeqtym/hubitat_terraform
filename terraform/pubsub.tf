resource "google_pubsub_topic" "hub_topic" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name    = "${each.key}-data-topic"
  project = var.project_id
}