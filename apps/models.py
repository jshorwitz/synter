from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date

Base = declarative_base()


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    daily_budget_micros = Column(Integer)
    currency_code = Column(String(3), default="USD")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    ad_groups = relationship("AdGroup", back_populates="campaign")
    daily_metrics = relationship("DailyMetric", back_populates="campaign")


class AdGroup(Base):
    __tablename__ = "ad_groups"

    id = Column(String(20), primary_key=True)
    campaign_id = Column(String(20), ForeignKey("campaigns.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="ad_groups")
    keywords = relationship("Keyword", back_populates="ad_group")
    search_terms = relationship("SearchTerm", back_populates="ad_group")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(String(20), primary_key=True)
    ad_group_id = Column(String(20), ForeignKey("ad_groups.id"), nullable=False)
    text = Column(String(500), nullable=False)
    match_type = Column(String(20), nullable=False)  # EXACT, PHRASE, BROAD
    status = Column(String(50), nullable=False)
    cpc_bid_micros = Column(Integer)
    
    # ICP Scoring fields
    icp_score = Column(Integer)  # 0-100
    icp_rationale = Column(Text)
    icp_confidence = Column(Float)  # 0-1
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    ad_group = relationship("AdGroup", back_populates="keywords")


class SearchTerm(Base):
    __tablename__ = "search_terms"

    id = Column(String(50), primary_key=True)  # hash of term + ad_group_id
    ad_group_id = Column(String(20), ForeignKey("ad_groups.id"), nullable=False)
    text = Column(String(500), nullable=False)
    matched_keyword_text = Column(String(500))
    last_seen = Column(Date, nullable=False)
    
    # ICP Scoring fields
    icp_score = Column(Integer)  # 0-100
    icp_rationale = Column(Text)
    icp_confidence = Column(Float)  # 0-1
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    ad_group = relationship("AdGroup", back_populates="search_terms")


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(String(100), primary_key=True)  # date_level_ref_id composite key
    date = Column(Date, nullable=False)
    level = Column(String(20), nullable=False)  # campaign, ad_group, keyword, search_term
    ref_id = Column(String(20), nullable=False)  # ID of the entity being measured
    
    # Core metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost_micros = Column(Integer, default=0)
    conversions = Column(Float, default=0.0)
    conversions_value = Column(Float, default=0.0)
    
    # Calculated fields
    ctr = Column(Float)  # Click-through rate
    cpc_micros = Column(Integer)  # Cost per click in micros
    conversion_rate = Column(Float)
    
    created_at = Column(DateTime, default=func.now())

    # Relationships
    campaign = relationship("Campaign", back_populates="daily_metrics", 
                          foreign_keys=[ref_id], primaryjoin="and_(DailyMetric.ref_id==Campaign.id, DailyMetric.level=='campaign')")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String(50), primary_key=True)
    type = Column(String(50), nullable=False)  # negative_keyword, pause_keyword, budget_shift
    target_level = Column(String(20), nullable=False)  # campaign, ad_group, keyword
    target_id = Column(String(20), nullable=False)
    
    # Recommendation details
    details_json = Column(Text)  # JSON string with specifics
    projected_impact = Column(Float)  # Expected savings/gains
    risk = Column(Float)  # Risk score 0-1
    priority = Column(String(10), default="medium")  # low, medium, high
    
    # Status tracking
    status = Column(String(20), default="proposed")  # proposed, dry_run_ok, applied, dismissed
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(50), primary_key=True)
    action = Column(String(100), nullable=False)
    payload_json = Column(Text)
    user = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    result = Column(String(20))  # success, error, dry_run
    google_change_id = Column(String(100))  # Google Ads resource name/ID
    error_message = Column(Text)
    
    # Context
    validate_only = Column(Boolean, default=True)
    customer_id = Column(String(20))


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(20), unique=True, nullable=False)
    refresh_token = Column(String(500), nullable=False)
    access_token = Column(String(500))
    token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
