from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class AuthenticatedUser(BaseModel):
    username: str
    role: str
