# File: database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Hỗ trợ cả biến môi trường DATABASE_URL (Docker) và fallback cổng 3307 (Local)
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:rootpassword@127.0.0.1:3307/ecommerce_db"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)