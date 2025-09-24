"""
Simple database setup for testing without PostgreSQL
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from datetime import datetime
import os

# Create SQLite database for testing
DATABASE_URL = "sqlite:///./synter_test.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Simplified models for testing
class Website(Base):
    __tablename__ = "websites"

    id = Column(String(50), primary_key=True)
    url = Column(String(500), nullable=False, unique=True)
    title = Column(String(500))
    description = Column(Text)
    industry = Column(String(100))
    business_model = Column(String(50))
    
    # Content analysis
    content_summary = Column(Text)
    key_topics = Column(Text)  # JSON array
    value_propositions = Column(Text)  # JSON array
    
    # Technical analysis
    technologies = Column(Text)  # JSON from BuiltWith
    tracking_pixels = Column(Text)  # JSON of detected pixels
    
    # Status
    analysis_status = Column(String(20), default="pending")
    last_analyzed = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(50), primary_key=True)
    report_type = Column(String(50), nullable=False)
    website_id = Column(String(50), ForeignKey("websites.id"), nullable=True)
    
    # Input data hash for deduplication  
    input_hash = Column(String(64), nullable=False)
    
    # Report content
    title = Column(String(200), nullable=False)
    summary = Column(Text)
    data_json = Column(Text)  # JSON with report data
    
    # Scoring and confidence
    overall_score = Column(Integer)  # 0-100 overall score
    confidence = Column(String(10))  # HIGH, MEDIUM, LOW
    
    # Report output
    html_content = Column(Text)  # Rendered HTML report
    pdf_path = Column(String(500))  # Path to generated PDF
    
    # Status and metadata
    status = Column(String(20), default="generating")  # generating, ready, failed
    generation_time_ms = Column(Integer)
    
    # Billing
    credit_cost = Column(Integer, default=1)  # Number of credits used
    user_id = Column(String(50))  # User who requested the report
    workspace_id = Column(String(50))  # Workspace for billing
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AdAccount(Base):
    __tablename__ = "ad_accounts"

    id = Column(String(50), primary_key=True)
    platform = Column(String(20), nullable=False)  # google, meta, reddit, twitter
    account_id = Column(String(100), nullable=False)  # Platform-specific account ID
    account_name = Column(String(200))
    
    # Connection details
    user_id = Column(String(50), nullable=False)
    workspace_id = Column(String(50), nullable=False)
    
    # Auth tokens (encrypted in production)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    
    # Account metadata
    currency = Column(String(3), default="USD")
    timezone = Column(String(50))
    account_status = Column(String(20))
    
    # Connection status
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime)
    sync_status = Column(String(20), default="pending")  # pending, syncing, success, error
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SpendData(Base):
    __tablename__ = "spend_data"

    id = Column(String(50), primary_key=True)
    ad_account_id = Column(String(50), ForeignKey("ad_accounts.id"), nullable=False)
    
    # Date and granularity
    date = Column(Date, nullable=False)
    granularity = Column(String(10), default="daily")  # daily, weekly, monthly
    
    # Campaign/Ad Group breakdown
    campaign_id = Column(String(100))
    campaign_name = Column(String(200))
    ad_group_id = Column(String(100))
    ad_group_name = Column(String(200))
    
    # Spend metrics
    spend = Column(Float, default=0.0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Float, default=0.0)
    
    # Calculated metrics
    cpm = Column(Float)  # Cost per mille
    cpc = Column(Float)  # Cost per click
    ctr = Column(Float)  # Click-through rate
    conversion_rate = Column(Float)
    cpa = Column(Float)  # Cost per acquisition
    
    # Currency
    currency = Column(String(3), default="USD")
    
    # Sync metadata
    synced_at = Column(DateTime, default=func.now())
    
    # Relationships
    ad_account = relationship("AdAccount")


class AccountConnection(Base):
    __tablename__ = "account_connections"

    id = Column(String(50), primary_key=True)
    website_id = Column(String(50), ForeignKey("websites.id"), nullable=False)
    ad_account_id = Column(String(50), ForeignKey("ad_accounts.id"), nullable=False)
    
    # Connection metadata
    connected_by = Column(String(50))  # User who made the connection
    connection_type = Column(String(20), default="manual")  # manual, auto_detected
    confidence = Column(Float, default=1.0)  # How confident we are this account belongs to this website
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    website = relationship("Website")
    ad_account = relationship("AdAccount")


# Billing Models

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    
    # Billing information
    stripe_customer_id = Column(String(100))
    stripe_subscription_id = Column(String(100))
    
    # Plan and entitlements
    plan = Column(String(20), default="FREE")  # FREE, PRO, ENTERPRISE
    report_credits = Column(Integer, default=3)  # Resets monthly
    credits_reset_date = Column(Date)
    can_publish = Column(Boolean, default=False)  # Can deploy campaigns
    
    # Usage tracking
    reports_generated_this_month = Column(Integer, default=0)
    last_report_generated = Column(DateTime)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    users = relationship("WorkspaceUser", back_populates="workspace")
    billing_events = relationship("BillingEvent", back_populates="workspace")


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    email = Column(String(320), unique=True, nullable=False)
    name = Column(String(200))
    
    # Auth
    password_hash = Column(String(255))  # For basic auth
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    workspaces = relationship("WorkspaceUser", back_populates="user")


class WorkspaceUser(Base):
    __tablename__ = "workspace_users"

    id = Column(String(50), primary_key=True)
    workspace_id = Column(String(50), ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="EDITOR")  # VIEWER, EDITOR, ADMIN
    
    created_at = Column(DateTime, default=func.now())

    # Relationships
    workspace = relationship("Workspace", back_populates="users")
    user = relationship("User", back_populates="workspaces")


class BillingEvent(Base):
    __tablename__ = "billing_events"

    id = Column(String(50), primary_key=True)
    workspace_id = Column(String(50), ForeignKey("workspaces.id"), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # subscription_created, credits_purchased, report_generated
    stripe_event_id = Column(String(100))  # Stripe webhook event ID
    
    # Billing data
    amount = Column(Integer)  # Amount in cents
    currency = Column(String(3), default="USD")
    credits_added = Column(Integer, default=0)
    credits_consumed = Column(Integer, default=0)
    
    # Product information
    stripe_price_id = Column(String(100))
    product_name = Column(String(200))
    plan_changed_to = Column(String(20))  # If plan change
    
    # Metadata
    metadata_json = Column(Text)  # Additional event data
    
    # Status
    processed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.now())

    # Relationships
    workspace = relationship("Workspace", back_populates="billing_events")


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    credits = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)  # Price in cents
    stripe_price_id = Column(String(100), nullable=False)
    
    # Marketing
    description = Column(Text)
    is_popular = Column(Boolean, default=False)
    discount_percent = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(50), primary_key=True)
    workspace_id = Column(String(50), ForeignKey("workspaces.id"), nullable=False)
    
    # Stripe information
    stripe_subscription_id = Column(String(100), unique=True, nullable=False)
    stripe_customer_id = Column(String(100), nullable=False)
    stripe_price_id = Column(String(100), nullable=False)
    
    # Subscription details
    plan_name = Column(String(50), nullable=False)  # PRO, ENTERPRISE
    status = Column(String(20), nullable=False)  # active, past_due, canceled, etc.
    
    # Billing cycle
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    
    # Entitlements
    monthly_credits = Column(Integer, default=0)  # Credits included in plan
    can_publish = Column(Boolean, default=False)
    max_users = Column(Integer, default=1)
    
    # Status
    is_active = Column(Boolean, default=True)
    canceled_at = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    workspace = relationship("Workspace")

def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database."""
    create_tables()

if __name__ == "__main__":
    print("🗄️  Initializing simple database...")
    init_db()
    print("✅ Database ready!")
