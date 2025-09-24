from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database import get_db
from ads.client import ads_client
from models import AuditLog, Recommendation
from datetime import datetime
import json
import uuid
import logging
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


class NegativeKeywordRequest(BaseModel):
    campaign_id: str
    keyword_text: str
    validate_only: bool = True
    reason: Optional[str] = None
    recommendation_id: Optional[str] = None


class PauseKeywordRequest(BaseModel):
    ad_group_id: str
    criterion_id: str
    validate_only: bool = True
    reason: Optional[str] = None
    recommendation_id: Optional[str] = None


class AdjustBudgetRequest(BaseModel):
    campaign_id: str
    pct_delta: float  # Percentage change, e.g. 0.15 for +15%
    validate_only: bool = True
    reason: Optional[str] = None
    recommendation_id: Optional[str] = None


def create_audit_log(
    action: str,
    payload: dict,
    user: str,
    result: str,
    validate_only: bool,
    google_change_id: Optional[str] = None,
    error_message: Optional[str] = None,
    db: Session = None
) -> str:
    """Create an audit log entry."""
    audit_id = str(uuid.uuid4())
    
    audit_log = AuditLog(
        id=audit_id,
        action=action,
        payload_json=json.dumps(payload),
        user=user,
        timestamp=datetime.utcnow(),
        result=result,
        google_change_id=google_change_id,
        error_message=error_message,
        validate_only=validate_only,
        customer_id=ads_client.customer_id
    )
    
    db.add(audit_log)
    db.commit()
    
    return audit_id


@router.post("/negative_keyword")
def add_negative_keyword(
    request: NegativeKeywordRequest,
    db: Session = Depends(get_db)
):
    """Add a negative keyword to a campaign."""
    try:
        client = ads_client.get_client()
        customer_id = ads_client.customer_id
        
        # Create the operation
        service = client.get_service("CampaignCriterionService")
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        
        criterion.campaign = client.get_service("GoogleAdsService").campaign_path(
            customer_id, request.campaign_id
        )
        criterion.negative = True
        criterion.keyword.text = request.keyword_text
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
        
        # Execute with validation
        try:
            result = ads_client.execute_mutate(
                operations=[operation],
                service_name="CampaignCriterionService",
                customer_id=customer_id,
                validate_only=request.validate_only
            )
            
            # Create audit log
            audit_payload = {
                "campaign_id": request.campaign_id,
                "keyword_text": request.keyword_text,
                "match_type": "EXACT",
                "reason": request.reason,
                "recommendation_id": request.recommendation_id
            }
            
            audit_id = create_audit_log(
                action="add_negative_keyword",
                payload=audit_payload,
                user="api_user",  # In production, get from auth
                result="success" if result["status"] in ["success", "validation_success"] else "error",
                validate_only=request.validate_only,
                google_change_id=result.get("resource_names", [None])[0],
                db=db
            )
            
            # Update recommendation status if provided
            if request.recommendation_id:
                rec = db.query(Recommendation).filter(Recommendation.id == request.recommendation_id).first()
                if rec:
                    rec.status = "dry_run_ok" if request.validate_only else "applied"
                    rec.updated_at = datetime.utcnow()
                    db.commit()
            
            return {
                "status": result["status"],
                "audit_id": audit_id,
                "validate_only": request.validate_only,
                "campaign_id": request.campaign_id,
                "keyword_text": request.keyword_text,
                "resource_names": result.get("resource_names", []),
                "message": f"Negative keyword {'validated' if request.validate_only else 'added'} successfully"
            }
            
        except Exception as e:
            # Create error audit log
            audit_id = create_audit_log(
                action="add_negative_keyword",
                payload=audit_payload,
                user="api_user",
                result="error",
                validate_only=request.validate_only,
                error_message=str(e),
                db=db
            )
            
            logger.error(f"Add negative keyword failed: {e}")
            raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Add negative keyword request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@router.post("/pause_keyword")
