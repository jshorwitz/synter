from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Keyword, SearchTerm
import re
import math
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)
router = APIRouter()

# ICP Lexicons from the spec
BRAND_TERMS = [
    "sourcegraph", "sourcegraph enterprise", "sourcegraph ai", "sourcegraph code search"
]

INCLUDE_TERMS = [
    "semantic code search", "enterprise code search", "codebase search",
    "code discovery", "code navigation", "code intelligence", "ai code assistant",
    "repo search", "monorepo search", "code indexing", "search in code",
    "large codebase", "semantic search code", "code understanding"
]

EXCLUDE_TERMS = [
    "homework", "assignment", "tutorial", "course", "learn", "leetcode",
    "job", "salary", "interview", "pdf", "definition", "free download",
    "torrent", "crack", "cheat", "student"
]


def fuzzy_match(text: str, pattern: str, max_edits: int = 1) -> bool:
    """Simple fuzzy matching with edit distance."""
    text = text.lower().strip()
    pattern = pattern.lower().strip()
    
    # Exact match first
    if pattern in text:
        return True
    
    # For simplicity, just check if most words are present
    pattern_words = pattern.split()
    text_words = text.split()
    
    matches = 0
    for p_word in pattern_words:
        for t_word in text_words:
            if p_word in t_word or t_word in p_word:
                matches += 1
                break
    
    # Consider it a match if most words are found
    return matches >= len(pattern_words) - max_edits


def calculate_icp_score(text: str, impressions: int = 0, clicks: int = 0) -> Tuple[int, str, float]:
    """
    Calculate ICP score for a keyword or search term.
    Returns (score, rationale, confidence)
    """
    text_lower = text.lower().strip()
    score = 50  # Start at neutral
    rationale_parts = []
    
    # Brand match check (+40)
    brand_match = False
    for brand_term in BRAND_TERMS:
        if fuzzy_match(text_lower, brand_term):
            score += 40
            brand_match = True
            rationale_parts.append(f"Brand match: '{brand_term}' (+40)")
            break
    
    if not brand_match:
        rationale_parts.append("Brand: no")
    
    # Include terms check (+25)
    include_match = False
    for include_term in INCLUDE_TERMS:
        if fuzzy_match(text_lower, include_term):
            score += 25
            include_match = True
            rationale_parts.append(f"Include match: '{include_term}' (+25)")
            break
    
    if not include_match:
        rationale_parts.append("Include: none")
    
    # Exclude terms check (-30)
    exclude_match = False
    for exclude_term in EXCLUDE_TERMS:
        if fuzzy_match(text_lower, exclude_term):
            score -= 30
            exclude_match = True
            rationale_parts.append(f"Exclude match: '{exclude_term}' (-30)")
            break
    
    if not exclude_match:
        rationale_parts.append("Exclude: none")
    
    # Free/open source without enterprise check (-15)
    if ("free" in text_lower or "open source" in text_lower) and "enterprise" not in text_lower:
        score -= 15
        rationale_parts.append("Free/open source without enterprise (-15)")
    
    # Clamp score to [0, 100]
    score = max(0, min(100, score))
    
    # Calculate confidence based on clicks (more clicks = higher confidence)
    confidence = min(1.0, math.log10(clicks + 10) / 2) if clicks > 0 else 0.5
    
    rationale = "; ".join(rationale_parts)
    
    return score, rationale, confidence


