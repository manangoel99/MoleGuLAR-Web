from datetime import datetime, timedelta
from typing import Optional, Union

from db import database, users
from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from models.user import *

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_passwd, hashed_passwd):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_passwd, hashed_passwd)

def get_password_hash(password):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

async def get_user(email: str) -> UserInDB:
    query = users.select(users.c.email == email)
    user = await database.fetch_one(query=query)
    return user

async def authenticate_user(email: str, password: str) -> Union[bool, UserInDB]:
    query = users.select(users.c.email == email)

    user = await database.fetch_one(query=query)

    if not user:
        return False
    
    if not verify_password(password, user.password):
        return False
    
    return user

async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode: dict = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({'exp': expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception: Exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict = jwt.decode(
            token, SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data: TokenData = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user: UserInDB = await get_user(email=email)
    if user is None:
        raise credentials_exception
    return user

async def user_signup(payload: SignUpFormData) -> int:
    user_exists: Optional[UserInDB] = await get_user(payload.email)

    if user_exists:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    payload.password = get_password_hash(payload.password)

    query = users.insert().values(**payload.dict())
    return await database.execute(query=query)
