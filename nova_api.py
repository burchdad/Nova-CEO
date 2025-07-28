from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
import aiohttp
import asyncio
import os
import logging
from datetime import datetime
from typing import Optional

# ===========================
# 🔹 App + Logging Setup
# ===========================
app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ===========================
# 🔹 Secure Env Loader
# ===========================
def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

# ===========================
# 🔹 Airtable Config
# ===========================
AIRTABLE_API_KEY = get_env_var("AIRTABLE_API_KEY")
BASE_ID = get_env_var("BASE_ID")
TABLE_ID_COMMANDS = get_env_var("TABLE_ID_COMMANDS")
TABLE_ID_GPT_TREE = get_env_var("TABLE_ID_GPT_TREE")
TABLE_ID_TASKS = get_env_var("TABLE_ID_TASKS")
TABLE_ID_KPIS = get_env_var("TABLE_ID_KPIS")
TABLE_ID_AI_AGENTS = get_env_var("TABLE_ID_AI_AGENTS")
TABLE_ID_DEPARTMENTS = get_env_var("TABLE_ID_DEPARTMENTS")

def airtable_headers():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

# ===========================
# 🔹 Nova Command Input Model
# ===========================
class CommandInput(BaseModel):
    command: str = Field(..., min_length=5, max_length=500)

# ===========================
# ✅ POST /nova/command
# ===========================
@app.post("/nova/command")
async def process_command(input: CommandInput):
    try:
        command_text = input.command
        issued_date = datetime.utcnow().strftime("%Y-%m-%d")

        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_COMMANDS}"
        payload = {
            "fields": {
                "Command Name": command_text[:255],
                "Command Input": command_text,
                "Issued By": "Nova Flutter App",
                "Issued Date": issued_date,
                "Status": "Queued",
                "Priority": "Medium",
                "Follow-up Needed?": True,
                "Validation Status": "Pending",
                "Comments": "Queued from Nova mobile demo"
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=airtable_headers(), json=payload) as resp:
                response_data = await resp.text()
                if resp.status in (200, 201):
                    return {"status": "success", "message": f"✅ Logged in Airtable: {command_text}"}
                else:
                    logging.error(f"❌ Airtable Error: {resp.status} - {response_data}")
                    return {"status": "error", "message": "Failed to log to Airtable", "details": response_data}

    except Exception as e:
        logging.exception("Unhandled exception in /nova/command")
        return {"status": "error", "message": "Internal server error", "details": str(e)}

# ===========================
# ✅ GPT Tree Fetch + Builder
# ===========================
@app.get("/nova/gpt_tree")
async def get_gpt_tree():
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_GPT_TREE}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=airtable_headers()) as resp:
                records = (await resp.json()).get("records", [])

        id_to_name = {r["id"]: r["fields"].get("GPT Name") for r in records if r["fields"].get("GPT Name")}

        def build_tree(name=None):
            tree = []
            for r in records:
                f = r["fields"]
                gpt_name = f.get("GPT Name")
                if (not name and gpt_name == "Nova CEO GPT") or (name and name in [id_to_name.get(pid) for pid in f.get("Parent GPT", [])]):
                    children = build_tree(gpt_name)
                    tree.append({
                        "name": gpt_name,
                        "id": f.get("GPT ID", r["id"]),
                        "role": f.get("Role / Department"),
                        "status": f.get("Status"),
                        "linked_department": f.get("Linked Department"),
                        "dashboard_url": f.get("Dashboards URL"),
                        "children": children
                    })
            return tree

        return {"status": "success", "data": {"gpt_tree": build_tree()}}

    except Exception as e:
        logging.exception("GPT Tree build error")
        return {"status": "error", "message": "Failed to fetch GPT Tree", "details": str(e)}

# ===========================
# ✅ GPT Health Endpoint
# ===========================
@app.get("/nova/gpt_health")
async def get_gpt_health(debug: bool = Query(False)):
    try:
        async with aiohttp.ClientSession() as session:
            urls = {
                "agents": f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_AI_AGENTS}",
                "tasks": f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_TASKS}",
                "kpis": f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_KPIS}",
                "departments": f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_DEPARTMENTS}"
            }
            headers = airtable_headers()

            async def fetch(url):
                async with session.get(url, headers=headers) as resp:
                    return (await resp.json()).get("records", [])

            agents, tasks, kpis, departments = await asyncio.gather(
                fetch(urls["agents"]), fetch(urls["tasks"]), fetch(urls["kpis"]), fetch(urls["departments"])
            )

        dept_lookup = {
            d["id"]: {
                "name": d["fields"].get("Department Name"),
                "priority": d["fields"].get("Priority"),
                "status": d["fields"].get("Status"),
                "dashboard_url": d["fields"].get("Dashboard URL"),
                "head_agent": d["fields"].get("Head AI Agent")
            } for d in departments
        }

        results = []
        for a in agents:
            f = a["fields"]
            record_id = a["id"]
            gpt_name = f.get("Agent Name") or f.get("GPT ID") or record_id
            dept_id = f.get("Assigned Department", [None])[0]
            dept = dept_lookup.get(dept_id)

            task_ids = f.get("Tasks", [])
            task_details = [t for t in tasks if t["id"] in task_ids]
            kpi_list = [
                {
                    "kpi_name": k["fields"].get("KPI Name"),
                    "current_score": k["fields"].get("Current Score"),
                    "target_score": k["fields"].get("Target Score"),
                    "performance_status": k["fields"].get("Performance Status")
                }
                for k in kpis if record_id in k["fields"].get("AI Agents", [])
            ]

            result = {
                "gpt_name": gpt_name,
                "gpt_id": record_id,
                "internal_gpt_id": f.get("GPT ID", record_id),
                "role": dept["name"] if dept else None,
                "status": f.get("Status"),
                "department": dept,
                "total_tasks": len(task_details),
                "active_tasks": sum(1 for t in task_details if t["fields"].get("Status") not in ["Complete", "Archived"]),
                "completed_tasks": sum(1 for t in task_details if t["fields"].get("Status") == "Complete"),
                "linked_kpis": kpi_list
            }
            if debug:
                result["debug_linked_tasks"] = [
                    {
                        "task_name": t["fields"].get("Task Name"),
                        "status": t["fields"].get("Status"),
                        "due_date": t["fields"].get("Due Date")
                    } for t in task_details
                ]
                result["debug_linked_kpis"] = kpi_list

            results.append(result)

        return {"status": "success", "debug_mode": debug, "data": results}

    except Exception as e:
        logging.exception("GPT Health error")
        return {"status": "error", "message": "Failed to fetch GPT health stats", "details": str(e)}
