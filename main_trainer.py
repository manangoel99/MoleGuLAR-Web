import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from trainer.trainer import trainer

metadata.create_all(engine)


app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(trainer, prefix="/api/v1/trainer")