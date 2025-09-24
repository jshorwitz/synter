from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Report, Website
from pydantic import BaseModel, HttpUrl
from services.report_generator import ReportGenerator
from services.website_analyzer import WebsiteAnalyzer
from services.spend_baseline_generator import SpendBaselineGenerator
from services.competitor_snapshot_generator import CompetitorSnapshotGenerator
from services.billing_service import BillingService
import json
import logging
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class TrackingReadinessRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = "system"
    workspace_id: Optional[str] = "default"

class SpendBaselineRequest(BaseModel):
    user_id: Optional[str] = "system"
    workspace_id: Optional[str] = "default"
    days: Optional[int] = 90
    account_ids: Optional[List[str]] = []  # Specific accounts to include

class CompetitorSnapshotRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = "system"
    workspace_id: Optional[str] = "default"
    
class ReportResponse(BaseModel):
    id: str
    report_type: str
    title: str
    status: str
    overall_score: Optional[int] = None
    confidence: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    generation_time_ms: Optional[int] = None
    credit_cost: int
    
    class Config:
        from_attributes = True

@router.post("/TRACKING_READINESS", response_model=ReportResponse)
async def generate_tracking_readiness_report(
    request: TrackingReadinessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate a tracking readiness report for a website."""
    
    logger.info(f"Tracking readiness report requested for {request.url}")
    
    # Check billing access first
    billing_service = BillingService()
    access_check = await billing_service.check_report_access(request.workspace_id, "TRACKING_READINESS")
    
    if not access_check['can_generate']:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "payment_required",
                "message": access_check.get('limit_reason', 'Insufficient credits'),
                "credits_available": access_check['credits_available'],
                "credits_needed": access_check['credits_needed'],
                "plan": access_check['plan'],
                "upgrade_required": access_check['upgrade_required']
            }
        )
    
    try:
        url = str(request.url)
        
        # Check if we already have a recent analysis for this URL
        input_data = {"url": url}
        report_gen = ReportGenerator()
        input_hash = report_gen.create_input_hash("TRACKING_READINESS", input_data)
        
        # Look for existing report
        existing_report = db.query(Report).filter(
            Report.report_type == "TRACKING_READINESS",
            Report.input_hash == input_hash,
            Report.status == "ready"
        ).first()
        
        if existing_report:
            logger.info(f"Returning existing report: {existing_report.id}")
            return existing_report
        
        # Check if website analysis exists
        website_analyzer = WebsiteAnalyzer()
        website_id = website_analyzer._create_website_id(url) if hasattr(website_analyzer, '_create_website_id') else None
        
        if website_id:
            website = db.query(Website).filter(Website.id == website_id).first()
        else:
            website = None
        
        # If no website analysis exists, we need to analyze first
        if not website or not website.technologies:
            logger.info(f"No website analysis found, analyzing {url} first...")
            
            # Run website analysis
            website_data = await website_analyzer.analyze_website(url, deep_analysis=True)
            
            # Use the analyzed data directly for report generation
            website_data['id'] = website_id
            website_data['url'] = url
        else:
            # Use existing website analysis
            website_data = {
                'id': website.id,
                'url': website.url,
                'title': website.title,
                'technologies': json.loads(website.technologies) if website.technologies else {},
                'tracking_pixels': json.loads(website.tracking_pixels) if website.tracking_pixels else []
            }
        
        logger.info(f"Generating report with {len(website_data.get('technologies', {}))} tech categories")
        
        # Generate the report
        report_data = await report_gen.generate_tracking_readiness_report(
            website_data,
            request.user_id,
            request.workspace_id
        )
        
        # Save report to database
        report = Report(**report_data)
        db.add(report)
        db.commit()
        db.refresh(report)
        
        # Consume credits after successful generation
        credit_result = await billing_service.consume_report_credits(
            request.workspace_id, "TRACKING_READINESS", report.id
        )
        
        if not credit_result['success']:
            logger.warning(f"Credit consumption failed after report generation: {credit_result}")
            # Report was generated successfully, so we still return it
        
        logger.info(f"Tracking readiness report generated successfully: {report.id}")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate tracking readiness report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/SPEND_BASELINE", response_model=ReportResponse)
async def generate_spend_baseline_report(
    request: SpendBaselineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate a spend baseline report from connected ad accounts."""
    
    logger.info(f"Spend baseline report requested for workspace {request.workspace_id}")
    
    # Check billing access first
    billing_service = BillingService()
    access_check = await billing_service.check_report_access(request.workspace_id, "SPEND_BASELINE")
    
    if not access_check['can_generate']:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "payment_required",
                "message": access_check.get('limit_reason', 'Insufficient credits'),
                "credits_available": access_check['credits_available'],
                "credits_needed": access_check['credits_needed'],
                "plan": access_check['plan'],
                "upgrade_required": access_check['upgrade_required']
            }
        )
    
    try:
        from simple_database import AdAccount
        
        # Get connected ad accounts for this workspace
        query = db.query(AdAccount).filter(
            AdAccount.workspace_id == request.workspace_id,
            AdAccount.is_active == True
        )
        
        if request.account_ids:
            query = query.filter(AdAccount.id.in_(request.account_ids))
        
        ad_accounts = query.all()
        
        if not ad_accounts:
            raise HTTPException(
                status_code=400, 
                detail="No connected ad accounts found. Connect Google Ads or Meta Ads accounts first."
            )
        
        # Convert to dict format for the generator
        account_data = []
        for account in ad_accounts:
            account_data.append({
                "id": account.id,
                "platform": account.platform,
                "account_id": account.account_id,
                "account_name": account.account_name,
                "access_token": account.access_token,
                "refresh_token": account.refresh_token,
                "currency": account.currency
            })
        
        # Check for existing report with same parameters
        baseline_gen = SpendBaselineGenerator()
        input_hash = baseline_gen._create_input_hash(account_data, request.days)
        
        existing_report = db.query(Report).filter(
            Report.report_type == "SPEND_BASELINE",
            Report.input_hash == input_hash,
            Report.status == "ready"
        ).first()
        
        if existing_report:
            logger.info(f"Returning existing spend baseline report: {existing_report.id}")
            return existing_report
        
        # Generate new report
        logger.info(f"Generating spend baseline report for {len(account_data)} accounts")
        
        report_data = await baseline_gen.generate_spend_baseline_report(
            account_data,
            request.days,
            request.user_id,
            request.workspace_id
        )
        
        # Save report to database
        report = Report(**report_data)
        db.add(report)
        db.commit()
        db.refresh(report)
        
        logger.info(f"Spend baseline report generated successfully: {report.id}")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate spend baseline report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/COMPETITOR_SNAPSHOT", response_model=ReportResponse)