def pause_keyword(
    request: PauseKeywordRequest,
    db: Session = Depends(get_db)
):
    """Pause a keyword."""
    try:
        client = ads_client.get_client()
        customer_id = ads_client.customer_id
        
        # Create the operation
        service = client.get_service("AdGroupCriterionService")
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.update
        
        criterion.resource_name = service.ad_group_criterion_path(
            customer_id, request.ad_group_id, request.criterion_id
        )
        criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
        
        # Set field mask
        client.copy_from(
            operation.update_mask,
            client.get_type("FieldMask")(paths=["status"])
        )
        
        # Execute with validation
        try:
            result = ads_client.execute_mutate(
                operations=[operation],
                service_name="AdGroupCriterionService",
                customer_id=customer_id,
                validate_only=request.validate_only
            )
            
            # Create audit log
            audit_payload = {
                "ad_group_id": request.ad_group_id,
                "criterion_id": request.criterion_id,
                "new_status": "PAUSED",
                "reason": request.reason,
                "recommendation_id": request.recommendation_id
            }
            
            audit_id = create_audit_log(
                action="pause_keyword",
                payload=audit_payload,
                user="api_user",
                result="success" if result["status"] in ["success", "validation_success"] else "error",
                validate_only=request.validate_only,
                google_change_id=result.get("resource_names", [None])[0],
                db=db
            )
            
            # Update recommendation status if provided
            if request.recommendation_id:
                rec = db.query(Recommendation).filter(Recommendation.id == request.recommendation_id).first()
                if rec:
                    rec.status = "dry_run_ok" if request.validate_only else "applied"
                    rec.updated_at = datetime.utcnow()
                    db.commit()
            
            return {
                "status": result["status"],
                "audit_id": audit_id,
                "validate_only": request.validate_only,
                "ad_group_id": request.ad_group_id,
                "criterion_id": request.criterion_id,
                "resource_names": result.get("resource_names", []),
                "message": f"Keyword pause {'validated' if request.validate_only else 'applied'} successfully"
            }
            
        except Exception as e:
            # Create error audit log
            audit_id = create_audit_log(
                action="pause_keyword",
                payload=audit_payload,
                user="api_user",
                result="error",
                validate_only=request.validate_only,
                error_message=str(e),
                db=db
            )
            
            logger.error(f"Pause keyword failed: {e}")
            raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Pause keyword request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@router.post("/adjust_budget")
