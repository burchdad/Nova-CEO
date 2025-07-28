from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
import aiohttp
import asyncio
import os
from datetime import datetime

app = FastAPI()

# ===========================
# 🔹 Airtable Config
# ===========================
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
BASE_ID = os.environ.get("BASE_ID")
    if not AIRTABLE_API_KEY or not BASE_ID:
    raise RuntimeError("🚨 Missing environment variables! Check Render settings.")
TABLE_ID_COMMANDS = os.environ.get("TABLE_ID_COMMANDS")
TABLE_ID_GPT_TREE = os.environ.get("TABLE_ID_GPT_TREE")
TABLE_ID_TASKS = os.environ.get("TABLE_ID_TASKS")
TABLE_ID_KPIS = os.environ.get("TABLE_ID_KPIS")
TABLE_ID_AI_AGENTS = os.environ.get("TABLE_ID_AI_AGENTS")
TABLE_ID_DEPARTMENTS = os.environ.get("TABLE_ID_DEPARTMENTS")

# ===========================
# 🔹 Nova Command Input Model
# ===========================
class CommandInput(BaseModel):
    command: str

# ===========================
# ✅ EXISTING: Nova Command Endpoint
# ===========================
@app.post("/nova/command")
def process_command(input: CommandInput):
    try:
        command_text = input.command
        issued_date = datetime.utcnow().strftime("%Y-%m-%d")

        airtable_url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_COMMANDS}"
        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

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

        response = requests.post(airtable_url, headers=headers, json=payload)

        print("🔗 Airtable URL:", airtable_url)
        print("📥 Command Text:", command_text)
        print("📅 Issued Date:", issued_date)
        print("🔍 Airtable Response:", response.status_code, response.text)

        if response.status_code in (200, 201):
            return {"status": "success", "message": f"✅ Logged in Airtable: {command_text}"}
        else:
            return {"status": "error", "message": "❌ Failed to log to Airtable", "details": response.text}

    except Exception as e:
        print("❌ Exception:", str(e))
        return {"status": "error", "message": "Internal server error", "details": str(e)}

# ===========================
# ✅ GPT Tree Helpers
# ===========================
async def fetch_gpt_tree_records():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_GPT_TREE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            return data.get("records", [])

def map_record_ids(records):
    id_to_name = {}
    for rec in records:
        rec_id = rec.get("id")
        fields = rec.get("fields", {})
        if rec_id and fields.get("GPT Name"):
            id_to_name[rec_id] = fields["GPT Name"]
    return id_to_name

def build_tree(records, id_to_name, parent_name=None):
    tree = []
    for rec in records:
        fields = rec.get("fields", {})
        gpt_name = fields.get("GPT Name", "")
        gpt_id = fields.get("GPT ID")
        parent_ids = fields.get("Parent GPT", [])
        parent_names = [id_to_name.get(pid, pid) for pid in parent_ids]

        if (parent_name is None and gpt_name == "Nova CEO GPT") or (parent_name in parent_names):
            children = build_tree(records, id_to_name, gpt_name)
            tree.append({
                "name": gpt_name,
                "id": gpt_id,
                "role": fields.get("Role / Department"),
                "status": fields.get("Status"),
                "linked_department": fields.get("Linked Department"),
                "dashboard_url": fields.get("Dashboards URL"),
                "children": children
            })
    return tree

@app.get("/nova/gpt_tree")
async def get_gpt_tree():
    try:
        records = await fetch_gpt_tree_records()
        id_to_name = map_record_ids(records)
        tree = build_tree(records, id_to_name)
        return {"gpt_tree": tree}
    except Exception as e:
        print("❌ GPT Tree Error:", str(e))
        return {"status": "error", "message": "Failed to fetch GPT Tree", "details": str(e)}

# ===========================
# ✅ Fetch Helpers for GPT Health
# ===========================

async def fetch_ai_agents():
    """Fetch AI Agents table (true source for task links)."""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_AI_AGENTS}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()

            # ✅ DEBUG: Print the first record’s fields to inspect actual column names
            if data.get("records"):
                print("🔍 SAMPLE AI Agent Fields:", data["records"][0].get("fields", {}))

            return data.get("records", [])

async def fetch_tasks():
    """Fetch all Tasks (for status lookups)."""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_TASKS}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return (await resp.json()).get("records", [])

async def fetch_kpis():
    """Fetch all KPIs (for linking to AI Agents)."""
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_KPIS}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return (await resp.json()).get("records", [])

async def fetch_departments():
    url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID_DEPARTMENTS}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return (await resp.json()).get("records", [])

