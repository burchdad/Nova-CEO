from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import asyncio

from services.airtable_service import airtable
from utils.config import (
    TABLE_ID_COMMANDS,
    TABLE_ID_GPT_TREE,
    TABLE_ID_AI_AGENTS,
    TABLE_ID_TASKS,
    TABLE_ID_KPIS,
    TABLE_ID_DEPARTMENTS
)

nova_router = APIRouter()


class CommandInput(BaseModel):
    command: str = Field(..., min_length=5, max_length=500, pattern=r"^[a-zA-Z0-9\s.,?!@#&()\-_=+]+$")


@nova_router.post("/command", tags=["Commands"])
async def process_command(input: CommandInput):
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
            return {
                "status": "error",
                "message": "Failed to log to Airtable",
                "details": response_data[:200]
            }
    except Exception as e:
        logging.exception("Unhandled exception in /nova/command")
        return {
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }


@nova_router.get("/gpt_tree", tags=["GPT Tree"])
async def get_gpt_tree():
    try:
        records = (await airtable.fetch(TABLE_ID_GPT_TREE)).get("records", [])
        id_to_name = {
            r["id"]: r["fields"].get("GPT Name")
            for r in records if r["fields"].get("GPT Name")
        }

        def build_tree(parent_name=None):
            tree = []
            for record in records:
                fields = record.get("fields", {})
                gpt_name = fields.get("GPT Name")
                parent_ids = fields.get("Parent GPT", [])
                parent_names = [id_to_name.get(pid) for pid in parent_ids]

                is_root = not parent_name and gpt_name == "Nova CEO GPT"
                is_child = parent_name and parent_name in parent_names

                if is_root or is_child:
                    children = build_tree(gpt_name)
                    tree.append({
                        "name": gpt_name,
                        "id": fields.get("GPT ID", record["id"]),
                        "role": fields.get("Role / Department"),
                        "status": fields.get("Status"),
                        "linked_department": fields.get("Linked Department"),
                        "dashboard_url": fields.get("Dashboards URL"),
                        "children": children
                    })
            return tree

        return {"status": "success", "data": {"gpt_tree": build_tree()}}
    except Exception as e:
        logging.exception("GPT Tree build error")
        return {
            "status": "error",
            "message": "Failed to fetch GPT Tree",
            "details": str(e)
        }


@nova_router.get("/gpt_health", tags=["GPT Health"])
async def get_gpt_health(debug: bool = Query(False)):
    try:
        agents, tasks, kpis, departments = await asyncio.gather(
            airtable.fetch(TABLE_ID_AI_AGENTS),
            airtable.fetch(TABLE_ID_TASKS),
            airtable.fetch(TABLE_ID_KPIS),
            airtable.fetch(TABLE_ID_DEPARTMENTS)
        )

        dept_lookup = {
            d["id"]: {
                "name": f.get("Department Name"),
                "priority": f.get("Priority"),
                "status": f.get("Status"),
                "dashboard_url": f.get("Dashboard URL"),
                "head_agent": f.get("Head AI Agent")
            }
            for d in departments.get("records", [])
            if (f := d.get("fields"))
        }

        results = []
        for a in agents.get("records", []):
            f = a.get("fields", {}) or {}
            record_id = a.get("id")
            gpt_name = f.get("Agent Name") or f.get("GPT ID") or record_id

            assigned_dept = f.get("Assigned Department") or []
            dept_id = assigned_dept[0] if assigned_dept else None
            dept = dept_lookup.get(dept_id)

            task_ids = f.get("Tasks") or []
            task_details = [t for t in tasks.get("records", []) if t.get("id") in task_ids]

            kpi_list = [
                {
                    "kpi_name": kf.get("KPI Name"),
                    "current_score": kf.get("Current Score"),
                    "target_score": kf.get("Target Score"),
                    "performance_status": kf.get("Performance Status")
                }
                for k in kpis.get("records", [])
                if record_id in (kf := k.get("fields", {})).get("AI Agents", [])
            ]

            result = {
                "gpt_name": gpt_name,
                "gpt_id": record_id,
                "internal_gpt_id": f.get("GPT ID", record_id),
                "role": dept["name"] if dept else None,
                "status": f.get("Status"),
                "department": dept,
                "total_tasks": len(task_details),
                "active_tasks": sum(1 for t in task_details if t.get("fields", {}).get("Status") not in ["Complete", "Archived"]),
                "completed_tasks": sum(1 for t in task_details if t.get("fields", {}).get("Status") == "Complete"),
                "linked_kpis": kpi_list
            }

            if debug:
                result["debug_linked_tasks"] = [
                    {
                        "task_name": t.get("fields", {}).get("Task Name"),
                        "status": t.get("fields", {}).get("Status"),
                        "due_date": t.get("fields", {}).get("Due Date")
                    } for t in task_details
                ]
                result["debug_linked_kpis"] = kpi_list

            results.append(result)

        return {"status": "success", "debug_mode": debug, "data": results}

    except Exception as e:
        logging.exception("GPT Health error")
        return {
            "status": "error",
            "message": "Failed to fetch GPT health stats",
            "details": str(e)
        }


