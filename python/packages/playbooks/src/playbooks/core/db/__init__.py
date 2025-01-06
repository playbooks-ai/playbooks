"""Database configuration and session management."""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

# Get database URL from environment variable, default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///playbooks.db")

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
session_factory = sessionmaker(bind=engine)
Database = scoped_session(session_factory)

# Base class for all models
Base = declarative_base()

if os.getenv("ENVIRONMENT", "development") != "production":
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
