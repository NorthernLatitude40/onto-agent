from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from src.common.database import get_db
from src.api.v1.endpoints.dto.schemas import ProjectCreate, ProjectResponse
from src.api.v1.endpoints.service.project_service import ProjectService

router = APIRouter()

# 1. 獲取爬蟲專案/群組列表
@router.get("/projects", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    service = ProjectService(db)
    return service.get_projects()

# 2. 創建新的爬蟲專案/群組
@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    service = ProjectService(db)
    return service.create_project(payload)

# 3. 刪除爬蟲專案/群組
@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    service = ProjectService(db)
    service.delete_project(project_id)
    return None
