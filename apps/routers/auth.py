from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import OAuthToken
from ads.client import ads_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/google_ads/start")
def start_oauth_flow():
    """Start the Google Ads OAuth flow."""
    # In production, this would redirect to Google OAuth
    # For MVP, we assume credentials are configured via environment
    return {
        "message": "OAuth flow would start here",
        "note": "For MVP, configure credentials in .env file",
        "required_scopes": ["https://www.googleapis.com/auth/adwords"]
    }


@router.post("/google_ads/callback")
def oauth_callback(code: str, db: Session = Depends(get_db)):
    """Handle OAuth callback and store refresh token."""
    # In production, this would exchange the code for tokens
    # For MVP, this is a placeholder
    return {
        "message": "OAuth callback handled",
        "note": "Tokens would be stored in database"
    }


@router.get("/google_ads/status")
def oauth_status():
    """Check Google Ads API connection status."""
    try:
        # Test the connection
        client = ads_client.get_client()
        customer_id = ads_client.customer_id
        
        # Try a simple query to verify credentials
        query = "SELECT customer.id FROM customer LIMIT 1"
        results = ads_client.execute_query(query, customer_id)
        
        return {
            "status": "connected",
            "customer_id": customer_id,
            "accounts_accessible": len(results) > 0
        }
    except Exception as e:
        logger.error(f"Google Ads API connection failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Google Ads API connection failed: {str(e)}"
        )
