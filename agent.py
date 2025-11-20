import json
import operator
from typing import Annotated, List, TypedDict, Union, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from utils.deployment_tools import (
    get_service_metadata,
    generate_deployment_plan,
    trigger_ci_pipeline,
    deploy_to_k8s,
    get_deployment_metrics,
    promote_rollout,
    rollback_deployment,
    trigger_static_site_deployment
)
from utils.prompts import DEPLOYMENT_PLANNER_PROMPT, METRIC_ANALYZER_PROMPT

from dotenv import load_dotenv
load_dotenv()

# --- State Definition ---
class DeploymentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    service_id: str
    plan: Dict[str, Any]
    current_step_index: int
    deployment_status: str # "planning", "executing", "verifying", "completed", "failed", "rolled_back"
    rollout_id: str # ID of the active rollout (for promote/rollback)
    # Static site params
    github_token: str
    repo_url: str
    app_name: str
    branch: str
    output_dir: str
    build_command: str

# --- Models & Tools ---
llm = ChatOpenAI(model="gpt-4.1", temperature=0)

# Tools for the planner
planner_tools = [get_service_metadata, generate_deployment_plan]
planner_llm = llm.bind_tools(planner_tools)

# Tools for the executor (CI/CD & Deploy)
executor_tools = [trigger_ci_pipeline, deploy_to_k8s, trigger_static_site_deployment]
executor_llm = llm.bind_tools(executor_tools, tool_choice="required")

# Tools for the verifier (Metrics & Rollback)
verifier_tools = [get_deployment_metrics, promote_rollout, rollback_deployment]
verifier_llm = llm.bind_tools(verifier_tools)


# --- Nodes ---

def planner_node(state: DeploymentState):
    """
    Generates the deployment plan.
    """
    print("--- PLANNER NODE ---")
    messages = state["messages"]
    
    # If plan is already set, move to execution
    if state.get("plan"):
        return {"deployment_status": "executing"}

    # Invoke LLM to get service info or generate plan
    response = planner_llm.invoke(messages)
    return {"messages": [response]}


def plan_parser_node(state: DeploymentState):
    """
    Parses the tool output to extract the plan JSON.
    """
    print("--- PLAN_PARSER NODE ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, ToolMessage):
        try:
            # Check if this tool message is from generate_deployment_plan
            # In a real app, we'd check tool_call_id or name more robustly
            content = last_message.content
            plan_data = json.loads(content)
            
            if "steps" in plan_data:
                print(f"📋 Plan generated with {len(plan_data['steps'])} steps.")
                return {
                    "plan": plan_data, 
                    "current_step_index": 0,
                    "deployment_status": "executing",
                    "service_id": plan_data.get("service_id", state.get("service_id"))
                }
        except json.JSONDecodeError:
            pass
            
    return {}


def executor_node(state: DeploymentState):
    """
    Executes the current step in the plan.
    """
    print(f"--- EXECUTOR NODE (Step {state.get('current_step_index')}) ---")
    plan = state.get("plan")
    idx = state.get("current_step_index", 0)
    
    if not plan or idx >= len(plan["steps"]):
        return {"deployment_status": "completed"}
    
    step = plan["steps"][idx]
    step_name = step["name"]
    service_id = state["service_id"]
    
    print(f"🚀 Executing Step: {step_name}")
    
    # Logic to map step names to tool calls
    # In a more advanced agent, the LLM would decide this mapping.
    # Here we map explicitly for deterministic execution in the Hackathon.
    
    tool_call_id = "call_" + step_name
    
    if step_name in ["run_unit_tests", "run_lint", "security_scan", "build_image"]:
        # Manually construct tool call for trigger_ci_pipeline
        tool_call = {
            "name": "trigger_ci_pipeline",
            "args": {"service_id": service_id, "step_name": step_name},
            "id": tool_call_id
        }
    elif step_name == "deploy_canary":
        tool_call = {
            "name": "deploy_to_k8s",
            "args": {"service_id": service_id, "version": "v1.2.1", "strategy": "canary"},
            "id": tool_call_id
        }
    elif step_name == "deploy_static_site":
        # Use params from state or defaults
        tool_call = {
            "name": "trigger_static_site_deployment",
            "args": {
                "repo_url": state.get("repo_url", ""),
                "app_name": state.get("app_name", service_id),
                "branch": state.get("branch", "main"),
                "output_dir": state.get("output_dir", "dist"),
                "build_command": state.get("build_command", "npm run build"),
                "github_token": state.get("github_token", "")
            },
            "id": tool_call_id
        }
    elif step_name == "verify_metrics":
        return {"deployment_status": "verifying"}
    elif step_name == "promote_full":
        return {"deployment_status": "completed"}
        
    if tool_call:
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="", tool_calls=[tool_call])]}
        
    return {"current_step_index": idx + 1}


