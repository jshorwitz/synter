from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from ads.client import ads_client
from models import Campaign, AdGroup, Keyword, SearchTerm, DailyMetric
from datetime import datetime, date, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)
router = APIRouter()


def create_composite_id(date_str: str, level: str, ref_id: str) -> str:
    """Create a composite ID for daily metrics."""
    return f"{date_str}_{level}_{ref_id}"


def create_search_term_id(term: str, ad_group_id: str) -> str:
    """Create a unique ID for search terms."""
    content = f"{term}_{ad_group_id}"
    return hashlib.md5(content.encode()).hexdigest()


@router.get("/keywords")
def sync_keywords(
    days: int = Query(default=90, description="Number of days to sync"),
    db: Session = Depends(get_db)
):
    """Sync keywords and their metrics from Google Ads."""
    try:
        customer_id = ads_client.customer_id
        
        # GAQL query for keywords with metrics
        query = f"""
        SELECT
          customer.id,
          campaign.id, campaign.name, campaign.status,
          ad_group.id, ad_group.name, ad_group.status,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.status,
          ad_group_criterion.cpc_bid_micros,
          metrics.impressions, metrics.clicks, metrics.cost_micros,
          metrics.conversions, metrics.conversions_value
        FROM keyword_view
        WHERE segments.date DURING LAST_{days}_DAYS
        """
        
        results = ads_client.execute_query(query, customer_id)
        
        campaigns_synced = set()
        ad_groups_synced = set()
        keywords_synced = 0
        metrics_synced = 0
        
        for row in results:
            # Sync campaign
            campaign_id = str(row.campaign.id)
            if campaign_id not in campaigns_synced:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if not campaign:
                    campaign = Campaign(
                        id=campaign_id,
                        name=row.campaign.name,
                        status=row.campaign.status.name,
                        daily_budget_micros=getattr(row.campaign, 'campaign_budget', {}).get('amount_micros', 0)
                    )
                    db.add(campaign)
                campaigns_synced.add(campaign_id)
            
            # Sync ad group
            ad_group_id = str(row.ad_group.id)
            if ad_group_id not in ad_groups_synced:
                ad_group = db.query(AdGroup).filter(AdGroup.id == ad_group_id).first()
                if not ad_group:
                    ad_group = AdGroup(
                        id=ad_group_id,
                        campaign_id=campaign_id,
                        name=row.ad_group.name,
                        status=row.ad_group.status.name
                    )
                    db.add(ad_group)
                ad_groups_synced.add(ad_group_id)
            
            # Sync keyword
            keyword_id = str(row.ad_group_criterion.criterion_id)
            keyword = db.query(Keyword).filter(Keyword.id == keyword_id).first()
            if not keyword:
                keyword = Keyword(
                    id=keyword_id,
                    ad_group_id=ad_group_id,
                    text=row.ad_group_criterion.keyword.text,
                    match_type=row.ad_group_criterion.keyword.match_type.name,
                    status=row.ad_group_criterion.status.name,
                    cpc_bid_micros=getattr(row.ad_group_criterion, 'cpc_bid_micros', None)
                )
                db.add(keyword)
                keywords_synced += 1
            
            # For aggregated metrics, we'll create one record per keyword
            # In a real implementation, you might want daily breakdowns
            metric_id = create_composite_id("aggregated", "keyword", keyword_id)
            metric = db.query(DailyMetric).filter(DailyMetric.id == metric_id).first()
            if not metric:
                metric = DailyMetric(
                    id=metric_id,
                    date=date.today() - timedelta(days=1),  # Yesterday as representative
                    level="keyword",
                    ref_id=keyword_id,
                    impressions=row.metrics.impressions,
                    clicks=row.metrics.clicks,
                    cost_micros=row.metrics.cost_micros,
                    conversions=row.metrics.conversions,
                    conversions_value=row.metrics.conversions_value,
                    ctr=row.metrics.clicks / max(row.metrics.impressions, 1) * 100,
                    cpc_micros=row.metrics.cost_micros // max(row.metrics.clicks, 1),
                    conversion_rate=row.metrics.conversions / max(row.metrics.clicks, 1) * 100
                )
                db.add(metric)
                metrics_synced += 1
        
        db.commit()
        
        return {
            "status": "success",
            "campaigns_synced": len(campaigns_synced),
            "ad_groups_synced": len(ad_groups_synced),
            "keywords_synced": keywords_synced,
            "metrics_synced": metrics_synced,
            "total_rows_processed": len(results)
        }
        
    except Exception as e:
        logger.error(f"Keyword sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/search_terms")
