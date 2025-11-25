"""
Database models and connection setup for user accounts and saved charts.
Uses SQLite with SQLAlchemy for simplicity and portability.
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database URL - use SQLite for simplicity (can switch to PostgreSQL for production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./synthesis_astrology.db")

# For SQLite, we need to handle the connection args differently
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship to saved charts
    charts = relationship("SavedChart", back_populates="owner", cascade="all, delete-orphan")
    
    # Relationship to chat conversations
    conversations = relationship("ChatConversation", back_populates="owner", cascade="all, delete-orphan")


class SavedChart(Base):
    """Saved birth chart model."""
    __tablename__ = "saved_charts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Chart identification
    chart_name = Column(String(255), nullable=False)  # Name of the person the chart is for
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Birth data
    birth_year = Column(Integer, nullable=False)
    birth_month = Column(Integer, nullable=False)
    birth_day = Column(Integer, nullable=False)
    birth_hour = Column(Integer, nullable=False)
    birth_minute = Column(Integer, nullable=False)
    birth_location = Column(String(500), nullable=False)
    unknown_time = Column(Boolean, default=False)
    
    # Calculated chart data (stored as JSON string)
    chart_data_json = Column(Text, nullable=True)
    
    # AI reading (if generated)
    ai_reading = Column(Text, nullable=True)
    
    # Relationship
    owner = relationship("User", back_populates="charts")
    
    # Relationship to chat conversations
    conversations = relationship("ChatConversation", back_populates="chart", cascade="all, delete-orphan")


class ChatConversation(Base):
    """Chat conversation about a specific chart."""
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chart_id = Column(Integer, ForeignKey("saved_charts.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Conversation title (auto-generated or user-defined)
    title = Column(String(255), default="New Conversation")
    
    # Relationship
    owner = relationship("User", back_populates="conversations")
    chart = relationship("SavedChart", back_populates="conversations")
    
    # Messages in this conversation
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Individual message in a chat conversation."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False)
    
    # Message content
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("ChatConversation", back_populates="messages")


def init_db():
    """Initialize the database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

