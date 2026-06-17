from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "postgresql+psycopg://postgres:123456@localhost/canteen_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    diet_type = Column(String, default="normal") 

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    calories = Column(Integer)
    weight = Column(Integer)
    category = Column(String)
    allowed_diets = Column(String, default="normal,diabetic,allergy")  

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="created")  # created, accepted, cooking, ready, delivered, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    qr_token = Column(String, unique=True, index=True)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Таблицы созданы")