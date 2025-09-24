import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from jinja2 import Template
import uuid
from services.semrush_enhanced import SEMrushEnhanced
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class CompetitorSnapshotGenerator:
    """Generate competitor snapshot reports using SEMrush data."""
    
    def __init__(self):
        self.semrush = SEMrushEnhanced()
        self.report_templates_dir = os.path.join(os.path.dirname(__file__), 'report_templates')
        os.makedirs(self.report_templates_dir, exist_ok=True)
    
    async def generate_competitor_snapshot_report(
        self,
        website_data: Dict,
        user_id: str = "system",
        workspace_id: str = "default"
    ) -> Dict:
        """Generate competitor snapshot report."""
        
        logger.info(f"Generating competitor snapshot report for {website_data.get('url')}")
        
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())
        
        try:
            target_url = website_data.get('url')
            target_domain = urlparse(target_url).netloc
            
            # Calculate input hash for deduplication
            input_hash = self._create_input_hash(target_domain)
            
            # Get comprehensive competitor analysis from SEMrush
            logger.info(f"Analyzing competitors for {target_domain}")
            competitor_overview = await self.semrush.get_competitor_overview(target_domain)
            
            # Get competitor domains for gap analysis
            organic_competitors = competitor_overview.get('organic_competitors', [])
            paid_competitors = competitor_overview.get('paid_competitors', [])
            
            # Combine and get top competitors
            all_competitors = list({comp['domain'] for comp in organic_competitors + paid_competitors})[:5]
            
            # Perform keyword gap analysis
            logger.info(f"Performing keyword gap analysis against {len(all_competitors)} competitors")
            keyword_gaps = await self.semrush.get_keyword_gap_analysis(target_domain, all_competitors)
            
            # Analyze competitive landscape
            analysis = self._analyze_competitive_landscape(
                competitor_overview, keyword_gaps, website_data
            )
            
            # Generate report content
            report_data = {
                "website_url": target_url,
                "website_title": website_data.get('title', 'Unknown Website'),
                "target_domain": target_domain,
                "analysis_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "summary": analysis['summary'],
                "domain_overview": competitor_overview.get('overview', {}),
                "competitive_landscape": analysis['competitive_landscape'],
                "keyword_opportunities": analysis['keyword_opportunities'],
                "ad_intelligence": analysis['ad_intelligence'],
                "recommendations": analysis['recommendations'],
                "competitor_overview": competitor_overview,
                "keyword_gaps": keyword_gaps
            }
            
            # Render HTML report
            html_content = self._render_competitor_snapshot_html(report_data)
            
            # Calculate generation time
            generation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Create report record
            report = {
                "id": report_id,
                "report_type": "COMPETITOR_SNAPSHOT",
                "website_id": website_data.get('id'),
                "input_hash": input_hash,
                "title": f"Competitor Snapshot - {website_data.get('title', target_domain)}",
                "summary": analysis['summary'],
                "data_json": json.dumps(report_data),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "html_content": html_content,
                "status": "ready",
                "generation_time_ms": generation_time_ms,
                "credit_cost": 3,
                "user_id": user_id,
                "workspace_id": workspace_id
            }
            
            logger.info(f"Competitor snapshot report generated: {report_id} (score: {analysis['overall_score']})")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate competitor snapshot report: {e}")
            return self._create_error_report(report_id, str(e), user_id, workspace_id)
    
    def _analyze_competitive_landscape(self, competitor_overview: Dict, keyword_gaps: Dict, website_data: Dict) -> Dict:
        """Analyze competitive landscape and generate insights."""
        
        domain_overview = competitor_overview.get('overview', {})
        organic_competitors = competitor_overview.get('organic_competitors', [])
        paid_competitors = competitor_overview.get('paid_competitors', [])
        top_keywords = competitor_overview.get('top_keywords', [])
        keyword_opportunities = keyword_gaps.get('top_keyword_opportunities', [])
        
        # Calculate competitive scores
        organic_strength = self._calculate_organic_strength(domain_overview, organic_competitors)
        paid_strength = self._calculate_paid_strength(domain_overview, paid_competitors)
        keyword_opportunity_score = self._calculate_keyword_opportunity_score(keyword_opportunities)
        
        # Overall competitive score
        overall_score = int((organic_strength + paid_strength + keyword_opportunity_score) / 3)
        
        # Determine confidence based on data quality
        confidence = self._determine_confidence(competitor_overview, keyword_gaps)
        
        # Generate competitive landscape insights
        competitive_landscape = {
            "organic_strength": {
                "score": organic_strength,
                "rank": domain_overview.get('organic_rank', 0),
                "keywords": domain_overview.get('organic_keywords', 0),
                "traffic": domain_overview.get('organic_traffic', 0),
                "top_competitors": organic_competitors[:5]
            },
            "paid_strength": {
                "score": paid_strength,
                "ad_keywords": domain_overview.get('ad_keywords', 0),
                "estimated_spend": sum(comp.get('ad_cost', 0) for comp in paid_competitors[:3]),
                "top_competitors": paid_competitors[:5]
            },
            "market_position": self._determine_market_position(organic_strength, paid_strength),
            "competitive_intensity": self._calculate_competitive_intensity(organic_competitors, paid_competitors)
        }
        
        # Generate keyword opportunities analysis
        keyword_analysis = {
            "total_opportunities": len(keyword_opportunities),
            "high_value_opportunities": len([kw for kw in keyword_opportunities if kw.get('opportunity_score', 0) >= 80]),
            "avg_opportunity_score": sum(kw.get('opportunity_score', 0) for kw in keyword_opportunities) / len(keyword_opportunities) if keyword_opportunities else 0,
            "top_opportunities": keyword_opportunities[:10],
            "keyword_gaps_summary": keyword_gaps.get('summary', {})
        }
        
        # Ad intelligence
        ad_copies = competitor_overview.get('ad_copies', [])
        ad_intelligence = {
            "ad_copies_found": len(ad_copies),
            "common_themes": self._extract_ad_themes(ad_copies),
            "messaging_patterns": self._analyze_messaging_patterns(ad_copies),
            "sample_ads": ad_copies[:5]
        }
        
        # Generate recommendations
        recommendations = self._generate_competitor_recommendations(
            competitive_landscape, keyword_analysis, ad_intelligence
        )
        
        # Generate summary
        summary = self._generate_competitive_summary(overall_score, competitive_landscape, keyword_analysis)
        
        return {
            "overall_score": overall_score,
            "confidence": confidence,
            "summary": summary,
            "competitive_landscape": competitive_landscape,
            "keyword_opportunities": keyword_analysis,
            "ad_intelligence": ad_intelligence,
            "recommendations": recommendations
        }
    
    def _calculate_organic_strength(self, overview: Dict, competitors: List[Dict]) -> int:
        """Calculate organic search strength score."""
        score = 50  # Base score
        
        # Keyword count factor
        keywords = overview.get('organic_keywords', 0)
        if keywords >= 10000:
            score += 25
        elif keywords >= 5000:
            score += 20
        elif keywords >= 1000:
            score += 15
        elif keywords >= 100:
            score += 10
        
        # Competitive position factor
        if competitors:
            avg_relevance = sum(comp.get('competitive_relevance', 0) for comp in competitors[:5]) / min(5, len(competitors))
            if avg_relevance >= 0.8:
                score += 15
            elif avg_relevance >= 0.6:
                score += 10
            elif avg_relevance >= 0.4:
                score += 5
        
        # Traffic factor
        traffic = overview.get('organic_traffic', 0)
        if traffic >= 100000:
            score += 10
        elif traffic >= 50000:
            score += 7
        elif traffic >= 10000:
            score += 5
        
        return min(100, max(0, score))
    
    def _calculate_paid_strength(self, overview: Dict, competitors: List[Dict]) -> int:
        """Calculate paid search strength score."""
        score = 50  # Base score
        
        # Ad keywords factor
        ad_keywords = overview.get('ad_keywords', 0)
        if ad_keywords >= 1000:
            score += 25
        elif ad_keywords >= 500:
            score += 20
        elif ad_keywords >= 100:
            score += 15
        elif ad_keywords >= 10:
            score += 10
        
        # Competitive position in paid
        if competitors:
            avg_relevance = sum(comp.get('competitive_relevance', 0) for comp in competitors[:5]) / min(5, len(competitors))
            if avg_relevance >= 0.8:
                score += 15
            elif avg_relevance >= 0.6:
                score += 10
            elif avg_relevance >= 0.4:
                score += 5
        
        # Investment level (estimated spend)
        total_competitor_spend = sum(comp.get('ad_cost', 0) for comp in competitors[:3])
        if total_competitor_spend >= 50000:
            score += 10
        elif total_competitor_spend >= 10000:
            score += 7
        elif total_competitor_spend >= 1000:
            score += 5
        
        return min(100, max(0, score))
    
    def _calculate_keyword_opportunity_score(self, opportunities: List[Dict]) -> int:
        """Calculate keyword opportunity score."""
        if not opportunities:
            return 30
        
        # Base on number and quality of opportunities
        high_value_count = len([kw for kw in opportunities if kw.get('opportunity_score', 0) >= 80])
        medium_value_count = len([kw for kw in opportunities if 60 <= kw.get('opportunity_score', 0) < 80])
        
        score = 40  # Base
        score += min(30, high_value_count * 3)  # 3 points per high-value opportunity
        score += min(20, medium_value_count * 2)  # 2 points per medium-value opportunity
        score += min(10, len(opportunities))  # 1 point per total opportunity
        
        return min(100, score)
    
    def _determine_confidence(self, competitor_overview: Dict, keyword_gaps: Dict) -> str:
        """Determine confidence level based on data quality."""
        organic_competitors = len(competitor_overview.get('organic_competitors', []))
        paid_competitors = len(competitor_overview.get('paid_competitors', []))
        keyword_opportunities = len(keyword_gaps.get('top_keyword_opportunities', []))
        
        if organic_competitors >= 5 and paid_competitors >= 3 and keyword_opportunities >= 10:
            return "HIGH"
        elif organic_competitors >= 3 and paid_competitors >= 2 and keyword_opportunities >= 5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _determine_market_position(self, organic_strength: int, paid_strength: int) -> str:
        """Determine market position based on organic and paid strength."""
        avg_strength = (organic_strength + paid_strength) / 2
        
        if avg_strength >= 80:
            return "Market Leader"
        elif avg_strength >= 65:
            return "Strong Competitor"
        elif avg_strength >= 50:
            return "Established Player"
        elif avg_strength >= 35:
            return "Emerging Player"
        else:
            return "New Entrant"
    
    def _calculate_competitive_intensity(self, organic_competitors: List[Dict], paid_competitors: List[Dict]) -> str:
        """Calculate competitive intensity of the market."""
        total_competitors = len(set([comp['domain'] for comp in organic_competitors + paid_competitors]))
        avg_relevance = 0
        
        if organic_competitors:
            avg_relevance = sum(comp.get('competitive_relevance', 0) for comp in organic_competitors[:5]) / min(5, len(organic_competitors))
        
        if total_competitors >= 10 and avg_relevance >= 0.7:
            return "Very High"
        elif total_competitors >= 7 and avg_relevance >= 0.5:
            return "High"
        elif total_competitors >= 5:
            return "Medium"
        else:
            return "Low"
    
    def _extract_ad_themes(self, ad_copies: List[Dict]) -> List[str]:
        """Extract common themes from ad copies."""
        themes = []
        
        if not ad_copies:
            return themes
        
        # Analyze titles and descriptions for common themes
        all_text = ' '.join([
            (ad.get('title', '') + ' ' + ad.get('description', '')).lower()
            for ad in ad_copies
        ])
        
        # Common business themes
        theme_keywords = {
            'efficiency': ['efficient', 'efficiency', 'streamline', 'optimize'],
            'innovation': ['innovative', 'cutting-edge', 'advanced', 'revolutionary'],
            'reliability': ['reliable', 'trusted', 'proven', 'secure'],
            'growth': ['grow', 'scale', 'expand', 'increase'],
            'savings': ['save', 'reduce', 'lower', 'affordable'],
            'ease_of_use': ['easy', 'simple', 'user-friendly', 'intuitive']
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                themes.append(theme.replace('_', ' ').title())
        
        return themes[:5]
    
    def _analyze_messaging_patterns(self, ad_copies: List[Dict]) -> List[str]:
        """Analyze messaging patterns in competitor ads."""
        patterns = []
        
        if not ad_copies:
            return patterns
        
        # Common patterns to look for
        pattern_checks = [
            ('Free Trial', lambda ad: 'free' in ad.get('title', '').lower() or 'trial' in ad.get('description', '').lower()),
            ('Call to Action', lambda ad: any(cta in ad.get('description', '').lower() for cta in ['start', 'get started', 'try', 'learn more'])),
            ('Benefits Focus', lambda ad: any(benefit in ad.get('title', '').lower() for benefit in ['improve', 'increase', 'boost', 'enhance'])),
            ('Problem Solution', lambda ad: any(problem in ad.get('description', '').lower() for problem in ['solution', 'solve', 'fix', 'address'])),
            ('Social Proof', lambda ad: any(proof in ad.get('description', '').lower() for proof in ['trusted', 'proven', 'thousands', 'leading']))
        ]
        
        for pattern_name, check_func in pattern_checks:
            if any(check_func(ad) for ad in ad_copies):
                patterns.append(pattern_name)
        
        return patterns
    
    def _generate_competitor_recommendations(self, landscape: Dict, keyword_analysis: Dict, ad_intelligence: Dict) -> List[Dict]:
        """Generate recommendations based on competitive analysis."""
        recommendations = []
        
        market_position = landscape.get('market_position', 'Unknown')
        competitive_intensity = landscape.get('competitive_intensity', 'Unknown')
        high_value_opportunities = keyword_analysis.get('high_value_opportunities', 0)
        total_opportunities = keyword_analysis.get('total_opportunities', 0)
        
        # Market position recommendations
        if market_position in ['New Entrant', 'Emerging Player']:
            recommendations.append({
                "priority": "high",
                "category": "Market Entry",
                "title": "Focus on Long-Tail Keywords",
                "description": f"As a {market_position.lower()}, target long-tail, low-competition keywords to establish market presence before competing on high-volume terms."
            })
        
        elif market_position in ['Market Leader', 'Strong Competitor']:
            recommendations.append({
                "priority": "medium", 
                "category": "Market Defense",
                "title": "Defend Market Position",
                "description": f"Maintain strong {market_position.lower()} position by monitoring competitor keyword movements and protecting branded terms."
            })
        
        # Keyword opportunity recommendations
        if high_value_opportunities >= 10:
            recommendations.append({
                "priority": "high",
                "category": "Keyword Expansion",
                "title": "Capitalize on High-Value Keyword Gaps",
                "description": f"Found {high_value_opportunities} high-value keyword opportunities. Prioritize these for immediate campaign expansion."
            })
        elif total_opportunities >= 20:
            recommendations.append({
                "priority": "medium",
                "category": "Keyword Research",
                "title": "Expand Keyword Portfolio",
                "description": f"Found {total_opportunities} keyword opportunities. Conduct deeper research to identify quick wins."
            })
        
        # Competitive intensity recommendations
        if competitive_intensity == "Very High":
            recommendations.append({
                "priority": "high",
                "category": "Differentiation",
                "title": "Focus on Unique Value Proposition",
                "description": "High competitive intensity detected. Emphasize unique differentiators and consider niche targeting."
            })
        elif competitive_intensity == "Low":
            recommendations.append({
                "priority": "medium",
                "category": "Market Opportunity",
                "title": "Aggressive Market Expansion",
                "description": "Low competitive intensity presents growth opportunity. Consider increasing budget and expanding keyword targeting."
            })
        
        # Ad intelligence recommendations
        ad_themes = ad_intelligence.get('common_themes', [])
        if 'Free Trial' in ad_intelligence.get('messaging_patterns', []):
            recommendations.append({
                "priority": "medium",
                "category": "Messaging",
                "title": "Consider Free Trial Messaging",
                "description": "Competitors are successfully using free trial offers. Test similar low-risk trial offers."
            })
        
        # Budget allocation recommendations
        organic_keywords = landscape.get('organic_strength', {}).get('keywords', 0)
        paid_keywords = landscape.get('paid_strength', {}).get('ad_keywords', 0)
        
        if organic_keywords > paid_keywords * 3:
            recommendations.append({
                "priority": "medium",
                "category": "Budget Allocation",
                "title": "Increase Paid Search Investment",
                "description": f"Strong organic presence ({organic_keywords} keywords) vs limited paid presence ({paid_keywords} keywords). Consider expanding paid campaigns."
            })
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _generate_competitive_summary(self, score: int, landscape: Dict, keyword_analysis: Dict) -> str:
        """Generate summary of competitive analysis."""
        market_position = landscape.get('market_position', 'Unknown')
        competitive_intensity = landscape.get('competitive_intensity', 'Unknown')
        opportunities = keyword_analysis.get('total_opportunities', 0)
        
        if score >= 80:
            return f"Strong competitive position as {market_position.lower()} with {opportunities} keyword opportunities in a {competitive_intensity.lower()} intensity market."
        elif score >= 60:
            return f"Solid competitive foundation as {market_position.lower()} with room for growth. {opportunities} keyword gaps identified."
        elif score >= 40:
            return f"Developing competitive presence as {market_position.lower()}. Significant opportunity with {opportunities} keyword gaps to pursue."
        else:
            return f"Early stage competitive position with substantial growth potential. {opportunities} keyword opportunities available for market entry."
    
    def _render_competitor_snapshot_html(self, report_data: Dict) -> str:
        """Render competitor snapshot report as HTML."""
        
        template_content = """<!DOCTYPE html>
<html>
<head>
    <title>Competitor Snapshot Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 20px; }
        .title { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; font-size: 16px; }
        .score-section { text-align: center; margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .score-circle { display: inline-block; width: 120px; height: 120px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto 15px; }
        .score-excellent { background: #27ae60; color: white; }
        .score-good { background: #f39c12; color: white; }
        .score-poor { background: #e74c3c; color: white; }
        .confidence { font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .summary { font-size: 18px; color: #2c3e50; margin: 20px 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }
        .card { background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; }
        .card-title { font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 15px; }
        .metric { display: flex; justify-content: space-between; margin: 8px 0; }
        .metric-label { color: #666; }
        .metric-value { font-weight: bold; color: #2c3e50; }
        .table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .table th { background: #f8f9fa; font-weight: bold; }
        .competitor-item { margin: 10px 0; padding: 15px; background: #f8f9fa; border-radius: 6px; }
        .domain { font-weight: bold; color: #2c3e50; }
        .relevance { color: #666; font-size: 14px; }
        .recommendation { margin: 15px 0; padding: 15px; border-left: 4px solid #3498db; background: #f8f9fa; }
        .rec-priority { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }
        .priority-high { background: #e74c3c; color: white; }
        .priority-medium { background: #f39c12; color: white; }
        .priority-low { background: #95a5a6; color: white; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">Competitor Snapshot Report</h1>
            <div class="subtitle">{{ website_title }} | {{ target_domain }}</div>
            <div class="subtitle">{{ analysis_date }}</div>
        </div>

        <div class="score-section">
            <div class="score-circle {% if overall_score >= 70 %}score-excellent{% elif overall_score >= 40 %}score-good{% else %}score-poor{% endif %}">
                {{ overall_score }}/100
            </div>
            <div class="confidence">{{ confidence }} Confidence</div>
            <div class="summary">{{ summary }}</div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-title">🔍 Organic Search Position</div>
                <div class="metric">
                    <span class="metric-label">Market Position:</span>
                    <span class="metric-value">{{ competitive_landscape.market_position }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Organic Keywords:</span>
                    <span class="metric-value">{{ "{:,}".format(competitive_landscape.organic_strength.keywords) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Organic Traffic:</span>
                    <span class="metric-value">{{ "{:,}".format(competitive_landscape.organic_strength.traffic) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Strength Score:</span>
                    <span class="metric-value">{{ competitive_landscape.organic_strength.score }}/100</span>
                </div>
            </div>

            <div class="card">
                <div class="card-title">💰 Paid Search Position</div>
                <div class="metric">
                    <span class="metric-label">Competitive Intensity:</span>
                    <span class="metric-value">{{ competitive_landscape.competitive_intensity }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Paid Keywords:</span>
                    <span class="metric-value">{{ "{:,}".format(competitive_landscape.paid_strength.ad_keywords) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Est. Competitor Spend:</span>
                    <span class="metric-value">${{ "{:,.0f}".format(competitive_landscape.paid_strength.estimated_spend) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Strength Score:</span>
                    <span class="metric-value">{{ competitive_landscape.paid_strength.score }}/100</span>
                </div>
            </div>

            <div class="card">
                <div class="card-title">🎯 Keyword Opportunities</div>
                <div class="metric">
                    <span class="metric-label">Total Opportunities:</span>
                    <span class="metric-value">{{ keyword_opportunities.total_opportunities }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">High-Value Gaps:</span>
                    <span class="metric-value">{{ keyword_opportunities.high_value_opportunities }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Avg Opportunity Score:</span>
                    <span class="metric-value">{{ "%.0f"|format(keyword_opportunities.avg_opportunity_score) }}/100</span>
                </div>
            </div>

            <div class="card">
                <div class="card-title">📢 Ad Intelligence</div>
                <div class="metric">
                    <span class="metric-label">Ad Copies Found:</span>
                    <span class="metric-value">{{ ad_intelligence.ad_copies_found }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Common Themes:</span>
                    <span class="metric-value">{{ ", ".join(ad_intelligence.common_themes[:3]) if ad_intelligence.common_themes else "None detected" }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Messaging Patterns:</span>
                    <span class="metric-value">{{ ad_intelligence.messaging_patterns|length }}</span>
                </div>
            </div>
        </div>

        <div style="margin: 40px 0;">
            <h3>🏆 Top Keyword Opportunities</h3>
            {% if keyword_opportunities.top_opportunities %}
            <table class="table">
                <thead>
                    <tr>
                        <th>Keyword</th>
                        <th>Search Volume</th>
                        <th>CPC</th>
                        <th>Competition</th>
                        <th>Opportunity Score</th>
                    </tr>
                </thead>
                <tbody>
                    {% for kw in keyword_opportunities.top_opportunities[:10] %}
                    <tr>
                        <td>{{ kw.keyword }}</td>
                        <td>{{ "{:,}".format(kw.search_volume) if kw.search_volume else "N/A" }}</td>
                        <td>${{ "%.2f"|format(kw.cpc) if kw.cpc else "N/A" }}</td>
                        <td>{{ "%.1f"|format(kw.competition * 100) if kw.competition else "N/A" }}%</td>
                        <td>{{ kw.opportunity_score }}/100</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No keyword opportunities identified.</p>
            {% endif %}
        </div>

        <div style="margin: 40px 0;">
            <h3>🏢 Key Competitors</h3>
            <div class="grid">
                {% for comp in competitive_landscape.organic_strength.top_competitors[:4] %}
                <div class="competitor-item">
                    <div class="domain">{{ comp.domain }}</div>
                    <div class="relevance">Relevance: {{ "%.0f"|format(comp.competitive_relevance * 100) }}%</div>
                    <div style="margin-top: 8px; font-size: 14px;">
                        <div>Keywords: {{ "{:,}".format(comp.common_keywords) }}</div>
                        <div>Traffic: {{ "{:,}".format(comp.organic_traffic) if comp.organic_traffic else "N/A" }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        {% if recommendations %}
        <div style="margin: 40px 0;">
            <h3>💡 Strategic Recommendations</h3>
            {% for rec in recommendations %}
            <div class="recommendation">
                <span class="rec-priority priority-{{ rec.priority }}">{{ rec.priority }} priority</span>
                <div style="font-weight: bold; margin: 8px 0;">{{ rec.title }}</div>
                <div>{{ rec.description }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="footer">
            <p>Report generated by Synter Digital Marketing Intelligence Platform</p>
            <p>Powered by SEMrush competitive intelligence</p>
        </div>
    </div>
</body>
</html>"""

        try:
            template = Template(template_content)
            return template.render(**report_data)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return f"<html><body><h1>Competitor Snapshot Report</h1><p>Score: {report_data.get('overall_score', 0)}/100</p><p>Domain: {report_data.get('target_domain')}</p></body></html>"
    
    def _create_input_hash(self, domain: str) -> str:
        """Create input hash for caching."""
        import hashlib
        input_str = f"COMPETITOR_SNAPSHOT:{domain}"
        return hashlib.sha256(input_str.encode()).hexdigest()
    
    def _create_error_report(self, report_id: str, error_msg: str, user_id: str, workspace_id: str) -> Dict:
        """Create error report."""
        return {
            "id": report_id,
            "report_type": "COMPETITOR_SNAPSHOT",
            "title": "Competitor Snapshot Report - Generation Failed",
            "summary": f"Report generation failed: {error_msg}",
            "status": "failed",
            "credit_cost": 0,  # Don't charge for failed reports
            "user_id": user_id,
            "workspace_id": workspace_id
        }
