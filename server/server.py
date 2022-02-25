import os
from typing import List, Union
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, Header, UploadFile, status, File
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from models import user_manager
from models.user import *
from models.train_job import *

TRAINER_SERVER = "http://localhost:8001/api/v1/trainer"

server = APIRouter()

@server.get("/dashboard", response_model=User)
async def dashboard(user: User = Depends(user_manager.get_current_user)):
    return user

@server.post("/submit/train", response_model=int)
async def submit_train_job(
    pdb_file: UploadFile = File(...),
    gpf_file: UploadFile = File(...),
    params: TrainParams = Depends(), 
    user: User = Depends(user_manager.get_current_user)
    ):
    params_ = TrainParamsWithUser(**params.dict(), user_id=user.id)

    fixed_params = params_.dict()
    fixed_params['logP'] = str(fixed_params['logP']).lower()
    fixed_params['QED'] = str(fixed_params['QED']).lower()

    url = urlencode(params_.dict())

    print(url)

    response = requests.post(f"{TRAINER_SERVER}/submit/train?{url}", 
        files={
            "pdb_file": pdb_file.file,
            "gpf_file": gpf_file.file
            })
    return response.json()

@server.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user: Union[bool, UserInDB] = await user_manager.authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    access_token: str = await user_manager.create_access_token(
        data={'sub': user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@server.post("/signup", response_model=Token)
async def signup(form_data: SignUpFormData):
    out: int = await user_manager.user_signup(form_data)
    access_token: str = await user_manager.create_access_token(
        data={'sub': form_data.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
