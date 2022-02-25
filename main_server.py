from logging import root
import os
from http import server

from fastapi import FastAPI
from sqlalchemy import exists

from db import database, engine, metadata
from server.server import server

from pathlib import Path

metadata.create_all(engine)

os.environ["ROOT_DIR"] = "/home/manan/Desktop/MoleGuLAR-Web/MoleGuLAR-Web-app/data"
os.environ["TRAINER_SERVER"] = "https://localhost:8000/api/v1/trainer"

root_path = Path(os.getenv("ROOT_DIR"))
root_path.mkdir(parents=True, exist_ok=True)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(server)
