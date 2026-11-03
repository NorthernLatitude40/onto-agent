from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from src.api.v1.endpoints.dao.project_dao import ProjectDAO
from src.api.v1.endpoints.dto.schemas import ProjectCreate

class ProjectService:
    def __init__(self, db: Session):
        self.dao = ProjectDAO(db)

    def get_projects(self):
        """取得專案列表的商業邏輯"""
        # 這裡可以加入額外的商業邏輯，例如權限檢查、數據過濾等
        return self.dao.get_all()

    def create_project(self, payload: ProjectCreate):
        """建立專案的商業邏輯"""
        try:
            return self.dao.create(name=payload.name, description=payload.description)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"創建專案失敗: {str(e)}"
            )

    def delete_project(self, project_id: int):
        """刪除專案的商業邏輯"""
        project = self.dao.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="專案未找到"
            )
        try:
            self.dao.delete(project)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"刪除專案失敗: {str(e)}"
            )

    def get_vehicle_configs(self):
        """获取车辆配置数据（使用连接池和缓存优化）"""
        from src.api.v1.endpoints.dao.vehicle_repo import list_vehicles
        
        # 直接调用 vehicle_repo 的方法，它已经实现了连接池和缓存
        return list_vehicles()