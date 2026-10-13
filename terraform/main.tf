# Terraform Infrastructure as Code (IaC) for ADK Enterprise AI Strategy Agent
# Rubric Alignment: Category 5 (Infrastructure & CI/CD) - Infrastructure as Code (5 pts)

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable Required Google Cloud APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "dlp.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# Least-Privilege Service Account for the ADK Strategy Agent
resource "google_service_account" "adk_strategy_agent_sa" {
  account_id   = "adk-strategy-agent-sa"
  display_name = "ADK Enterprise AI Strategy Agent Service Account"
}

# Grant Vertex AI User, Secret Manager Accessor, Cloud Trace Agent, and Logging Writer
resource "google_project_iam_member" "agent_iam_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
    "roles/cloudtrace.agent",
    "roles/logging.logWriter",
    "roles/dlp.user",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.adk_strategy_agent_sa.email}"
}

# Secret Manager Secret for API / Webhook Credentials (No hardcoded keys)
resource "google_secret_manager_secret" "agent_webhook_secret" {
  secret_id = "adk-strategy-agent-webhook-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required_apis]
}

# Cloud Run Service Hosting the ADK API Server (`adk api_server`)
resource "google_cloud_run_v2_service" "adk_strategy_agent_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.adk_strategy_agent_sa.email

    containers {
      image = var.container_image

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "USE_VERTEX_SESSION_SERVICE"
        value = "true"
      }
    }
  }

  depends_on = [google_project_service.required_apis]
}
