from models import UserOut, PasswordUpdateIn, ScopeUpdateIn, UserCreateIn, UsernameUpdateIn


from fastapi import FastAPI, Depends, HTTPException, status, Request, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from file_locker_middleware import FileLockerMiddleware
from eec.core.abstract.user_repository import IUserRepository
from eec import BaseUserRepository, Neo4JHelper, Neo4JUserRepository, UserModel, NotFoundException, AlreadyExistsException
from dotenv import load_dotenv
from pathlib import Path
import os
import json
import logging
import httpx

load_dotenv()

DATA_PATH = Path(os.getenv("DATA_PATH") or "data")
LOGGER_PATH = Path(os.getenv("LOGGER_PATH") or "logs")
SYSTEM_TYPE = os.getenv("SYSTEM_TYPE") or "base"
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL") or "http://eec.localhost/api/v1/auth"

user_repository: IUserRepository = None
last_user_repository_update: float = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

o_auth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scopes={"admin": "Admin access", "editor": "Editor access", "export": "Export access"})


def neo4j_user_repository():
    global user_repository

    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    Neo4JHelper(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD
    )

    user_repository = Neo4JUserRepository()


def read_base_user_repository():
    global user_repository, last_user_repository_update, DATA_PATH
    USER_DATA_PATH = DATA_PATH / "user_repository.json"

    if user_repository is None or last_user_repository_update is None or last_user_repository_update < USER_DATA_PATH.stat().st_mtime:
        if not USER_DATA_PATH.exists():
            print("User repository not found. Creating new one.")
            user_repository = BaseUserRepository()
            return
        with open(USER_DATA_PATH, "r") as f:
            user_repository = BaseUserRepository.decode(json.load(f))
        last_user_repository_update = USER_DATA_PATH.stat().st_mtime


def write_base_user_repository():
    global user_repository, last_user_repository_update, DATA_PATH
    USER_DATA_PATH = DATA_PATH / "user_repository.json"

    temp_path = USER_DATA_PATH.parent / (USER_DATA_PATH.name + ".tmp")
    with open(temp_path, "w") as f:
        json.dump(user_repository.encode(), f)
    os.replace(temp_path, USER_DATA_PATH)
    last_user_repository_update = USER_DATA_PATH.stat().st_mtime


async def auth_required(security_scopes: SecurityScopes, token: dict = Depends(o_auth2_scheme)):
    response = httpx.get(
        f'{AUTH_SERVICE_URL}/verify',
        headers={'Authorization': f"Bearer {token}"}
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if 'admin' in response.json()["scopes"]:
        return response.json()

    if 'admin' in security_scopes.scopes:
        if 'admin' not in response.json()["scopes"]:
            raise HTTPException(status_code=401, detail="Unauthorized")

    for scope in security_scopes.scopes:
        if scope != "admin" and scope not in response.json()["scopes"]:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return response.json()


app = FastAPI(
    title="User Repository Service", description="User Repository Service",
    root_path="/api/v1/users",
    root_path_in_servers=True
)
if SYSTEM_TYPE == "base":
    app.add_middleware(FileLockerMiddleware,
                       files_to_lock=[DATA_PATH / "user_repository.json"],
                       before=read_base_user_repository, after=write_base_user_repository)


@ app.on_event("startup")
async def startup_event():
    if SYSTEM_TYPE == "neo4j":
        neo4j_user_repository()

    elif SYSTEM_TYPE == "base":
        read_base_user_repository()


@ app.get("/", response_model=list[UserOut])
async def get_all_users(user: dict = Security(auth_required, scopes=[])):
    _all_users = user_repository.get_all_users()
    return [UserOut(
        user_id=user.user_id,
        username=user.username,
        scopes=user.scopes
    ) for user in _all_users]


@ app.get("/me", response_model=UserOut)
async def get_current_user(auth_user: dict = Security(auth_required)):
    return UserOut(
        user_id=auth_user["user_id"],
        username=auth_user["username"],
        scopes=auth_user["scopes"]
    )


@ app.get("/user/{id}", response_model=UserOut)
async def get_user(id: str, auth_user: dict = Security(auth_required, scopes=[])):
    try:
        user = user_repository.get_user_by_id(id)
        return UserOut(
            user_id=user.user_id,
            username=user.username,
            scopes=user.scopes
        )
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")


@ app.get("/user/username/{username}", response_model=UserOut)
async def get_user_by_username(username: str, auth_user: dict = Security(auth_required, scopes=[])):
    try:
        user = user_repository.get_user_by_name(username)
        return UserOut(
            user_id=user.user_id,
            username=user.username,
            scopes=user.scopes
        )
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")


@ app.post("/user/create", response_model=UserOut)
async def create_user(user: UserCreateIn, auth_user: dict = Security(auth_required, scopes=['admin'])):
    try:
        hashed_password = pwd_context.hash(user.password)
        data = user_repository.add_user(
            username=user.username,
            hashed_password=hashed_password,
            scopes=user.scopes,
        )
        return UserOut(
            user_id=data.user_id,
            username=data.username,
            scopes=data.scopes
        )
    except AlreadyExistsException:
        raise HTTPException(status_code=409, detail="User already exists")


@ app.put("/user/{id}/update/username", response_model=UserOut)
async def update_user_username(id: str, user: UsernameUpdateIn, auth_user: dict = Security(auth_required, scopes=[])):
    if auth_user["role"] != "admin" and auth_user["user_id"] != id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        db_user = user_repository.get_user_by_id(id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")

    if not pwd_context.verify(
            user.password, db_user.hashed_password) and auth_user["role"] != "admin":
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = user_repository.change_username(
            user_id=id,
            username=user.username,
        )
        return UserOut(
            user_id=data.user_id,
            username=data.username,
            scopes=data.scopes
        )
    except AlreadyExistsException:
        raise HTTPException(status_code=409, detail="Username already exists")


@ app.put("/user/{id}/update/password", response_model=UserOut)
async def update_user_password(id: str, user: PasswordUpdateIn, auth_user: dict = Security(auth_required, scopes=[])):
    if auth_user["role"] != "admin" and auth_user["user_id"] != id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        db_user = user_repository.get_user_by_id(id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")

    if not pwd_context.verify(user.old_password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        data = user_repository.change_password(
            user_id=id,
            hashed_password=pwd_context.hash(user.password),
        )
        return UserOut(
            user_id=data.user_id,
            username=data.username,
            scopes=data.scopes
        )
    except AlreadyExistsException:
        raise HTTPException(status_code=409, detail="Username already exists")


@ app.put("/user/{id}/update/scopes", response_model=UserOut)
async def update_user_role(id: str, user: ScopeUpdateIn, auth_user: dict = Security(auth_required, scopes=['admin'])):
    try:
        data = user_repository.change_scopes(
            user_id=id,
            scopes=user.scopes,
        )
        return UserOut(
            user_id=data.user_id,
            username=data.username,
            scopes=data.scopes
        )
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")


@ app.delete("/user/{id}/delete", status_code=204)
async def delete_user(id: str, auth_user: dict = Security(auth_required, scopes=['admin'])):
    try:
        user_repository.delete_user(id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
