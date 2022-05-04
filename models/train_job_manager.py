import asyncio
import os
import pickle as pkl
from collections import defaultdict
from pathlib import Path

import ray
from db import JobStatus, database, train_jobs
from fastapi import status
from fastapi.exceptions import HTTPException
from trainer.train_model import TrainModel

from models.train_job import *


async def create_job(pdb_path: str, gpf_path: str, params: dict, user_id: int):
    job = TrainJob(pdb_path=pdb_path, gpf_path=gpf_path, params=params, user_id=user_id)

    query = train_jobs.insert().values(**job.dict())
    job_id = await database.execute(query)

    loop = asyncio.get_event_loop()
    # await run_job(job_id, user_id, pdb_path, gpf_path, params)
    loop.create_task(run_job(job_id, user_id, pdb_path, gpf_path, params))

    return job_id


async def run_job(
    job_id: int, user_id: int, pdb_path: str, gpf_path: str, params: dict
):
    model = TrainModel.remote(
        {
            "pdb_path": pdb_path,
            "gpf_path": gpf_path,
            "user_id": user_id,
            "params": params,
        },
        job_id,
    )

    model_train_id = model.train.remote()
    try:
        ray.get(model_train_id)
    except:
        query = (
            train_jobs.update()
            .where(train_jobs.c.id == job_id)
            .values(status=JobStatus.failed)
        )
        await database.execute(query)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error in training job"
        )

    query = (
        train_jobs.update()
        .where(train_jobs.c.id == job_id)
        .values(status=JobStatus.finished)
    )
    return await database.execute(query)


async def get_job_status(user_id: int, job_id: int):
    query = train_jobs.select().where(train_jobs.c.id == job_id)
    job = await database.fetch_one(query)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Job not found")

    return job.status
