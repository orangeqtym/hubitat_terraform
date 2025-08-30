terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    github = {
      source  = "integrations/github"
      version = ">=6.2.2"
    }
  }
}

provider "docker" {
  host = "npipe:////./pipe/dockerDesktopLinuxEngine"
}

provider "github" {
  token = var.github_token
}