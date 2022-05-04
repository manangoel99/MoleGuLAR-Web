import os
from http import server

from fastapi import FastAPI

from db import database, engine, metadata
from trainer.trainer_server import trainer

metadata.create_all(engine)


def setup_docking_tool():
    os.system("tar -xf /app/mgltools_x86_64Linux2_1.5.7.tar_.gz")
    os.chdir("mgltools_x86_64Linux2_1.5.7")
    os.system("./install.sh")
    os.chdir("..")
    os.chdir("AutoDock-GPU")
    os.system("make DEVICE=CUDA NUMWI=64")
    os.chdir("..")


app = FastAPI()


@app.on_event("startup")
async def startup():
    setup_docking_tool()
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


app.include_router(trainer, prefix="/api/v1/trainer")
