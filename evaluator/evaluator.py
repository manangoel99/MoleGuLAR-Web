import os
import pickle as pkl
import shutil
from pathlib import Path

import ray
import requests
from db import JobStatus
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from models.eval_job_manager import get_molecules
from werkzeug.utils import secure_filename

TRAINER_SERVER = "http://localhost:8001/api/v1/trainer"

evaluator = APIRouter()


@evaluator.post("/submit/eval")
async def submit_eval_job(job_id: int, user_id: int, num_molecules: int = 10):
    response = requests.get(f"{TRAINER_SERVER}/status/{user_id}/{job_id}")
    print(response.json())
    if response.status_code != 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=response.text)

    if response.json() != "finished":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Job Not Finished")

    return await get_molecules(job_id, user_id, num_molecules)
