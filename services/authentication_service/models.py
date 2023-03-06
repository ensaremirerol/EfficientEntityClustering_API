from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    scopes: list[str]
