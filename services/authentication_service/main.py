from models import Token, AuthenticatedUser

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from file_locker_middleware import FileLockerMiddleware
from eec.core.abstract.user_repository import IUserRepository
from eec import BaseUserRepository, Neo4JHelper, Neo4JUserRepository, UserModel, NotFoundException
from dotenv import load_dotenv
from pathlib import Path
import os
import json
import logging

load_dotenv()

DATA_PATH = Path(os.getenv("DATA_PATH") or "data")
LOGGER_PATH = Path(os.getenv("LOGGER_PATH") or "logs")
SYSTEM_TYPE = os.getenv("SYSTEM_TYPE") or "base"
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
user_repository: IUserRepository = None
last_user_repository_update: float = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

o_auth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", scopes={"admin": "Admin access"})


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


app = FastAPI(
    title="Authentication Service", description="Authentication Service for EEC",
    root_path="/api/v1/auth", version="1.0.0",
    root_path_in_servers=True
)
if SYSTEM_TYPE == "base":
    app.add_middleware(FileLockerMiddleware,
                       files_to_lock=[DATA_PATH / "user_repository.json"],
                       before=read_base_user_repository, after=write_base_user_repository)


@app.on_event("startup")
async def startup_event():
    if SYSTEM_TYPE == "neo4j":
        neo4j_user_repository()

    elif SYSTEM_TYPE == "base":
        read_base_user_repository()
    user_count = user_repository.get_user_count()

    if user_count == 1:
        user = user_repository.get_all_users()[0]
        user_repository.change_role(user.user_id, "admin")
        write_base_user_repository()

    elif user_count == 0:
        user_repository.add_user(
            username="admin", hashed_password=pwd_context.hash("admin"), role="admin")
        write_base_user_repository()


@app.post("/login", response_model=Token, tags=["auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user: UserModel = user_repository.get_user_by_name(form_data.username)
    except NotFoundException:
        print("User not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "sub": user.username,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token, "token_type": "bearer"}


@app.get("/verify", response_model=AuthenticatedUser, tags=["auth"])
async def verify(request: Request, token: str = Depends(o_auth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        exp: float = payload.get("exp")
        if exp is None or exp < datetime.utcnow().timestamp():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user_repository.username_exists(username):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(username=username, role=role)


if __name__ == "__main__":
    print("only debug")
    logging.basicConfig(level=logging.DEBUG)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
