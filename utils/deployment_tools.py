import os
import json
import time
import random
from typing import List, Dict, Any, Optional
from langchain.tools import tool

# Mock Data for Hackathon
MOCK_SERVICES = {
    "demo-api": {
        "id": "demo-api",
        "repo_url": "https://github.com/user/demo-api",
        "namespace": "default",
        "current_version": "v1.0.0",
        "type": "backend"
    },
    "demo-frontend": {
        "id": "demo-frontend",
        "repo_url": "https://github.com/user/demo-frontend",
        "namespace": "default",
        "current_version": "v1.2.0",
        "type": "frontend"
    }
}

@tool
def get_service_metadata(service_id: str) -> str:
    """
    Retrieves metadata for a given service ID.
    Useful for understanding the service context before planning deployment.
    """
    service = MOCK_SERVICES.get(service_id)
    if not service:
        return json.dumps({"error": "Service not found"})
    return json.dumps(service)

@tool
def generate_deployment_plan(service_id: str, strategy: str = "canary") -> str:
    """
    Generates a deployment plan based on the service and strategy.
    Returns a JSON string representing the plan steps.
    """
    # In a real scenario, this might query current state and policies.
    # For now, we generate a standard plan.
    
    service = MOCK_SERVICES.get(service_id)
    service_type = service.get("type", "backend") if service else "backend"
    
    steps = [
        {"name": "run_unit_tests", "description": "Run unit tests via CI", "status": "pending"}
    ]
    
    if service_type == "frontend":
        steps.append({"name": "deploy_static_site", "description": "Deploy static site to AWS Lambda", "status": "pending"})
    else:
        steps.append({"name": "deploy_canary", "description": f"Deploy {strategy} version (10% traffic)", "status": "pending"})
        
    plan = {
        "service_id": service_id,
        "strategy": strategy,
        "steps": steps
    }
    return json.dumps(plan)

@tool
def trigger_ci_pipeline(service_id: str, step_name: str) -> str:
    """
    Triggers a CI/CD pipeline step (e.g., CodeBuild).
    Returns the build ID and status.
    """
    # Mocking AWS CodeBuild trigger
    print(f"🚀 Triggering CI Step: {step_name} for {service_id}")
    time.sleep(1) # Simulate API call
    
    # Simulate random failure for demonstration (very low probability)
    if random.random() < 0.05:
        return json.dumps({"status": "failed", "error": "Build failed due to test errors"})
        
    return json.dumps({"status": "success", "build_id": f"build-{random.randint(1000, 9999)}"})

@tool
def deploy_to_k8s(service_id: str, version: str, strategy: str) -> str:
    """
    Applies Kubernetes manifests to deploy the service.
    Supports 'canary', 'blue-green', 'rolling'.
    """
    # Mocking `kubectl apply` or Argo Rollouts
    print(f"☸️  Deploying {service_id} ({version}) with {strategy} strategy")
    time.sleep(1)
    
    return json.dumps({
        "status": "success", 
        "message": f"Deployed {service_id}:{version} successfully",
        "rollout_id": f"ro-{random.randint(1000,9999)}"
    })

@tool
def get_deployment_metrics(service_id: str, window_minutes: int = 5) -> str:
    """
    Fetches performance metrics (Latency, Error Rate, CPU) from Observability system.
    Used for verification.
    """
    # Mocking CloudWatch/Prometheus
    print(f"📊 Fetching metrics for {service_id} (last {window_minutes}m)")
    
    # Simulate healthy metrics usually, but sometimes degraded
    is_healthy = random.random() > 0.2
    
    if is_healthy:
        metrics = {
            "avg_latency_ms": random.randint(20, 100),
            "error_rate_percent": round(random.uniform(0, 0.5), 2),
            "cpu_usage_percent": random.randint(30, 60)
        }
    else:
        metrics = {
            "avg_latency_ms": random.randint(200, 500), # High latency
            "error_rate_percent": round(random.uniform(2.0, 5.0), 2), # High error rate
            "cpu_usage_percent": random.randint(80, 95)
        }
        
    return json.dumps(metrics)

@tool
def promote_rollout(service_id: str, rollout_id: str) -> str:
    """
    Promotes a canary rollout to stable (100% traffic).
    """
    print(f"✅ Promoting rollout {rollout_id} for {service_id}")
    return json.dumps({"status": "success", "message": "Promotion completed"})

@tool
def rollback_deployment(service_id: str, rollout_id: str, reason: str) -> str:
    """
    Rolls back the deployment to the previous stable version.
    """
    print(f"↩️  Rolling back {service_id} (Rollout: {rollout_id}). Reason: {reason}")
    return json.dumps({"status": "success", "message": "Rollback completed"})

@tool
def trigger_static_site_deployment(
    repo_url: str, 
    app_name: str, 
    branch: str = "main", 
    output_dir: str = "dist", 
    build_command: str = "npm run build",
    github_token: str = ""
) -> str:
    """
    Triggers the Lambda-based static site deployment.
    """
    import requests
    
    api_url = os.environ.get("STATIC_SITE_DEPLOY_API_URL")
    
    # Mock for local testing if URL is MOCK or not set
    if not api_url or api_url == "MOCK":
        print(f"⚠️  Using MOCK Static Site Deployment for {app_name}")
        time.sleep(2)
        return json.dumps({
            "status": "success", 
            "response": {
                "message": "Mock deployment successful", 
                "url": f"https://{app_name}.example.com"
            }
        })
        
    payload = {
        "github_token": github_token,
        "repo_url": repo_url,
        "app_name": app_name,
        "branch": branch,
        "output_dir": output_dir,
        "build_command": build_command
    }
    
    print(f"🚀 Triggering Static Site Deployment for {app_name}...")
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        return json.dumps({"status": "success", "response": response.json()})
    except Exception as e:
        return json.dumps({"status": "failed", "error": str(e)})