def execution_result_node(state: DeploymentState):
    """
    Processes the result of the execution tool call.
    """
    print("--- EXECUTION_RESULT NODE ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, ToolMessage):
        # Check if it was a deployment to capture rollout_id
        content = last_message.content
        try:
            data = json.loads(content)
            updates = {"current_step_index": state["current_step_index"] + 1}
            
            if "rollout_id" in data:
                updates["rollout_id"] = data["rollout_id"]
                
            return updates
        except:
            return {"current_step_index": state["current_step_index"] + 1}
            
    return {}


def verifier_node(state: DeploymentState):
    """
    Analyzes metrics and decides to promote or rollback.
    """
    print("--- VERIFIER NODE ---")
    service_id = state["service_id"]
    rollout_id = state.get("rollout_id", "unknown")
    
    prompt = METRIC_ANALYZER_PROMPT.format(service_id=service_id, rollout_id=rollout_id)
    
    # We pass the conversation history + specific prompt
    response = verifier_llm.invoke([HumanMessage(content=prompt)])
    return {"messages": [response]}


def verifier_result_node(state: DeploymentState):
    """
    Processes the result of verification.
    """
    print("--- VERIFIER_RESULT NODE ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, ToolMessage):
        content = last_message.content
        if "Promoting" in content or "Promotion completed" in content:
             # Move to next step (which might be promote_full or finish)
             return {"deployment_status": "executing", "current_step_index": state["current_step_index"] + 1}
        elif "Rolling back" in content or "Rollback completed" in content:
             return {"deployment_status": "rolled_back"}
             
    return {}


# --- Graph Construction ---

workflow = StateGraph(DeploymentState)

# Add Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("plan_parser", plan_parser_node)
workflow.add_node("executor", executor_node)
workflow.add_node("execution_result", execution_result_node)
workflow.add_node("verifier", verifier_node)
workflow.add_node("verifier_result", verifier_result_node)

# Add Tool Nodes
workflow.add_node("planner_tools", ToolNode(planner_tools))
workflow.add_node("executor_tools", ToolNode(executor_tools))
workflow.add_node("verifier_tools", ToolNode(verifier_tools))

# Set Entry Point
workflow.set_entry_point("planner")

# Conditional Edges

def should_continue_planning(state):
    messages = state["messages"]
    last_message = messages[-1]
    
    if state.get("plan"):
        return "executor"
        
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "planner_tools"
        
    return "planner"

workflow.add_conditional_edges(
    "planner",
    should_continue_planning
)

workflow.add_edge("planner_tools", "plan_parser")
workflow.add_edge("plan_parser", "planner") # Loop back to check if plan is ready

def should_continue_execution(state):
    status = state.get("deployment_status")
    if status == "verifying":
        return "verifier"
    if status == "completed":
        return END
    if status == "rolled_back":
        return END
        
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "executor_tools"
        
    return "executor" # Continue loop

workflow.add_conditional_edges(
    "executor",
    should_continue_execution
)

workflow.add_edge("executor_tools", "execution_result")
workflow.add_edge("execution_result", "executor")

def should_continue_verification(state):
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "verifier_tools"
    return "executor" # Back to executor to finish steps

workflow.add_conditional_edges(
    "verifier",
    should_continue_verification
)

workflow.add_edge("verifier_tools", "verifier_result")
workflow.add_edge("verifier_result", "executor") # Back to executor loop


from langgraph.checkpoint.memory import InMemorySaver

def build_graph():
    checkpointer = InMemorySaver()
    return workflow.compile(checkpointer=checkpointer)