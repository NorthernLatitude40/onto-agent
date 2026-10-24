from sqlalchemy.orm import Session
from src.model.project import ScraperGroup

class ProjectDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        """查詢所有專案"""
        return self.db.query(ScraperGroup).all()

    def get_by_id(self, project_id: int):
        """根據 ID 查詢單一專案"""
        return self.db.query(ScraperGroup).filter(ScraperGroup.id == project_id).first()

    def create(self, name: str, description: str):
        """建立新專案"""
        db_project = ScraperGroup(name=name, description=description)
        self.db.add(db_project)
        self.db.commit()
        self.db.refresh(db_project)
        return db_project

    def delete(self, project: ScraperGroup):
        """刪除專案"""
        self.db.delete(project)
        self.db.commit()