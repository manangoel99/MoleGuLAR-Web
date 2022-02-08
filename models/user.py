from lib2to3.pgen2 import token
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class User(BaseModel):
    name: str
    email: str

class UserInDB(User):
    hashed_password: str

class SignUpFormData(User):
    password: str