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

# Fix for Render: They provide postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# For SQLite, we need to handle the connection args differently
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL with connection pool settings for production
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=300,    # Recycle connections every 5 minutes
    )

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
    is_admin = Column(Boolean, default=False)  # Admin flag for developer access
    credits = Column(Integer, default=3)  # Free credits for new users
    
    # Stripe subscription fields
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    subscription_status = Column(String(50), default="inactive")  # inactive, active, past_due, canceled, trialing
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    
    # Reading purchase and free month tracking
    has_purchased_reading = Column(Boolean, default=False)  # Has user purchased a $28 full reading?
    reading_purchase_date = Column(DateTime, nullable=True)  # When did they purchase the reading?
    free_chat_month_end_date = Column(DateTime, nullable=True)  # End date of free month of chats after reading purchase
    
    # Relationship to saved charts
    charts = relationship("SavedChart", back_populates="owner", cascade="all, delete-orphan")
    
    # Relationship to chat conversations
    conversations = relationship("ChatConversation", back_populates="owner", cascade="all, delete-orphan")
    
    # Relationship to credit transactions
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")


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
    
    # Token/cost tracking for billing
    tokens_used = Column(Integer, nullable=True)
    credits_charged = Column(Integer, default=1)
    
    # Relationship
    conversation = relationship("ChatConversation", back_populates="messages")


class CreditTransaction(Base):
    """Credit purchase and usage tracking."""
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Transaction details
    amount = Column(Integer, nullable=False)  # positive = purchase, negative = usage
    transaction_type = Column(String(50), nullable=False)  # 'purchase', 'reading', 'chat', 'bonus', 'refund'
    stripe_payment_id = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="credit_transactions")


class SubscriptionPayment(Base):
    """Subscription payment history tracking."""
    __tablename__ = "subscription_payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Payment details
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    stripe_invoice_id = Column(String(255), nullable=True, index=True)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(10), default="usd")
    status = Column(String(50), nullable=False)  # succeeded, pending, failed, refunded
    payment_date = Column(DateTime, nullable=False)
    billing_period_start = Column(DateTime, nullable=True)
    billing_period_end = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User")


class AdminBypassLog(Base):
    """Log admin secret key usage for auditing."""
    __tablename__ = "admin_bypass_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=True)  # User email if available
    endpoint = Column(String(255), nullable=False)  # API endpoint accessed
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text, nullable=True)  # Additional context


class FamousPerson(Base):
    """Famous person with birth chart data for similarity matching."""
    __tablename__ = "famous_people"

    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    name = Column(String(255), nullable=False, unique=True, index=True)
    wikipedia_url = Column(String(500), nullable=False)
    occupation = Column(String(255), nullable=True)
    
    # Birth data
    birth_year = Column(Integer, nullable=False)
    birth_month = Column(Integer, nullable=False)
    birth_day = Column(Integer, nullable=False)
    birth_hour = Column(Integer, nullable=True)  # May be unknown
    birth_minute = Column(Integer, nullable=True)  # May be unknown
    birth_location = Column(String(500), nullable=False)
    unknown_time = Column(Boolean, default=True)  # Most famous people won't have exact birth times
    
    # Chart data (stored as JSON for quick comparison)
    chart_data_json = Column(Text, nullable=True)  # Key chart elements for comparison
    
    # Key chart elements for matching (stored separately for fast queries)
    sun_sign_sidereal = Column(String(50), nullable=True, index=True)
    sun_sign_tropical = Column(String(50), nullable=True, index=True)
    moon_sign_sidereal = Column(String(50), nullable=True, index=True)
    moon_sign_tropical = Column(String(50), nullable=True, index=True)
    # Rising signs removed - query from JSON instead to reduce database size
    
    # Additional planetary placements (stored as JSON for all planets including outer planets)
    # Format: {"sidereal": {"Mercury": {"sign": "Gemini", "degree": 15.5, "retrograde": false}, ...}, "tropical": {...}}
    planetary_placements_json = Column(Text, nullable=True)
    
    # Top 3 aspects (both sidereal and tropical) - stored as JSON
    # Format: {"sidereal": [{"p1": "Sun", "p2": "Moon", "type": "Conjunction", "orb": "2.5°", "strength": "4.5"}], "tropical": [...]}
    top_aspects_json = Column(Text, nullable=True)
    
    # Numerology
    life_path_number = Column(String(10), nullable=True, index=True)
    day_number = Column(String(10), nullable=True)
    
    # Chinese Zodiac
    chinese_zodiac_animal = Column(String(50), nullable=True, index=True)
    
    # Metadata
    page_views = Column(Integer, nullable=True, index=True)  # Wikipedia page views (for ranking)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

