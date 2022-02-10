import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from server.server import server
from trainer.trainer import trainer

metadata.create_all(engine)

os.environ["ROOT_DIR"] = "/home/manan/Desktop/MoleGuLAR-Web/MoleGuLAR-Web-app/data"
os.environ["TRAINER_SERVER"] = "https://localhost:8000/api/v1/trainer"

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(server)
