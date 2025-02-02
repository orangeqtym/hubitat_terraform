# Hubitat Terraform Project

This project uses Terraform to deploy a Cloud Run service triggered by a Pub/Sub topic on Google Cloud Platform (GCP).

## Overview

The infrastructure includes:

* **Pub/Sub Topic:** A Pub/Sub topic (`weather-topic`) to which messages can be published.
* **Cloud Run Service:** A Cloud Run service (`my-cloudrun-service`) that processes messages from the Pub/Sub topic.
* **IAM Binding:**  Grants the Cloud Run service the necessary permissions to subscribe to the Pub/Sub topic.

The current setup allows for manual triggering of the Cloud Run service by publishing messages to the Pub/Sub topic.  Future enhancements will include scheduled, time-based triggers via Cloud Scheduler.

## Prerequisites

* **Google Cloud Account:** You need an active GCP project with billing enabled.
* **Terraform Installed:**  Ensure Terraform is installed and available in your system's PATH.
* **gcloud CLI:**  The `gcloud` command-line tool is required for interacting with GCP (e.g., publishing messages to Pub/Sub).
* **Docker:** Docker is required to build the container image if building image locally.

## Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/qtymothy/hubitat_terraform.git
   ```

2. **Navigate to Terraform Directory:**
   ```bash
   cd hubitat_terraform/terraform
   ```

3. **Initialize Terraform:**
   ```bash
   terraform init
   ```

4. **Set Variables:** Create a `terraform.tfvars` file in the `terraform` directory or set the following environment variables:

   ```bash
   project_id = "your-project-id"  # Replace with your GCP project ID
   region      = "your-region"      # Replace with your desired GCP region (e.g., "northamerica-northeast1")
   ```
   You may also set variables as command line parameters, but this is less secure as the variables will be visible in command history:
   ```bash
   terraform apply -var="project_id=your-project-id" -var="region=your-region"
   ```
5. **Build and Push Docker Image:**
Build your docker image locally and push to Google Artifact Registry:
   ```bash
    gcloud builds submit --tag northamerica-northeast1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/hello .
   ```
6. **Deploy with Terraform:**
   ```bash
   terraform apply
   ```

## Manual Testing

After deployment, you can manually trigger the Cloud Run service by publishing messages to the Pub/Sub topic:

## Future Enhancements

* **Scheduled Triggers:** Implement Cloud Scheduler to trigger the Cloud Run service on a regular schedule.


## Contributing

Contributions are welcome!  Please create a pull request with your proposed changes.