@nova_router.get("/gpt_agents", tags=["GPT Agents"])
async def get_gpt_agents():
    try:
        records = (await airtable.fetch(TABLE_ID_AI_AGENTS)).get("records", [])
        agents = [
            {
                "id": r["id"],
                "name": r["fields"].get("Agent Name") or r["fields"].get("GPT ID"),
                "role": r["fields"].get("Role / Department"),
                "status": r["fields"].get("Status"),
                "dashboard_url": r["fields"].get("Dashboards URL")
            }
            for r in records if r.get("fields", {}).get("Agent Name") or r.get("fields", {}).get("GPT ID")
        ]
        return {"status": "success", "data": agents}
    except Exception as e:
        logging.exception("GPT Agents fetch error")
        return {
            "status": "error",
            "message": "Failed to fetch GPT Agents",
            "details": str(e)
        }


@nova_router.get("/gpt_departments", tags=["GPT Departments"])
async def get_gpt_departments():
    try:
        records = (await airtable.fetch(TABLE_ID_DEPARTMENTS)).get("records", [])
        departments = [
            {
                "id": r["id"],
                "name": r["fields"].get("Department Name"),
                "priority": r["fields"].get("Priority"),
                "status": r["fields"].get("Status"),
                "dashboard_url": r["fields"].get("Dashboard URL"),
                "head_agent": r["fields"].get("Head AI Agent")
            }
            for r in records if r.get("fields", {}).get("Department Name")
        ]
        return {"status": "success", "data": departments}
    except Exception as e:
        logging.exception("GPT Departments fetch error")
        return {
            "status": "error",
            "message": "Failed to fetch GPT Departments",
            "details": str(e)
        }


@nova_router.get("/gpt_kpis", tags=["GPT KPIs"])
async def get_gpt_kpis():
    try:
        records = (await airtable.fetch(TABLE_ID_KPIS)).get("records", [])
        kpis = [
            {
                "id": r["id"],
                "name": r["fields"].get("KPI Name"),
                "current_score": r["fields"].get("Current Score"),
                "target_score": r["fields"].get("Target Score"),
                "performance_status": r["fields"].get("Performance Status"),
                "linked_agents": r["fields"].get("AI Agents", [])
            }
            for r in records if r.get("fields", {}).get("KPI Name")
        ]
        return {"status": "success", "data": kpis}
    except Exception as e:
        logging.exception("GPT KPIs fetch error")
        return {
            "status": "error",
            "message": "Failed to fetch GPT KPIs",
            "details": str(e)
        }

print("nova_routes.py loaded")

__all__ = ["nova_router"]
