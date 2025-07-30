from fastapi import FastAPI
from contextlib import asynccontextmanager

from routes.nova_routes import nova_router
from services.airtable_service import airtable

@asynccontextmanager
async def lifespan(app: FastAPI):
    await airtable.init_session()  # Startup
    yield
    await airtable.close_session()  # Shutdown

app = FastAPI(lifespan=lifespan)

app.include_router(nova_router, prefix="/nova")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Nova CEO API"}
