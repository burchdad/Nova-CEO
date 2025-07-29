from fastapi import FastAPI
from routes.nova_routes import router as nova_router

app = FastAPI()
app.include_router(nova_router, prefix="/nova")

# Gracefully shutdown aiohttp session
from services.airtable_service import close_session

@app.on_event("shutdown")
async def shutdown_event():
    await close_session()
