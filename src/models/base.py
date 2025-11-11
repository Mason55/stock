# src/models/base.py - Shared SQLAlchemy declarative base
from sqlalchemy.orm import declarative_base

# Single metadata registry for all ORM models so that create_all/metadata
# operations cover every table defined under src.models.*
Base = declarative_base()

__all__ = ["Base"]
