import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from evaluator.evaluator import evaluator

metadata.create_all(engine)

app = FastAPI()


def setup_docking_tool():
    os.system("tar -xf /app/mgltools_x86_64Linux2_1.5.7.tar_.gz")
    os.chdir("mgltools_x86_64Linux2_1.5.7")
    os.system("./install.sh")
    os.chdir("..")
    os.chdir("AutoDock-GPU")
    os.system("make DEVICE=CUDA NUMWI=64")
    os.chdir("..")


@app.on_event("startup")
async def startup():
    setup_docking_tool()
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


app.include_router(evaluator, prefix="/api/v1/evaluator")
