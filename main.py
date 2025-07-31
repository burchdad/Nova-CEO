import os
from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from routes.nova_routes import nova_router
from services.airtable_service import airtable
from decouple import config

# Load environment variables from .env file
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await airtable.init_session()  # Startup

    # Optional debug logging (safe for dev, remove/comment in prod)
    #BASE_ID = config("BASE_ID", default="NOT SET")
    #TABLE_ID_COMMANDS = config("TABLE_ID_COMMANDS", default="NOT SET")
    #AIRTABLE_API_KEY = config("AIRTABLE_API_KEY", default="NOT SET")
    
    #print("🧪 ENV TABLE_ID_COMMANDS:", TABLE_ID_COMMANDS)
    #print("🧪 ENV BASE_ID:", BASE_ID)
    #print("🧪 ENV AIRTABLE_API_KEY:", (AIRTABLE_API_KEY[:4] + "..." + AIRTABLE_API_KEY[-4:]) if AIRTABLE_API_KEY != "NOT SET" else "NOT SET")

    yield

    await airtable.close_session()  # Shutdown

# Initialize FastAPI with lifecycle hooks
app = FastAPI(lifespan=lifespan)

# Register routes
app.include_router(nova_router, prefix="/nova")

# Default healthcheck route
@app.get("/")
def read_root():
    return {"message": "Welcome to the Nova CEO API"}