def sync_search_terms(
    days: int = Query(default=30, description="Number of days to sync"),
    db: Session = Depends(get_db)
):
    """Sync search terms from Google Ads."""
    try:
        customer_id = ads_client.customer_id
        
        # GAQL query for search terms
        query = f"""
        SELECT
          search_term_view.search_term,
          ad_group.id, ad_group.name,
          ad_group_criterion.keyword.text,
          segments.date,
          metrics.impressions, metrics.clicks, metrics.cost_micros,
          metrics.conversions, metrics.conversions_value
        FROM search_term_view
        WHERE segments.date DURING LAST_{days}_DAYS
        """
        
        results = ads_client.execute_query(query, customer_id)
        
        search_terms_synced = 0
        
        for row in results:
            ad_group_id = str(row.ad_group.id)
            search_term = row.search_term_view.search_term
            search_term_id = create_search_term_id(search_term, ad_group_id)
            
            # Check if search term already exists
            existing_term = db.query(SearchTerm).filter(SearchTerm.id == search_term_id).first()
            
            if not existing_term:
                search_term_obj = SearchTerm(
                    id=search_term_id,
                    ad_group_id=ad_group_id,
                    text=search_term,
                    matched_keyword_text=getattr(row.ad_group_criterion.keyword, 'text', None),
                    last_seen=row.segments.date
                )
                db.add(search_term_obj)
                search_terms_synced += 1
            else:
                # Update last seen date
                existing_term.last_seen = max(existing_term.last_seen, row.segments.date)
        
        db.commit()
        
        return {
            "status": "success",
            "search_terms_synced": search_terms_synced,
            "total_rows_processed": len(results)
        }
        
    except Exception as e:
        logger.error(f"Search terms sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/campaigns")
def sync_campaigns(
    days: int = Query(default=30, description="Number of days for budget data"),
    db: Session = Depends(get_db)
):
    """Sync campaign budgets and pacing data."""
    try:
        customer_id = ads_client.customer_id
        
        # GAQL query for campaigns with budget data
        query = f"""
        SELECT
          campaign.id, campaign.name, campaign.status,
          campaign_budget.amount_micros, campaign_budget.status,
          segments.date, metrics.cost_micros
        FROM campaign
        WHERE segments.date DURING LAST_{days}_DAYS
        """
        
        results = ads_client.execute_query(query, customer_id)
        
        campaigns_updated = set()
        daily_metrics_added = 0
        
        for row in results:
            campaign_id = str(row.campaign.id)
            
            # Update campaign budget info
            if campaign_id not in campaigns_updated:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if campaign:
                    campaign.daily_budget_micros = row.campaign_budget.amount_micros
                    campaign.status = row.campaign.status.name
                    campaigns_updated.add(campaign_id)
            
            # Add daily metric
            metric_id = create_composite_id(str(row.segments.date), "campaign", campaign_id)
            existing_metric = db.query(DailyMetric).filter(DailyMetric.id == metric_id).first()
            
            if not existing_metric:
                daily_metric = DailyMetric(
                    id=metric_id,
                    date=row.segments.date,
                    level="campaign",
                    ref_id=campaign_id,
                    cost_micros=row.metrics.cost_micros
                )
                db.add(daily_metric)
                daily_metrics_added += 1
        
        db.commit()
        
        return {
            "status": "success",
            "campaigns_updated": len(campaigns_updated),
            "daily_metrics_added": daily_metrics_added,
            "total_rows_processed": len(results)
        }
        
    except Exception as e:
        logger.error(f"Campaign sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/full_sync")
def full_sync(db: Session = Depends(get_db)):
    """Perform a full sync of all data."""
    try:
        # Sync in order: campaigns -> keywords -> search terms
        campaign_result = sync_campaigns(30, db)
        keyword_result = sync_keywords(90, db)
        search_term_result = sync_search_terms(30, db)
        
        return {
            "status": "success",
            "campaigns": campaign_result,
            "keywords": keyword_result,
            "search_terms": search_term_result
        }
        
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Full sync failed: {str(e)}")
