resource "google_storage_bucket" "project_bucket" {
  name                        = "${var.project_id}-bucket"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "backup_bucket" {
  name                        = "hubitat-terraform-state"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true

  lifecycle {
    prevent_destroy = true
  }
}
