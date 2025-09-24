from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from database import get_db
from pydantic import BaseModel, EmailStr
from services.billing_service import BillingService
from typing import Optional, List
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class CheckoutRequest(BaseModel):
    workspace_id: str
    product_type: str  # "subscription" or "credit_pack"
    product_id: str    # Plan name or credit pack ID
    success_url: str
    cancel_url: str
    customer_email: Optional[EmailStr] = None

class CheckoutResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    checkout_url: Optional[str] = None
    error: Optional[str] = None

class EntitlementsResponse(BaseModel):
    workspace_id: str
    plan: str
    report_credits: int
    can_publish: bool
    reports_generated_this_month: int
    subscription: Optional[dict] = None

class ReportAccessResponse(BaseModel):
    can_generate: bool
    has_credits: bool
    credits_available: int
    credits_needed: int
    plan: str
    limit_reason: Optional[str] = None
    upgrade_required: bool

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    db: Session = Depends(get_db)
):
    """Create Stripe checkout session for subscription or credit pack."""
    
    logger.info(f"Creating checkout for workspace {request.workspace_id}: {request.product_type}/{request.product_id}")
    
    try:
        billing_service = BillingService()
        
        # Create checkout session
        result = await billing_service.create_checkout_session(
            workspace_id=request.workspace_id,
            product_type=request.product_type,
            product_id=request.product_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=request.customer_email
        )
        
        if result['success']:
            return CheckoutResponse(
                success=True,
                session_id=result['session_id'],
                checkout_url=result['checkout_url']
            )
        else:
            return CheckoutResponse(
                success=False,
                error=result['error']
            )
            
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Checkout failed: {str(e)}")

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    
    try:
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")
        
        billing_service = BillingService()
        result = await billing_service.handle_webhook(payload, signature)
        
        if result['success']:
            return {"received": True}
        else:
            logger.error(f"Webhook handling failed: {result}")
            raise HTTPException(status_code=400, detail="Webhook processing failed")
            
    except Exception as e:
        logger.error(f"Webhook endpoint failed: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook failed: {str(e)}")

@router.get("/entitlements/{workspace_id}", response_model=EntitlementsResponse)
async def get_workspace_entitlements(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get current entitlements and billing status for a workspace."""
    
    try:
        billing_service = BillingService()
        entitlements = await billing_service.get_workspace_entitlements(workspace_id)
        
        return EntitlementsResponse(**entitlements)
        
    except Exception as e:
        logger.error(f"Failed to get entitlements for {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get entitlements: {str(e)}")

@router.get("/access/{workspace_id}/{report_type}", response_model=ReportAccessResponse)
async def check_report_access(
    workspace_id: str,
    report_type: str,
    db: Session = Depends(get_db)
):
    """Check if workspace can generate a specific report type."""
    
    try:
        if report_type not in ["TRACKING_READINESS", "SPEND_BASELINE", "COMPETITOR_SNAPSHOT"]:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        billing_service = BillingService()
        access_check = await billing_service.check_report_access(workspace_id, report_type)
        
        return ReportAccessResponse(**access_check)
        
    except Exception as e:
        logger.error(f"Access check failed for {workspace_id}/{report_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Access check failed: {str(e)}")

@router.get("/pricing")
def get_pricing_info():
    """Get pricing information for frontend display."""
    
    try:
        billing_service = BillingService()
        pricing = billing_service.get_pricing_info()
        
        return pricing
        
    except Exception as e:
        logger.error(f"Failed to get pricing info: {e}")
        raise HTTPException(status_code=500, detail=f"Pricing info failed: {str(e)}")

@router.post("/consume-credits/{workspace_id}")
async def consume_report_credits(
    workspace_id: str,
    report_type: str,
    report_id: str,
    db: Session = Depends(get_db)
):
    """Consume credits for report generation."""
    
    try:
        billing_service = BillingService()
        
        result = await billing_service.consume_report_credits(
            workspace_id, report_type, report_id
        )
        
        if result['success']:
            return {
                "success": True,
                "credits_consumed": result['credits_consumed'],
                "credits_remaining": result['credits_remaining']
            }
        else:
            return {
                "success": False,
                "error": result['error'],
                "reason": result.get('reason'),
                "upgrade_required": result.get('upgrade_required', False)
            }
            
    except Exception as e:
        logger.error(f"Credit consumption failed: {e}")
        raise HTTPException(status_code=500, detail=f"Credit consumption failed: {str(e)}")

@router.get("/usage/{workspace_id}")
async def get_usage_stats(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed usage statistics for a workspace."""
    
    try:
        from simple_database import SessionLocal, BillingEvent
        
        # Get entitlements
        billing_service = BillingService()
        entitlements = await billing_service.get_workspace_entitlements(workspace_id)
        
        # Get billing events
        db = SessionLocal()
        try:
            billing_events = db.query(BillingEvent).filter(
                BillingEvent.workspace_id == workspace_id
            ).order_by(BillingEvent.created_at.desc()).limit(50).all()
            
            # Calculate usage statistics
            total_spent = sum(event.amount or 0 for event in billing_events if event.amount) / 100  # Convert from cents
            total_credits_purchased = sum(event.credits_added for event in billing_events if event.credits_added)
            total_credits_consumed = sum(event.credits_consumed for event in billing_events if event.credits_consumed)
            
            recent_events = []
            for event in billing_events[:10]:  # Last 10 events
                recent_events.append({
                    "event_type": event.event_type,
                    "product_name": event.product_name,
                    "credits_added": event.credits_added,
                    "credits_consumed": event.credits_consumed,
                    "amount": event.amount / 100 if event.amount else 0,
                    "created_at": event.created_at.isoformat()
                })
            
            return {
                **entitlements,
                "usage_stats": {
                    "total_spent": total_spent,
                    "total_credits_purchased": total_credits_purchased,
                    "total_credits_consumed": total_credits_consumed,
                    "recent_events": recent_events
                }
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get usage stats for {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Usage stats failed: {str(e)}")
