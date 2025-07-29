from decouple import config

AIRTABLE_API_KEY = config("AIRTABLE_API_KEY", default="")
BASE_ID = config("BASE_ID", default="")
TABLE_ID_COMMANDS = config("TABLE_ID_COMMANDS", default="")
TABLE_ID_GPT_TREE = config("TABLE_ID_GPT_TREE", default="")
TABLE_ID_TASKS = config("TABLE_ID_TASKS", default="")
TABLE_ID_KPIS = config("TABLE_ID_KPIS", default="")
TABLE_ID_AI_AGENTS = config("TABLE_ID_AI_AGENTS", default="")
TABLE_ID_DEPARTMENTS = config("TABLE_ID_DEPARTMENTS", default="")
