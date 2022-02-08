from typing import List, Union

from fastapi import APIRouter, Depends, Header, status
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from models import user_manager
from models.user import *

server = APIRouter()

@server.get("/dashboard", response_model=User)
async def dashboard(user: User = Depends(user_manager.get_current_user)):
    return user

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
