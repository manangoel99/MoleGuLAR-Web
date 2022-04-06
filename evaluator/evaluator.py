import os
import pickle as pkl
import shutil
from pathlib import Path
import requests

import ray
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from werkzeug.utils import secure_filename
from db import JobStatus

TRAINER_SERVER = "http://localhost:8001/api/v1/trainer"

evaluator = APIRouter()

@evaluator.post("/submit/eval")
async def submit_eval_job(job_id: int, user_id: int):

    print(job_id, user_id)

    response = requests.get(f"{TRAINER_SERVER}/status/{user_id}/{job_id}")

    if response.status_code != 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=response.text)
    
    if response.json() != JobStatus.finished:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Job Not Finished")
    



