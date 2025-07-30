import aiohttp
from utils.config import AIRTABLE_API_KEY, BASE_ID


class AirtableClient:
    def __init__(self, base_id, api_key):
        self.base_url = f"https://api.airtable.com/v0/{base_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.session: aiohttp.ClientSession | None = None

    async def init_session(self):
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch(self, table_id):
        url = f"{self.base_url}/{table_id}"
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                return await resp.json()
        except aiohttp.ClientError as e:
            return {"error": str(e)}

    async def post(self, table_id, payload):
        url = f"{self.base_url}/{table_id}"
        try:
            async with self.session.post(url, headers=self.headers, json=payload) as resp:
                return resp.status, await resp.text()
        except aiohttp.ClientError as e:
            return 500, str(e)


# Global instance
airtable = AirtableClient(BASE_ID, AIRTABLE_API_KEY)
