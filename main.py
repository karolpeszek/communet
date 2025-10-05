from fastapi import FastAPI
from backend.tochange import router as router1
from backend.recurring_routes import router as recurring_routes
app = FastAPI()

app.include_router(router1)
app.include_router(recurring_routes)