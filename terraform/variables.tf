variable "project_id" {
  description = "Google Cloud Project ID hosting Vertex AI and the ADK Agent."
  type        = string
}

variable "region" {
  description = "Google Cloud region for Vertex AI Agent Engine and Cloud Run."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name of the Cloud Run / ADK Agent service."
  type        = string
  default     = "adk-enterprise-ai-strategy-agent"
}

variable "container_image" {
  description = "Artifact Registry container image URI for the ADK agent."
  type        = string
  default     = "us-central1-docker.pkg.dev/my-project/adk-repo/strategy-agent:latest"
}
