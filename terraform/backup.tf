terraform {
  backend "gcs" {
    bucket = "hubitat-terraform-state"
    prefix = "terraform/state"
  }
}