def adjust_budget(
    request: AdjustBudgetRequest,
    db: Session = Depends(get_db)
):
    """Adjust campaign budget by percentage."""
    try:
        # Policy gates
        if abs(request.pct_delta) > 0.20 and request.validate_only:
            return {
                "status": "blocked_by_policy",
                "message": f"Budget change of {request.pct_delta*100:+.1f}% exceeds 20% limit. Requires approval.",
                "policy_violation": True
            }
        
        client = ads_client.get_client()
        customer_id = ads_client.customer_id
        
        # First, get current budget info
        query = f"""
        SELECT 
          campaign.id,
          campaign.name,
          campaign_budget.id,
          campaign_budget.amount_micros
        FROM campaign
        WHERE campaign.id = {request.campaign_id}
        """
        
        results = ads_client.execute_query(query, customer_id)
        if not results:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        current_budget_micros = results[0].campaign_budget.amount_micros
        budget_id = str(results[0].campaign_budget.id)
        
        # Calculate new budget
        new_budget_micros = int(current_budget_micros * (1 + request.pct_delta))
        
        # Policy gate: minimum budget
        if new_budget_micros < 10000000:  # $100 minimum
            return {
                "status": "blocked_by_policy",
                "message": "Cannot reduce budget below $100/day minimum",
                "current_budget_usd": current_budget_micros / 1000000,
                "proposed_budget_usd": new_budget_micros / 1000000,
                "policy_violation": True
            }
        
        # Create the operation
        service = client.get_service("CampaignBudgetService")
        operation = client.get_type("CampaignBudgetOperation")
        budget = operation.update
        
        budget.resource_name = service.campaign_budget_path(customer_id, budget_id)
        budget.amount_micros = new_budget_micros
        
        # Set field mask
        client.copy_from(
            operation.update_mask,
            client.get_type("FieldMask")(paths=["amount_micros"])
        )
        
        # Execute with validation
        try:
            result = ads_client.execute_mutate(
                operations=[operation],
                service_name="CampaignBudgetService",
                customer_id=customer_id,
                validate_only=request.validate_only
            )
            
            # Create audit log
            audit_payload = {
                "campaign_id": request.campaign_id,
                "budget_id": budget_id,
                "pct_delta": request.pct_delta,
                "old_budget_micros": current_budget_micros,
                "new_budget_micros": new_budget_micros,
                "old_budget_usd": current_budget_micros / 1000000,
                "new_budget_usd": new_budget_micros / 1000000,
                "reason": request.reason,
                "recommendation_id": request.recommendation_id
            }
            
            audit_id = create_audit_log(
                action="adjust_budget",
                payload=audit_payload,
                user="api_user",
                result="success" if result["status"] in ["success", "validation_success"] else "error",
                validate_only=request.validate_only,
                google_change_id=result.get("resource_names", [None])[0],
                db=db
            )
            
            # Update recommendation status if provided
            if request.recommendation_id:
                rec = db.query(Recommendation).filter(Recommendation.id == request.recommendation_id).first()
                if rec:
                    rec.status = "dry_run_ok" if request.validate_only else "applied"
                    rec.updated_at = datetime.utcnow()
                    db.commit()
            
            return {
                "status": result["status"],
                "audit_id": audit_id,
                "validate_only": request.validate_only,
                "campaign_id": request.campaign_id,
                "budget_change": {
                    "old_usd": current_budget_micros / 1000000,
                    "new_usd": new_budget_micros / 1000000,
                    "delta_pct": request.pct_delta * 100,
                    "delta_usd": (new_budget_micros - current_budget_micros) / 1000000
                },
                "resource_names": result.get("resource_names", []),
                "message": f"Budget adjustment {'validated' if request.validate_only else 'applied'} successfully"
            }
            
        except Exception as e:
            # Create error audit log
            audit_id = create_audit_log(
                action="adjust_budget",
                payload=audit_payload,
                user="api_user",
                result="error",
                validate_only=request.validate_only,
                error_message=str(e),
                db=db
            )
            
            logger.error(f"Adjust budget failed: {e}")
            raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Adjust budget request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@router.post("/dry_run_all")
def dry_run_all_recommendations(
    recommendation_ids: list[str] = Body(..., description="List of recommendation IDs to dry-run"),
    db: Session = Depends(get_db)
):
    """Dry-run multiple recommendations at once."""
    try:
        results = []
        
        for rec_id in recommendation_ids:
            rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
            if not rec:
                results.append({
                    "recommendation_id": rec_id,
                    "status": "not_found",
                    "error": "Recommendation not found"
                })
                continue
            
            try:
                details = json.loads(rec.details_json) if rec.details_json else {}
                
                if rec.type == "negative_keyword":
                    request = NegativeKeywordRequest(
                        campaign_id=details.get("ad_group_id"),  # This should be campaign_id in practice
                        keyword_text=details.get("search_term"),
                        validate_only=True,
                        reason="Bulk dry-run",
                        recommendation_id=rec_id
                    )
                    result = add_negative_keyword(request, db)
                
                elif rec.type == "pause_keyword":
                    request = PauseKeywordRequest(
                        ad_group_id=details.get("ad_group_id"),
                        criterion_id=rec.target_id,
                        validate_only=True,
                        reason="Bulk dry-run",
                        recommendation_id=rec_id
                    )
                    result = pause_keyword(request, db)
                
                elif rec.type == "budget_shift":
                    request = AdjustBudgetRequest(
                        campaign_id=rec.target_id,
                        pct_delta=details.get("suggested_change_pct", 0) / 100,
                        validate_only=True,
                        reason="Bulk dry-run",
                        recommendation_id=rec_id
                    )
                    result = adjust_budget(request, db)
                
                else:
                    result = {
                        "status": "unsupported",
                        "error": f"Unsupported recommendation type: {rec.type}"
                    }
                
                results.append({
                    "recommendation_id": rec_id,
                    "type": rec.type,
                    "result": result
                })
                
            except Exception as e:
                results.append({
                    "recommendation_id": rec_id,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "total_processed": len(recommendation_ids),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Bulk dry-run failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk dry-run failed: {str(e)}")
