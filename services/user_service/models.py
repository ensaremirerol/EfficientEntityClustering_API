from pydantic import BaseModel


class UserOut(BaseModel):
    user_id: str
    username: str
    scopes: list[str]


class UserCreateIn(BaseModel):
    username: str
    password: str
    scopes: list[str]


class UsernameUpdateIn(BaseModel):
    username: str
    password: str


class PasswordUpdateIn(BaseModel):
    old_password: str
    password: str


class ScopeUpdateIn(BaseModel):
    scopes: list[str]
