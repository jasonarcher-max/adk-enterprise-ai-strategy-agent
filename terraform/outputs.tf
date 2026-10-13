output "service_url" {
  description = "Deployed Cloud Run URL for the ADK Enterprise AI Strategy Agent."
  value       = google_cloud_run_v2_service.adk_strategy_agent_service.uri
}

output "agent_service_account_email" {
  description = "Least-privilege IAM Service Account email for the ADK Agent."
  value       = google_service_account.adk_strategy_agent_sa.email
}
