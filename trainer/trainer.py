from logging import root
import os
import shutil

import ray
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from models import train_job_manager
from models.train_job import *
from werkzeug.utils import secure_filename

ray.init()

trainer = APIRouter()

@trainer.post("/submit/train")
async def submit_train_job(pdb_file: UploadFile = File(...), gpf_file: UploadFile = File(...), params: TrainParamsWithUser = Depends()):
    
    root_path = os.getenv("ROOT_DIR")
    user_id = params.dict().get("user_id", None)

    print(root_path, user_id, params)

    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    # try:
    user_path = os.path.join(root_path, str(user_id))
    if not os.path.exists(user_path):
        os.mkdir(user_path)
    pdb_file_path = os.path.join(user_path, secure_filename(pdb_file.filename) + ".pdb")
    with open(pdb_file_path, "wb") as f:
        shutil.copyfileobj(pdb_file.file, f)
    
    gpf_file_path = os.path.join(user_path, secure_filename(gpf_file.filename) + ".gpf")
    with open(gpf_file_path, "wb") as f:
        shutil.copyfileobj(gpf_file.file, f)
    # except:
    #     raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user directory")

    job_id = await train_job_manager.create_job(pdb_file_path, gpf_file_path, params.dict() , user_id)
    return job_id