# ===========================
# ✅ GPT Health Endpoint (with optional debug mode)
# ===========================
@app.get("/nova/gpt_health")
async def get_gpt_health(debug: bool = Query(False, description="Enable detailed debug info for tasks/KPIs")):
    try:
        # ✅ Fetch everything in parallel
        ai_agents_task = fetch_ai_agents()
        tasks_records_task = fetch_tasks()
        kpi_records_task = fetch_kpis()
        departments_task = fetch_departments()

        ai_agents_records, tasks_records, kpi_records, departments_records = await asyncio.gather(
            ai_agents_task,
            tasks_records_task,
            kpi_records_task,
            departments_task
        )

        # ✅ Build Department lookup: {recID → details}
        department_lookup = {
            dept["id"]: {
                "name": dept["fields"].get("Department Name", "Unknown"),
                "priority": dept["fields"].get("Priority", "Unknown"),
                "status": dept["fields"].get("Status", "Unknown"),
                "dashboard_url": dept["fields"].get("Dashboard URL", None),
                "head_agent": dept["fields"].get("Head AI Agent", []),
            }
            for dept in departments_records
        }

        health_data = []

        for agent in ai_agents_records:
            fields = agent.get("fields", {})

            # ✅ Pick the best possible GPT Name (multiple fallbacks)
            gpt_name = (
                fields.get("AI Agent Name") or
                fields.get("Agent Name") or
                fields.get("GPT ID") or
                agent.get("id", "Unnamed GPT")
            )

            # ✅ Airtable Record ID for backend linking
            gpt_record_id = agent.get("id", "")

            # ✅ Internal GPT ID (fallback to record_id if missing)
            gpt_internal_id = fields.get("GPT ID", gpt_record_id)

            # ✅ Status
            gpt_status = fields.get("Status", "Unknown")

            # ✅ Resolve Role / Department
            assigned_depts = fields.get("Assigned Department", [])
            dept_details = None
            gpt_role = "Unknown"
            if assigned_depts:
                dept_id = assigned_depts[0]  # Take first if multiple
                dept_details = department_lookup.get(dept_id, None)
                if dept_details:
                    gpt_role = dept_details["name"]

            # ✅ Tasks linked to this AI Agent
            linked_task_ids = fields.get("Tasks", [])
            gpt_tasks = [t for t in tasks_records if t["id"] in linked_task_ids]

            total_tasks = len(gpt_tasks)
            active_tasks = sum(
                1 for t in gpt_tasks if t.get("fields", {}).get("Status") not in ["Complete", "Archived"]
            )
            completed_tasks = sum(
                1 for t in gpt_tasks if t.get("fields", {}).get("Status") == "Complete"
            )

            # ✅ KPIs linked to this AI Agent
            gpt_kpis = []
            for kpi in kpi_records:
                kpi_fields = kpi.get("fields", {})
                linked_agents = kpi_fields.get("AI Agents", [])
                if gpt_record_id in linked_agents:
                    gpt_kpis.append({
                        "kpi_name": kpi_fields.get("KPI Name"),
                        "current_score": kpi_fields.get("Current Score"),
                        "target_score": kpi_fields.get("Target Score"),
                        "performance_status": kpi_fields.get("Performance Status")
                    })

            # ✅ Debugging linked tasks + KPIs if requested
            debug_task_list = []
            debug_kpi_list = []
            if debug:
                debug_task_list = [
                    {
                        "task_name": t["fields"].get("Task Name"),
                        "status": t["fields"].get("Status"),
                        "due_date": t["fields"].get("Due Date")
                    } for t in gpt_tasks
                ]
                debug_kpi_list = gpt_kpis

            # ✅ Build GPT Health entry
            health_entry = {
                "gpt_name": gpt_name,
                "gpt_id": gpt_record_id,
                "internal_gpt_id": gpt_internal_id,
                "role": gpt_role,
                "status": gpt_status,
                "department": dept_details if dept_details and dept_details["name"] != "Unknown" else None,
                "total_tasks": total_tasks,
                "active_tasks": active_tasks,
                "completed_tasks": completed_tasks,
                "linked_kpis": gpt_kpis
            }

            if debug:
                health_entry["debug_linked_tasks"] = debug_task_list
                health_entry["debug_linked_kpis"] = debug_kpi_list

            health_data.append(health_entry)

        return {"gpt_health": health_data, "debug_mode": debug}

    except Exception as e:
        print("❌ GPT Health Error:", str(e))
        return {
            "status": "error",
            "message": "Failed to fetch GPT health stats",
            "details": str(e)
        }
