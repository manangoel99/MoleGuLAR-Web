import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from evaluator.evaluator import evaluator

metadata.create_all(engine)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(evaluator, prefix="/api/v1/evaluator")