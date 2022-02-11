import ray
from db import database, train_jobs

from models.train_job import *

async def create_job(pdb_path: str, gpf_path: str, params: dict, user_id: int):
    job = TrainJob(pdb_path=pdb_path, gpf_path=gpf_path, params=params, user_id=user_id)
    query = train_jobs.insert().values(**job.dict())
    return await database.execute(query)
