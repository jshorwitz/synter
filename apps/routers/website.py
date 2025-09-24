from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from models import Website, Competitor, Persona, WebsiteCampaign
from pydantic import BaseModel, HttpUrl
import hashlib
import validators
import logging
from datetime import datetime
import json
from services.website_analyzer import WebsiteAnalyzer
from services.competitor_research import CompetitorResearcher
from services.persona_generator import PersonaGenerator

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class WebsiteAnalysisRequest(BaseModel):
    url: HttpUrl
    deep_analysis: bool = True
    include_competitors: bool = True
    include_personas: bool = True

class WebsiteResponse(BaseModel):
    id: str
    url: str
    title: str | None = None
    description: str | None = None
    industry: str | None = None
    business_model: str | None = None
    analysis_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

def create_website_id(url: str) -> str:
    """Create a unique ID for a website from its URL."""
    return hashlib.md5(url.encode()).hexdigest()

@router.post("/analyze", response_model=WebsiteResponse)
def analyze_website(
    request: WebsiteAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Analyze a website for marketing insights."""
    try:
        url = str(request.url)
        
        # Validate URL
        if not validators.url(url):
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # Create unique ID
        website_id = create_website_id(url)
        
        # Check if already exists
        existing = db.query(Website).filter(Website.id == website_id).first()
        if existing:
            if existing.analysis_status == "analyzing":
                return existing
            elif existing.analysis_status == "completed":
                # Re-analyze if requested
                existing.analysis_status = "analyzing"
                existing.last_analyzed = datetime.utcnow()
                db.commit()
                background_tasks.add_task(
                    analyze_website_background, 
                    website_id, 
                    request.deep_analysis,
                    request.include_competitors,
                    request.include_personas
                )
                return existing
        
        # Create new website record
        website = Website(
            id=website_id,
            url=url,
            analysis_status="analyzing"
        )
        db.add(website)
        db.commit()
        
        # Start background analysis
        background_tasks.add_task(
            analyze_website_background, 
            website_id, 
            request.deep_analysis,
            request.include_competitors,
            request.include_personas
        )
        
        return website
        
    except Exception as e:
        logger.error(f"Website analysis request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

async def analyze_website_background(
    website_id: str, 
    deep_analysis: bool = True,
    include_competitors: bool = True,
    include_personas: bool = True
):
    """Background task to analyze website."""
    from database import SessionLocal
    db = SessionLocal()
    
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            logger.error(f"Website {website_id} not found for analysis")
            return
        
        analyzer = WebsiteAnalyzer()
        
        # Step 1: Basic website analysis
        logger.info(f"Starting analysis for {website.url}")
        analysis_result = await analyzer.analyze_website(website.url, deep_analysis)
        
        # Update website with analysis results
        website.title = analysis_result.get('title')
        website.description = analysis_result.get('description')
        website.industry = analysis_result.get('industry')
        website.business_model = analysis_result.get('business_model')
        website.content_summary = analysis_result.get('content_summary')
        website.key_topics = json.dumps(analysis_result.get('key_topics', []))
        website.value_propositions = json.dumps(analysis_result.get('value_propositions', []))
        website.technologies = json.dumps(analysis_result.get('technologies', {}))
        website.tracking_pixels = json.dumps(analysis_result.get('tracking_pixels', []))
        
        db.commit()
        
        # Step 2: Competitor research (if requested)
        if include_competitors:
            logger.info(f"Starting competitor research for {website.url}")
            researcher = CompetitorResearcher()
            competitors = await researcher.find_competitors(
                website.url, 
                analysis_result.get('industry'),
                analysis_result.get('key_topics', [])
            )
            
            # Save competitors
            for comp_data in competitors[:5]:  # Limit to top 5
                competitor_id = create_website_id(comp_data['url']) + "_comp"
                competitor = Competitor(
                    id=competitor_id,
                    website_id=website_id,
                    competitor_url=comp_data['url'],
                    competitor_name=comp_data.get('name'),
                    traffic_rank=comp_data.get('traffic_rank'),
                    monthly_visits=comp_data.get('monthly_visits'),
                    traffic_sources=json.dumps(comp_data.get('traffic_sources', {})),
                    organic_keywords=comp_data.get('organic_keywords'),
                    paid_keywords=comp_data.get('paid_keywords'),
                    estimated_budget=comp_data.get('estimated_budget'),
                    competitive_score=comp_data.get('competitive_score', 50),
                    key_differences=json.dumps(comp_data.get('key_differences', []))
                )
                db.add(competitor)
        
        # Step 3: Persona generation (if requested)
        if include_personas:
            logger.info(f"Generating personas for {website.url}")
            persona_gen = PersonaGenerator()
            personas = await persona_gen.generate_personas(
                analysis_result,
                db.query(Competitor).filter(Competitor.website_id == website_id).all()
            )
            
            # Save personas
            for i, persona_data in enumerate(personas):
                persona_id = f"{website_id}_persona_{i}"
                persona = Persona(
                    id=persona_id,
                    website_id=website_id,
                    name=persona_data.get('name'),
                    job_title=persona_data.get('job_title'),
                    industry=persona_data.get('industry'),
                    company_size=persona_data.get('company_size'),
                    pain_points=json.dumps(persona_data.get('pain_points', [])),
                    goals=json.dumps(persona_data.get('goals', [])),
                    motivations=json.dumps(persona_data.get('motivations', [])),
                    search_behaviors=json.dumps(persona_data.get('search_behaviors', [])),
                    preferred_channels=json.dumps(persona_data.get('preferred_channels', [])),
                    keywords=json.dumps(persona_data.get('keywords', [])),
                    ad_copy_themes=json.dumps(persona_data.get('ad_copy_themes', [])),
                    confidence_score=persona_data.get('confidence_score', 0.5)
                )
                db.add(persona)
        
        # Mark analysis as complete
        website.analysis_status = "completed"
        website.last_analyzed = datetime.utcnow()
        db.commit()
        
        logger.info(f"Analysis complete for {website.url}")
        
    except Exception as e:
        logger.error(f"Background analysis failed for {website_id}: {e}")
        # Mark as failed
        if website:
            website.analysis_status = "failed"
            db.commit()
    finally:
        db.close()

@router.get("/{website_id}", response_model=WebsiteResponse)
def get_website(website_id: str, db: Session = Depends(get_db)):
    """Get website analysis results."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return website

@router.get("/{website_id}/competitors")
def get_competitors(website_id: str, db: Session = Depends(get_db)):
    """Get competitor analysis for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    competitors = db.query(Competitor).filter(Competitor.website_id == website_id).all()
    return {
        "website_id": website_id,
        "competitors": [
            {
                "id": comp.id,
                "url": comp.competitor_url,
                "name": comp.competitor_name,
                "traffic_rank": comp.traffic_rank,
                "monthly_visits": comp.monthly_visits,
                "organic_keywords": comp.organic_keywords,
                "paid_keywords": comp.paid_keywords,
                "estimated_budget": comp.estimated_budget,
                "competitive_score": comp.competitive_score
            }
            for comp in competitors
        ]
    }

@router.get("/{website_id}/personas")
def get_personas(website_id: str, db: Session = Depends(get_db)):
    """Get generated personas for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    personas = db.query(Persona).filter(Persona.website_id == website_id).all()
    return {
        "website_id": website_id,
        "personas": [
            {
                "id": persona.id,
                "name": persona.name,
                "job_title": persona.job_title,
                "industry": persona.industry,
                "company_size": persona.company_size,
                "pain_points": json.loads(persona.pain_points) if persona.pain_points else [],
                "goals": json.loads(persona.goals) if persona.goals else [],
                "keywords": json.loads(persona.keywords) if persona.keywords else [],
                "confidence_score": persona.confidence_score
            }
            for persona in personas
        ]
    }

@router.get("/")
def list_websites(
    skip: int = 0, 
    limit: int = 50,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List analyzed websites."""
    query = db.query(Website)
    
    if status:
        query = query.filter(Website.analysis_status == status)
    
    websites = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "websites": websites,
        "total": total,
        "skip": skip,
        "limit": limit
    }
