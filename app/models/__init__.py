"""SQLAlchemy ORM models for CMDB configuration items.

Import all models here so that Base.metadata.create_all() discovers them.
"""

from app.models.app import App
from app.models.device import Device
from app.models.ingestion_log import IngestionLog
from app.models.relationships import (
    app_integrations,
    device_app_dependencies,
    user_app_assignments,
)
from app.models.user import User

__all__ = [
    "App",
    "Device",
    "IngestionLog",
    "User",
    "app_integrations",
    "device_app_dependencies",
    "user_app_assignments",
]