@router.post("/icp")
def score_icp(
    level: str = Query(..., description="Level to score: 'keyword' or 'term'"),
    limit: int = Query(default=1000, description="Maximum items to score"),
    db: Session = Depends(get_db)
):
    """Compute and save ICP scores for keywords or search terms."""
    try:
        if level not in ["keyword", "term"]:
            raise HTTPException(status_code=400, detail="Level must be 'keyword' or 'term'")
        
        scored_count = 0
        
        if level == "keyword":
            # Score keywords that don't have scores yet
            keywords = db.query(Keyword).filter(Keyword.icp_score.is_(None)).limit(limit).all()
            
            for keyword in keywords:
                # Get metrics for this keyword to inform confidence
                from models import DailyMetric
                metrics = db.query(DailyMetric).filter(
                    DailyMetric.level == "keyword",
                    DailyMetric.ref_id == keyword.id
                ).first()
                
                clicks = metrics.clicks if metrics else 0
                impressions = metrics.impressions if metrics else 0
                
                score, rationale, confidence = calculate_icp_score(
                    keyword.text, impressions, clicks
                )
                
                keyword.icp_score = score
                keyword.icp_rationale = rationale
                keyword.icp_confidence = confidence
                scored_count += 1
        
        elif level == "term":
            # Score search terms that don't have scores yet
            search_terms = db.query(SearchTerm).filter(SearchTerm.icp_score.is_(None)).limit(limit).all()
            
            for search_term in search_terms:
                # For search terms, we use simplified metrics
                # In a real implementation, you'd aggregate metrics by search term
                score, rationale, confidence = calculate_icp_score(search_term.text, 10, 1)
                
                search_term.icp_score = score
                search_term.icp_rationale = rationale
                search_term.icp_confidence = confidence
                scored_count += 1
        
        db.commit()
        
        return {
            "status": "success",
            "level": level,
            "items_scored": scored_count,
            "total_requested": limit
        }
        
    except Exception as e:
        logger.error(f"ICP scoring failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.get("/icp/stats")
def get_icp_stats(db: Session = Depends(get_db)):
    """Get ICP scoring statistics."""
    try:
        # Keyword stats
        keyword_stats = db.query(
            Keyword.icp_score,
            db.func.count(Keyword.id).label('count')
        ).filter(
            Keyword.icp_score.isnot(None)
        ).group_by(Keyword.icp_score).all()
        
        # Search term stats
        term_stats = db.query(
            SearchTerm.icp_score,
            db.func.count(SearchTerm.id).label('count')
        ).filter(
            SearchTerm.icp_score.isnot(None)
        ).group_by(SearchTerm.icp_score).all()
        
        # Create score distribution buckets
        keyword_buckets = {"high": 0, "medium": 0, "low": 0, "unscored": 0}
        term_buckets = {"high": 0, "medium": 0, "low": 0, "unscored": 0}
        
        for score, count in keyword_stats:
            if score >= 70:
                keyword_buckets["high"] += count
            elif score >= 40:
                keyword_buckets["medium"] += count
            else:
                keyword_buckets["low"] += count
        
        for score, count in term_stats:
            if score >= 70:
                term_buckets["high"] += count
            elif score >= 40:
                term_buckets["medium"] += count
            else:
                term_buckets["low"] += count
        
        # Count unscored items
        unscored_keywords = db.query(Keyword).filter(Keyword.icp_score.is_(None)).count()
        unscored_terms = db.query(SearchTerm).filter(SearchTerm.icp_score.is_(None)).count()
        
        keyword_buckets["unscored"] = unscored_keywords
        term_buckets["unscored"] = unscored_terms
        
        return {
            "keywords": keyword_buckets,
            "search_terms": term_buckets,
            "scoring_criteria": {
                "high_fit": "70-100 (strong ICP match)",
                "medium_fit": "40-69 (moderate ICP match)",
                "low_fit": "0-39 (poor ICP match)"
            }
        }
        
    except Exception as e:
        logger.error(f"Getting ICP stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/icp/sample")
def get_sample_scores(
    level: str = Query(..., description="Level: 'keyword' or 'term'"),
    score_range: str = Query(default="all", description="Score range: 'high', 'medium', 'low', or 'all'"),
    limit: int = Query(default=10, description="Number of samples"),
    db: Session = Depends(get_db)
):
    """Get sample scored items for inspection."""
    try:
        if level not in ["keyword", "term"]:
            raise HTTPException(status_code=400, detail="Level must be 'keyword' or 'term'")
        
        # Define score filters
        score_filter = None
        if score_range == "high":
            score_filter = (70, 100)
        elif score_range == "medium":
            score_filter = (40, 69)
        elif score_range == "low":
            score_filter = (0, 39)
        
        if level == "keyword":
            query = db.query(Keyword).filter(Keyword.icp_score.isnot(None))
            if score_filter:
                query = query.filter(
                    Keyword.icp_score >= score_filter[0],
                    Keyword.icp_score <= score_filter[1]
                )
            results = query.limit(limit).all()
            
            return {
                "level": level,
                "score_range": score_range,
                "samples": [
                    {
                        "id": kw.id,
                        "text": kw.text,
                        "match_type": kw.match_type,
                        "icp_score": kw.icp_score,
                        "icp_rationale": kw.icp_rationale,
                        "confidence": kw.icp_confidence
                    }
                    for kw in results
                ]
            }
        
        else:  # search terms
            query = db.query(SearchTerm).filter(SearchTerm.icp_score.isnot(None))
            if score_filter:
                query = query.filter(
                    SearchTerm.icp_score >= score_filter[0],
                    SearchTerm.icp_score <= score_filter[1]
                )
            results = query.limit(limit).all()
            
            return {
                "level": level,
                "score_range": score_range,
                "samples": [
                    {
                        "id": term.id,
                        "text": term.text,
                        "matched_keyword": term.matched_keyword_text,
                        "icp_score": term.icp_score,
                        "icp_rationale": term.icp_rationale,
                        "confidence": term.icp_confidence
                    }
                    for term in results
                ]
            }
        
    except Exception as e:
        logger.error(f"Getting sample scores failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sample retrieval failed: {str(e)}")
