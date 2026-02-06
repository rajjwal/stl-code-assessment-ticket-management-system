"""Junction tables for many-to-many relationships between CIs.

These are defined as SQLAlchemy Table objects (not ORM models) since they
are pure association tables with no extra columns beyond foreign keys.
"""

from sqlalchemy import Column, ForeignKey, String, Table

from app.database import Base

# Links Okta users to the applications they use.
# Populated by matching user.apps array entries against app.name via fuzzy matching.
user_app_assignments = Table(
    "user_app_assignments",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("app_id", String, ForeignKey("apps.id"), primary_key=True),
)

# Tracks integration relationships between applications.
# target_app_id is nullable because some integration targets (e.g., "Docker")
# may not exist as managed apps in the CMDB.
app_integrations = Table(
    "app_integrations",
    Base.metadata,
    Column("source_app_id", String, ForeignKey("apps.id"), primary_key=True),
    Column("target_app_id", String, ForeignKey("apps.id"), nullable=True),
    Column("target_app_name", String, primary_key=True),
)

# Links devices to applications installed or dependent on them.
device_app_dependencies = Table(
    "device_app_dependencies",
    Base.metadata,
    Column("device_id", String, ForeignKey("devices.id"), primary_key=True),
    Column("app_id", String, ForeignKey("apps.id"), primary_key=True),
)
