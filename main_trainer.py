import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from trainer.trainer import trainer

metadata.create_all(engine)

os.environ["ROOT_DIR"] = "/home/manan/Desktop/MoleGuLAR-Web/MoleGuLAR-Web-app/data"
os.environ["TRAINER_SERVER"] = "https://localhost:8000/api/v1/trainer"
os.environ["AUTODOCK_PATH"] = "/home/manan/MGLTools-1.5.7/bin/pythonsh /home/manan/MGLTools-1.5.7/MGLToolsPckgs/AutoDockTools/Utilities24"

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(trainer, prefix="/api/v1/trainer")