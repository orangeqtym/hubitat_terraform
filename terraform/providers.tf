terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">=5.45.1"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">=6.18.1"
    }
    github = {
      source  = "integrations/github"
      version = ">=6.2.2"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

provider "github" {
  token = var.github_token
}