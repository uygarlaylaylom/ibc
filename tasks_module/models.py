from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class TaskCreate(BaseModel):
    """Pydantic model for creating a Task."""
    source_company: str
    task_description: str
    tags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    bracket_category: Optional[str] = None
    status: str = Field(default="Todo")
    priority: str = Field(default="Normal")
    due_date: Optional[datetime] = None
    owner: Optional[str] = None
    hall: Optional[str] = None
    category: Optional[str] = None

class TaskUpdate(BaseModel):
    """Pydantic model for updating a Task."""
    status: Optional[str] = None
    priority: Optional[str] = None

class Task(TaskCreate):
    """Pydantic model representing a Task reading from DB."""
    id: UUID
    created_at: datetime
