from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
import aiohttp
import asyncio
import logging
from datetime import datetime
from typing import Optional
from decouple import config

# ===========================
# 🔹 App + Logging Setup
# ===========================
app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ===========================
# 🔹 Persistent aiohttp Session
# ===========================
session = aiohttp.ClientSession()

@app.on_event("shutdown")
async def shutdown_event():
    await session.close()

# ===========================
# 🔹 Airtable Config (via python-decouple)
# ===========================
AIRTABLE_API_KEY = config("AIRTABLE_API_KEY", default="")
BASE_ID = config("BASE_ID", default="")
TABLE_ID_COMMANDS = config("TABLE_ID_COMMANDS", default="")
TABLE_ID_GPT_TREE = config("TABLE_ID_GPT_TREE", default="")
TABLE_ID_TASKS = config("TABLE_ID_TASKS", default="")
TABLE_ID_KPIS = config("TABLE_ID_KPIS", default="")
TABLE_ID_AI_AGENTS = config("TABLE_ID_AI_AGENTS", default="")
TABLE_ID_DEPARTMENTS = config("TABLE_ID_DEPARTMENTS", default="")

if not AIRTABLE_API_KEY:
    raise RuntimeError("Missing AIRTABLE_API_KEY")

# ===========================
# 🔹 Airtable Helper Class
# ===========================
class AirtableClient:
    def __init__(self, base_id, api_key):
        self.base_url = f"https://api.airtable.com/v0/{base_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def fetch(self, table_id):
        url = f"{self.base_url}/{table_id}"
        async with session.get(url, headers=self.headers) as resp:
            return await resp.json()

    async def post(self, table_id, payload):
        url = f"{self.base_url}/{table_id}"
        async with session.post(url, headers=self.headers, json=payload) as resp:
            return resp.status, await resp.text()

airtable = AirtableClient(BASE_ID, AIRTABLE_API_KEY)

# ===========================
# 🔹 Nova Command Input Model
# ===========================
class CommandInput(BaseModel):
    command: str = Field(..., min_length=5, max_length=500, regex=r"^[a-zA-Z0-9\s.,?!@#&()\-_=+]+$")

# ===========================
# ✅ POST /nova/command
# ===========================
@app.post("/nova/command")
async def process_command(input: CommandInput):
    """
    Processes a command and logs it to Airtable.
    """
    try:
        command_text = input.command
        issued_date = datetime.utcnow().strftime("%Y-%m-%d")
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
        status, response_data = await airtable.post(TABLE_ID_COMMANDS, payload)
        if status in (200, 201):
            return {"status": "success", "message": f"✅ Logged in Airtable: {command_text}"}
        else:
            logging.error(f"❌ Airtable Error: {status} - {response_data[:200]}")
            return {"status": "error", "message": "Failed to log to Airtable", "details": response_data[:200]}
    except Exception as e:
        logging.exception(f"Unhandled exception in /nova/command: {e}")
        return {"status": "error", "message": "Internal server error", "details": str(e)}

# ===========================
# ✅ GPT Tree Fetch + Builder
# ===========================
@app.get("/nova/gpt_tree")
async def get_gpt_tree():
    """
    Constructs a tree of GPTs from Airtable based on parent-child hierarchy.
    """
    try:
        records = (await airtable.fetch(TABLE_ID_GPT_TREE)).get("records", [])
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
        logging.exception(f"GPT Tree build error: {e}")
        return {"status": "error", "message": "Failed to fetch GPT Tree", "details": str(e)}

# ===========================
# ✅ GPT Health Endpoint
# ===========================
@app.get("/nova/gpt_health")
async def get_gpt_health(debug: bool = Query(False)):
    """
    Aggregates GPT health stats across agents, tasks, KPIs, and departments.
    """
    try:
        agents, tasks, kpis, departments = await asyncio.gather(
            airtable.fetch(TABLE_ID_AI_AGENTS),
            airtable.fetch(TABLE_ID_TASKS),
            airtable.fetch(TABLE_ID_KPIS),
            airtable.fetch(TABLE_ID_DEPARTMENTS)
        )

        agents = agents.get("records", [])
        tasks = tasks.get("records", [])
        kpis = kpis.get("records", [])
        departments = departments.get("records", [])

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
        logging.exception(f"GPT Health error: {e}")
        return {"status": "error", "message": "Failed to fetch GPT health stats", "details": str(e)}
