from typing import List
from fastapi import APIRouter, HTTPException, Header

from eec import BaseEntity, BaseEntityRepository

entities_router = APIRouter()