async def generate_competitor_snapshot_report(
    request: CompetitorSnapshotRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate a competitor snapshot report using SEMrush data."""
    
    logger.info(f"Competitor snapshot report requested for {request.url}")
    
    try:
        url = str(request.url)
        
        # Check if we already have a recent analysis for this URL
        snapshot_gen = CompetitorSnapshotGenerator()
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        input_hash = snapshot_gen._create_input_hash(domain)
        
        # Look for existing report
        existing_report = db.query(Report).filter(
            Report.report_type == "COMPETITOR_SNAPSHOT",
            Report.input_hash == input_hash,
            Report.status == "ready"
        ).first()
        
        if existing_report:
            logger.info(f"Returning existing competitor snapshot report: {existing_report.id}")
            return existing_report
        
        # Check if website analysis exists
        website_analyzer = WebsiteAnalyzer()
        website_id = website_analyzer._create_website_id(url) if hasattr(website_analyzer, '_create_website_id') else None
        
        if website_id:
            website = db.query(Website).filter(Website.id == website_id).first()
        else:
            website = None
        
        # If no website analysis exists, we need to analyze first
        if not website:
            logger.info(f"No website analysis found, analyzing {url} first...")
            
            # Run website analysis
            website_data = await website_analyzer.analyze_website(url, deep_analysis=False)
            website_data['id'] = website_id
            website_data['url'] = url
        else:
            # Use existing website analysis
            website_data = {
                'id': website.id,
                'url': website.url,
                'title': website.title,
                'industry': website.industry,
                'business_model': website.business_model
            }
        
        logger.info(f"Generating competitor snapshot for {domain}")
        
        # Generate the competitor snapshot report
        report_data = await snapshot_gen.generate_competitor_snapshot_report(
            website_data,
            request.user_id,
            request.workspace_id
        )
        
        # Save report to database
        report = Report(**report_data)
        db.add(report)
        db.commit()
        db.refresh(report)
        
        logger.info(f"Competitor snapshot report generated successfully: {report.id}")
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate competitor snapshot report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Get report by ID."""
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report

@router.get("/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: str, db: Session = Depends(get_db)):
    """Get report HTML content."""
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not report.html_content:
        raise HTTPException(status_code=404, detail="HTML content not available")
    
    return HTMLResponse(content=report.html_content)

@router.get("/{report_id}/data")
def get_report_data(report_id: str, db: Session = Depends(get_db)):
    """Get raw report data as JSON."""
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        data = json.loads(report.data_json) if report.data_json else {}
        return {
            "report_id": report.id,
            "report_type": report.report_type,
            "title": report.title,
            "summary": report.summary,
            "overall_score": report.overall_score,
            "confidence": report.confidence,
            "status": report.status,
            "data": data,
            "created_at": report.created_at,
            "generation_time_ms": report.generation_time_ms
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid report data")

@router.get("/")
def list_reports(
    report_type: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List reports with optional filters."""
    
    query = db.query(Report)
    
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if user_id:
        query = query.filter(Report.user_id == user_id)
    if workspace_id:
        query = query.filter(Report.workspace_id == workspace_id)
    if status:
        query = query.filter(Report.status == status)
    
    # Order by creation date (newest first)
    query = query.order_by(Report.created_at.desc())
    
    reports = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "reports": reports,
        "total": total,
        "skip": skip,
        "limit": limit,
        "filters": {
            "report_type": report_type,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "status": status
        }
    }

@router.delete("/{report_id}")
def delete_report(report_id: str, db: Session = Depends(get_db)):
    """Delete a report."""
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    db.delete(report)
    db.commit()
    
    logger.info(f"Report deleted: {report_id}")
    
    return {"message": "Report deleted successfully"}

# Helper function for website_analyzer
def _create_website_id(url: str) -> str:
    """Create a website ID from URL - helper function."""
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()

# Monkey patch the website analyzer to add the missing method
if not hasattr(WebsiteAnalyzer, '_create_website_id'):
    WebsiteAnalyzer._create_website_id = staticmethod(_create_website_id)
