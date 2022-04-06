from fastapi.exceptions import HTTPException
from fastapi import status
import os
import pickle as pkl
from collections import defaultdict
from pathlib import Path

import ray
from db import database, train_jobs, JobStatus
from trainer.train_model import TrainModel

from models.train_job import *

async def create_job(pdb_path: str, gpf_path: str, params: dict, user_id: int):
    job = TrainJob(pdb_path=pdb_path, gpf_path=gpf_path, params=params, user_id=user_id)
    
    query = train_jobs.insert().values(**job.dict())
    job_id = await database.execute(query)

    model = TrainModel.remote({
        "pdb_path": pdb_path,
        "gpf_path": gpf_path,
        "user_id": user_id,
        "params": params
    }, job_id)


    #TODO: Figure out a way to lock the file for writing

    user_mapping_file = Path(
        os.path.join(os.environ["ROOT_DIR"], "user_job_mapping.pkl")
    )

    model_train_id = model.train.remote()

    try:
        with open(user_mapping_file, "rb") as f:
            user_job_mapping = pkl.load(f)
    except FileNotFoundError:
        user_job_mapping = defaultdict(list)
    user_job_mapping[(user_id, job_id)].append({
        "training_id": model_train_id
    })


    with open(user_mapping_file, "wb") as f:
        pkl.dump(user_job_mapping, f)

    return job_id

async def get_job_status(user_id: int, job_id: int):
    user_mapping_file = Path(
        os.path.join(os.environ["ROOT_DIR"], "user_job_mapping.pkl")
    )
    try:
        with open(user_mapping_file, "rb") as f:
            user_job_mapping = pkl.load(f)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No job found")
    
    if (user_id, job_id) not in user_job_mapping:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No job found")
    
    ray_train_job_id = user_job_mapping[(user_id, job_id)]
    ls = []
    for i in ray_train_job_id:
        ls.append(i['training_id'])
    ready, not_ready = ray.wait(ls, timeout=0.1)

    if ls[0] in not_ready:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="training jop is still in progress")
    
    query = train_jobs.update().where(train_jobs.c.id == job_id).values(status=JobStatus.finished)
    await database.execute(query)

    return JobStatus.finished