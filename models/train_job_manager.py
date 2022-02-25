from collections import defaultdict

import ray
from db import database, train_jobs

from models.train_job import *
from trainer.train_model import TrainModel

user_job_mapping = defaultdict(list)

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

    model_train_id = model.train.remote()

    user_job_mapping[(user_id, job_id)].append({
        "training_id": model_train_id
    })

    return job_id

