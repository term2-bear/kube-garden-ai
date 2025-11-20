from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from mangum import Mangum
from langchain.messages import HumanMessage
from agent import build_graph

app = FastAPI()

# Initialize the agent graph
agent = build_graph()

class DeployRequest(BaseModel):
    service_id: str
    thread_id: str
    strategy: str = "canary"
    message: str = "Deploying new version"
    # Static site params
    github_token: Optional[str] = None
    repo_url: Optional[str] = None
    app_name: Optional[str] = None
    branch: Optional[str] = "main"
    output_dir: Optional[str] = "dist"
    build_command: Optional[str] = "npm run build"

class DeployResponse(BaseModel):
    status: str
    plan: Optional[Dict[str, Any]] = None
    current_step_index: Optional[int] = None
    logs: Optional[List[str]] = None

@app.get("/")
def read_root():
    return {"message": "Kube-Garden Deployment Agent is running"}

@app.post("/deploy", response_model=DeployResponse)
async def deploy(request: DeployRequest):
    config = {"configurable": {"thread_id": request.thread_id}, "recursion_limit": 100}
    
    try:
        # Initial message to start the planning
        user_msg = f"Deploy service '{request.service_id}' using '{request.strategy}' strategy. Note: {request.message}"
        
        # Run the agent
        inputs = {
            "messages": [HumanMessage(content=user_msg)], 
            "service_id": request.service_id,
            "github_token": request.github_token or "",
            "repo_url": request.repo_url or "",
            "app_name": request.app_name or request.service_id,
            "branch": request.branch or "main",
            "output_dir": request.output_dir or "dist",
            "build_command": request.build_command or "npm run build"
        }
        
        result = await agent.ainvoke(inputs, config=config)
        
        return DeployResponse(
            status=result.get("deployment_status", "unknown"),
            plan=result.get("plan"),
            current_step_index=result.get("current_step_index"),
            logs=[m.content for m in result["messages"] if hasattr(m, "content")]
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deploy/{thread_id}/status", response_model=DeployResponse)
async def get_status(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state = await agent.aget_state(config)
        if not state:
            raise HTTPException(status_code=404, detail="Deployment not found")
            
        result = state.values
        
        return DeployResponse(
            status=result.get("deployment_status", "unknown"),
            plan=result.get("plan"),
            current_step_index=result.get("current_step_index"),
            logs=[m.content for m in result["messages"] if hasattr(m, "content")]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mangum handler for AWS Lambda
handler = Mangum(app)
