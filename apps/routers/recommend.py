from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from database import get_db
from models import Recommendation, Keyword, SearchTerm, DailyMetric, Campaign, AdGroup
from datetime import datetime, date, timedelta
import json
import uuid
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter()


def generate_recommendation_id() -> str:
    """Generate a unique recommendation ID."""
    return str(uuid.uuid4())


def calculate_percentile(values: List[float], percentile: int) -> float:
    """Calculate percentile of a list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    if index.is_integer():
        return sorted_values[int(index)]
    else:
        lower = sorted_values[int(index)]
        upper = sorted_values[int(index) + 1]
        return lower + (upper - lower) * (index - int(index))


@router.get("/")
def get_recommendations(
    types: str = Query(default="neg,pause,budget", description="Comma-separated list: neg,pause,budget"),
    limit: int = Query(default=50, description="Maximum recommendations to return"),
    status: str = Query(default="proposed", description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get current recommendations."""
    try:
        type_list = [t.strip() for t in types.split(",")]
        type_mapping = {
            "neg": "negative_keyword",
            "pause": "pause_keyword", 
            "budget": "budget_shift"
        }
        
        filtered_types = [type_mapping.get(t, t) for t in type_list if t in type_mapping or t in type_mapping.values()]
        
        query = db.query(Recommendation)
        
        if filtered_types:
            query = query.filter(Recommendation.type.in_(filtered_types))
        
        if status != "all":
            query = query.filter(Recommendation.status == status)
        
        recommendations = query.order_by(Recommendation.priority.desc(), Recommendation.projected_impact.desc()).limit(limit).all()
        
        result = []
        for rec in recommendations:
            rec_dict = {
                "id": rec.id,
                "type": rec.type,
                "target_level": rec.target_level,
                "target_id": rec.target_id,
                "details": json.loads(rec.details_json) if rec.details_json else {},
                "projected_impact": rec.projected_impact,
                "risk": rec.risk,
                "priority": rec.priority,
                "status": rec.status,
                "created_at": rec.created_at.isoformat(),
                "updated_at": rec.updated_at.isoformat()
            }
            result.append(rec_dict)
        
        return {
            "recommendations": result,
            "total": len(result),
            "filters_applied": {
                "types": filtered_types,
                "status": status,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Getting recommendations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.post("/generate")
def generate_recommendations(
    types: str = Query(default="neg,pause,budget", description="Comma-separated list: neg,pause,budget"),
    force_refresh: bool = Query(default=False, description="Clear existing and regenerate"),
    db: Session = Depends(get_db)
):
    """Generate new recommendations based on current data."""
    try:
        type_list = [t.strip() for t in types.split(",")]
        
        if force_refresh:
            # Clear existing proposed recommendations
            db.query(Recommendation).filter(Recommendation.status == "proposed").delete()
            db.commit()
        
        recommendations_created = 0
        
        # 1. NEGATIVE KEYWORD recommendations
        if "neg" in type_list:
            negative_recs = _generate_negative_keyword_recommendations(db)
            recommendations_created += len(negative_recs)
            for rec in negative_recs:
                db.add(rec)
        
        # 2. PAUSE KEYWORD recommendations  
        if "pause" in type_list:
            pause_recs = _generate_pause_keyword_recommendations(db)
            recommendations_created += len(pause_recs)
            for rec in pause_recs:
                db.add(rec)
        
        # 3. BUDGET SHIFT recommendations
        if "budget" in type_list:
            budget_recs = _generate_budget_shift_recommendations(db)
            recommendations_created += len(budget_recs)
            for rec in budget_recs:
                db.add(rec)
        
        db.commit()
        
        return {
            "status": "success",
            "recommendations_created": recommendations_created,
            "types_processed": type_list,
            "force_refresh": force_refresh
        }
        
    except Exception as e:
        logger.error(f"Generating recommendations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


def _generate_negative_keyword_recommendations(db: Session) -> List[Recommendation]:
    """Generate negative keyword recommendations based on search terms."""
    recommendations = []
    
    # Find search terms with low ICP score, high spend, no conversions
    cutoff_date = date.today() - timedelta(days=7)
    
    # This is a simplified query - in reality you'd need to aggregate metrics by search term
    problematic_terms = db.query(SearchTerm).filter(
        and_(
            SearchTerm.icp_score < 40,
            SearchTerm.icp_score.isnot(None),
            SearchTerm.last_seen >= cutoff_date
        )
    ).limit(20).all()  # Limit to avoid too many recommendations
    
    for term in problematic_terms:
        # In a real implementation, you'd calculate actual spend for this term
        # For MVP, we'll simulate based on ICP score
        estimated_spend = max(100, (40 - term.icp_score) * 20)  # Lower score = higher simulated spend
        
        if estimated_spend >= 300:  # Meet the spend threshold
            details = {
                "search_term": term.text,
                "icp_score": term.icp_score,
                "rationale": term.icp_rationale,
                "estimated_spend_7d": estimated_spend,
                "ad_group_id": term.ad_group_id,
                "match_type": "EXACT",
                "impact_explanation": f"Prevent spend on low-fit term (ICP: {term.icp_score})"
            }
            
            recommendation = Recommendation(
                id=generate_recommendation_id(),
                type="negative_keyword",
                target_level="campaign",
                target_id=term.ad_group_id,  # We'd need to get campaign_id in practice
                details_json=json.dumps(details),
                projected_impact=estimated_spend * 0.8,  # Assume 80% of spend would be saved
                risk=1 - (term.icp_confidence or 0.5),
                priority="high" if term.icp_score < 20 else "medium"
            )
            recommendations.append(recommendation)
    
    return recommendations


def _generate_pause_keyword_recommendations(db: Session) -> List[Recommendation]:
    """Generate pause keyword recommendations."""
    recommendations = []
    
    # Get account-wide conversion rate percentiles
    all_metrics = db.query(DailyMetric).filter(
        and_(
            DailyMetric.level == "keyword",
            DailyMetric.conversions > 0,
            DailyMetric.clicks > 0
        )
    ).all()
    
    conversion_rates = [
        (metric.conversions / metric.clicks * 100) 
        for metric in all_metrics 
        if metric.clicks > 0
    ]
    
    if not conversion_rates:
        return recommendations  # No data to work with
    
    p25_conv_rate = calculate_percentile(conversion_rates, 25)
    
    # Find keywords with poor performance
    poor_keywords = db.query(Keyword).filter(
        and_(
            Keyword.icp_score < 50,
            Keyword.icp_score.isnot(None)
        )
    ).limit(15).all()  # Limit for MVP
    
    for keyword in poor_keywords:
        # Get metrics for this keyword
        metrics = db.query(DailyMetric).filter(
            and_(
                DailyMetric.level == "keyword",
                DailyMetric.ref_id == keyword.id,
                DailyMetric.date >= date.today() - timedelta(days=14)
            )
        ).first()
        
        if not metrics:
            continue
        
        # Simulate spend check and performance
        estimated_spend = max(200, (50 - keyword.icp_score) * 25)
        conv_rate = (metrics.conversions / max(metrics.clicks, 1)) * 100
        
        if estimated_spend >= 500 and conv_rate < p25_conv_rate:
            details = {
                "keyword_text": keyword.text,
                "match_type": keyword.match_type,
                "icp_score": keyword.icp_score,
                "estimated_spend_14d": estimated_spend,
                "conversion_rate": conv_rate,
                "account_p25_conv_rate": p25_conv_rate,
                "rationale": f"Low ICP ({keyword.icp_score}) + poor conversion rate ({conv_rate:.2f}% vs {p25_conv_rate:.2f}% p25)"
            }
            
            recommendation = Recommendation(
                id=generate_recommendation_id(),
                type="pause_keyword",
                target_level="keyword",
                target_id=keyword.id,
                details_json=json.dumps(details),
                projected_impact=estimated_spend * 0.7,  # Assume 70% savings
                risk=0.3,  # Moderate risk of losing some good traffic
                priority="high" if keyword.icp_score < 30 else "medium"
            )
            recommendations.append(recommendation)
    
    return recommendations


def _generate_budget_shift_recommendations(db: Session) -> List[Recommendation]:
    """Generate budget shift recommendations."""
    recommendations = []
    
    # Policy gate: check if account has enough conversions
    recent_conversions = db.query(func.sum(DailyMetric.conversions)).filter(
        and_(
            DailyMetric.date >= date.today() - timedelta(days=30),
            DailyMetric.level == "campaign"
        )
    ).scalar() or 0
    
    if recent_conversions < 20:
        logger.info("Skipping budget recommendations: insufficient conversions (<20 in last 30 days)")
        return recommendations
    
    # Find campaigns with different ICP performance
    campaigns = db.query(Campaign).limit(10).all()  # Limit for MVP
    
    for campaign in campaigns:
        # Get average ICP score for this campaign's keywords
        avg_icp = db.query(func.avg(Keyword.icp_score)).filter(
            and_(
                Keyword.ad_group_id.in_(
                    db.query(AdGroup.id).filter(AdGroup.campaign_id == campaign.id)
                ),
                Keyword.icp_score.isnot(None)
            )
        ).scalar()
        
        if not avg_icp:
            continue
        
        # Get campaign metrics
        campaign_metrics = db.query(func.sum(DailyMetric.cost_micros)).filter(
            and_(
                DailyMetric.level == "campaign",
                DailyMetric.ref_id == campaign.id,
                DailyMetric.date >= date.today() - timedelta(days=7)
            )
        ).scalar() or 0
        
        daily_budget = campaign.daily_budget_micros or 0
        
        # Logic: if high-fit campaign is constrained by budget, recommend increase
        # if low-fit campaign is overspending, recommend decrease
        if avg_icp >= 80 and campaign_metrics > daily_budget * 6:  # Spending close to weekly budget
            details = {
                "campaign_name": campaign.name,
                "current_daily_budget_micros": daily_budget,
                "avg_icp_score": float(avg_icp),
                "weekly_spend_micros": int(campaign_metrics),
                "recommendation": "increase",
                "suggested_change_pct": 15,
                "rationale": f"High-fit campaign (ICP: {avg_icp:.1f}) appears budget-constrained"
            }
            
            recommendation = Recommendation(
                id=generate_recommendation_id(),
                type="budget_shift",
                target_level="campaign",
                target_id=campaign.id,
                details_json=json.dumps(details),
                projected_impact=daily_budget * 0.15 * 0.3,  # Assume 30% incremental return
                risk=0.2,  # Low risk for high-fit campaigns
                priority="medium"
            )
            recommendations.append(recommendation)
            
        elif avg_icp < 40 and daily_budget >= 10000000:  # At least $100/day minimum
            details = {
                "campaign_name": campaign.name,
                "current_daily_budget_micros": daily_budget,
                "avg_icp_score": float(avg_icp),
                "recommendation": "decrease",
                "suggested_change_pct": -20,
                "rationale": f"Low-fit campaign (ICP: {avg_icp:.1f}) may be overspending"
            }
            
            recommendation = Recommendation(
                id=generate_recommendation_id(),
                type="budget_shift",
                target_level="campaign",
                target_id=campaign.id,
                details_json=json.dumps(details),
                projected_impact=daily_budget * 0.20 * 0.8,  # Assume 80% of cut is waste
                risk=0.1,  # Low risk to reduce low-fit spend
                priority="low"
            )
            recommendations.append(recommendation)
    
    return recommendations


@router.put("/{recommendation_id}/status")
def update_recommendation_status(
    recommendation_id: str,
    status: str = Query(..., description="New status: proposed, dry_run_ok, applied, dismissed"),
    db: Session = Depends(get_db)
):
    """Update the status of a recommendation."""
    try:
        valid_statuses = ["proposed", "dry_run_ok", "applied", "dismissed"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        recommendation = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        old_status = recommendation.status
        recommendation.status = status
        recommendation.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "success",
            "recommendation_id": recommendation_id,
            "old_status": old_status,
            "new_status": status,
            "updated_at": recommendation.updated_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Updating recommendation status failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status update failed: {str(e)}")


@router.delete("/{recommendation_id}")
def delete_recommendation(
    recommendation_id: str,
    db: Session = Depends(get_db)
):
    """Delete a recommendation."""
    try:
        recommendation = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        db.delete(recommendation)
        db.commit()
        
        return {
            "status": "success",
            "recommendation_id": recommendation_id,
            "message": "Recommendation deleted"
        }
        
    except Exception as e:
        logger.error(f"Deleting recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
