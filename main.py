from fastapi import FastAPI
from backend.tochange import router as router1
app = FastAPI()

app.include_router(router1)