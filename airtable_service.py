import aiohttp
from utils.config import AIRTABLE_API_KEY, BASE_ID

session = aiohttp.ClientSession()

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

async def close_session():
    await session.close()
