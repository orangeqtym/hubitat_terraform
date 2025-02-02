# --- Service Account ---
resource "google_service_account" "project_sa" {
  account_id   = "project-service-account"
  display_name = "Service Account for Project"
  project      = var.project_id
}

# keep
resource "google_service_account" "cloudbuild_sa" {
  account_id   = "cloudbuild"
  display_name = "Cloud Build Service Account"
}

# --- IAM Bindings ---
# Cloud Run
resource "google_project_iam_member" "invoker" {
  for_each = {for idx, val in var.instance_names : val => idx}
  project = google_pubsub_topic.hub_topic[each.key].project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Storage
resource "google_project_iam_member" "storage_object_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Artifact Registry
resource "google_project_iam_member" "artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Eventarc
resource "google_project_iam_member" "eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Secret Manager
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Pub/Sub
resource "google_pubsub_topic_iam_member" "pubsub_subscriber" {
  for_each = {for idx, val in var.instance_names : val => idx}
  project = google_pubsub_topic.hub_topic[each.key].project
  topic   = google_pubsub_topic.hub_topic[each.key].name
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

resource "google_pubsub_topic_iam_member" "pubsub_publisher" {
  for_each = {for idx, val in var.instance_names : val => idx}
  project = google_pubsub_topic.hub_topic[each.key].project
  topic   = google_pubsub_topic.hub_topic[each.key].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Cloud Functions
resource "google_project_iam_member" "functions_developer" {
  project = var.project_id
  role    = "roles/cloudfunctions.developer"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Eventarc Trigger
resource "google_project_iam_member" "eventarc_invoker" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.project_sa.email}"
}

# Grant Service Account Token Creator role to the service account on the Cloud Build service account
resource "google_service_account_iam_member" "sa_token_creator" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.GCP_CLOUD_PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.project_sa.email}"
  depends_on = [google_project_iam_member.cloud_build_user]
}

resource "google_project_iam_member" "cloud_build_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${var.GCP_CLOUD_PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
}

# keep
resource "google_project_iam_member" "cloudbuild_sa_roles" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
  role    = "roles/cloudbuild.builds.editor"
  depends_on = [google_project_iam_member.cloud_build_user]
}

# keep
resource "google_project_iam_member" "cloudbuild_sa_token_creator" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
  role    = "roles/iam.serviceAccountTokenCreator"
  depends_on = [google_project_iam_member.cloud_build_user]
}

#keep
resource "google_project_iam_member" "cloudbuild_sa_function_admin" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
  role    = "roles/cloudfunctions.admin"
}
