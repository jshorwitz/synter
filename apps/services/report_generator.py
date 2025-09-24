import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader
import markdown
from models import Report, Website
import uuid

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generate various types of reports for website analysis."""
    
    def __init__(self):
        self.report_templates_dir = os.path.join(os.path.dirname(__file__), 'report_templates')
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.report_templates_dir),
            autoescape=True
        )
        # Create templates directory if it doesn't exist
        os.makedirs(self.report_templates_dir, exist_ok=True)
    
    def create_input_hash(self, report_type: str, input_data: Dict) -> str:
        """Create a hash of input data for deduplication."""
        # Create a consistent string representation of the input
        input_str = f"{report_type}:{json.dumps(input_data, sort_keys=True)}"
        return hashlib.sha256(input_str.encode()).hexdigest()
    
    async def generate_tracking_readiness_report(
        self, 
        website_data: Dict, 
        user_id: str = "system", 
        workspace_id: str = "default"
    ) -> Dict:
        """Generate a tracking readiness report for a website."""
        
        logger.info(f"Generating tracking readiness report for {website_data.get('url')}")
        
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())
        
        try:
            # Calculate input hash for deduplication
            input_hash = self.create_input_hash("TRACKING_READINESS", {
                "url": website_data.get('url'),
                "technologies": website_data.get('technologies', {}),
                "tracking_pixels": website_data.get('tracking_pixels', [])
            })
            
            # Analyze tracking readiness
            analysis = self._analyze_tracking_readiness(website_data)
            
            # Generate report content
            report_data = {
                "website_url": website_data.get('url'),
                "website_title": website_data.get('title', 'Unknown Website'),
                "analysis_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "summary": analysis['summary'],
                "sections": analysis['sections'],
                "recommendations": analysis['recommendations'],
                "technologies": website_data.get('technologies', {}),
                "tracking_pixels": website_data.get('tracking_pixels', [])
            }
            
            # Render HTML report
            html_content = self._render_tracking_readiness_html(report_data)
            
            # Calculate generation time
            generation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Create report record
            report = {
                "id": report_id,
                "report_type": "TRACKING_READINESS",
                "website_id": website_data.get('id'),
                "input_hash": input_hash,
                "title": f"Tracking Readiness Report - {website_data.get('title', 'Website')}",
                "summary": analysis['summary'],
                "data_json": json.dumps(report_data),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "html_content": html_content,
                "status": "ready",
                "generation_time_ms": generation_time_ms,
                "credit_cost": 1,
                "user_id": user_id,
                "workspace_id": workspace_id
            }
            
            logger.info(f"Tracking readiness report generated: {report_id} (score: {analysis['overall_score']})")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate tracking readiness report: {e}")
            return {
                "id": report_id,
                "report_type": "TRACKING_READINESS", 
                "input_hash": "error",
                "title": "Report Generation Failed",
                "summary": f"Error generating report: {str(e)}",
                "status": "failed",
                "user_id": user_id,
                "workspace_id": workspace_id
            }
    
    def _analyze_tracking_readiness(self, website_data: Dict) -> Dict:
        """Analyze tracking readiness based on detected technologies and pixels."""
        
        technologies = website_data.get('technologies', {})
        tracking_pixels = website_data.get('tracking_pixels', [])
        
        # Initialize scoring
        score = 0
        max_score = 100
        sections = []
        recommendations = []
        
        # 1. Analytics Tracking (40 points)
        analytics_score = 0
        analytics_found = []
        
        analytics_tools = ['Google Analytics', 'Adobe Analytics', 'Mixpanel', 'Amplitude', 'Hotjar']
        for category, tools in technologies.items():
            if 'analytics' in category.lower():
                for tool in tools:
                    if any(analytics_tool.lower() in tool.lower() for analytics_tool in analytics_tools):
                        analytics_found.append(tool)
                        analytics_score += 15
        
        # Check tracking pixels for analytics
        for pixel in tracking_pixels:
            if 'analytics' in pixel.lower():
                analytics_found.append(pixel)
                analytics_score += 10
        
        analytics_score = min(analytics_score, 40)  # Cap at 40 points
        score += analytics_score
        
        sections.append({
            "title": "Analytics Tracking",
            "score": analytics_score,
            "max_score": 40,
            "status": "excellent" if analytics_score >= 30 else "good" if analytics_score >= 15 else "poor",
            "details": f"Found {len(analytics_found)} analytics tools: {', '.join(analytics_found[:3])}" if analytics_found else "No analytics tracking detected",
            "items": analytics_found
        })
        
        if analytics_score < 15:
            recommendations.append({
                "priority": "high",
                "category": "Analytics",
                "title": "Install Web Analytics",
                "description": "Add Google Analytics 4 or similar analytics tracking to measure website performance"
            })
        
        # 2. Conversion Tracking (35 points)
        conversion_score = 0
        conversion_found = []
        
        conversion_pixels = ['Facebook Pixel', 'Google Ads', 'LinkedIn Insight', 'Twitter Pixel', 'TikTok Pixel']
        for pixel in tracking_pixels:
            for conv_pixel in conversion_pixels:
                if conv_pixel.lower() in pixel.lower():
                    conversion_found.append(pixel)
                    conversion_score += 12
        
        # Check technologies for conversion tracking
        for category, tools in technologies.items():
            if any(word in category.lower() for word in ['advertising', 'marketing', 'conversion']):
                conversion_found.extend(tools)
                conversion_score += 8
        
        conversion_score = min(conversion_score, 35)  # Cap at 35 points
        score += conversion_score
        
        sections.append({
            "title": "Conversion Tracking", 
            "score": conversion_score,
            "max_score": 35,
            "status": "excellent" if conversion_score >= 25 else "good" if conversion_score >= 12 else "poor",
            "details": f"Found {len(conversion_found)} conversion tracking tools" if conversion_found else "No conversion tracking detected",
            "items": conversion_found
        })
        
        if conversion_score < 12:
            recommendations.append({
                "priority": "high",
                "category": "Conversion Tracking",
                "title": "Setup Conversion Pixels", 
                "description": "Install Facebook Pixel, Google Ads tracking, or other platform pixels to track conversions"
            })
        
        # 3. Technical Implementation (25 points)
        technical_score = 0
        technical_items = []
        
        # Check for tag management
        tag_managers = ['Google Tag Manager', 'Tealium', 'Adobe Launch']
        for category, tools in technologies.items():
            for tool in tools:
                if any(tm.lower() in tool.lower() for tm in tag_managers):
                    technical_items.append(f"Tag Manager: {tool}")
                    technical_score += 10
        
        # Check for consent management
        consent_tools = ['OneTrust', 'Cookiebot', 'TrustArc']
        for category, tools in technologies.items():
            for tool in tools:
                if any(ct.lower() in tool.lower() for ct in consent_tools):
                    technical_items.append(f"Consent Management: {tool}")
                    technical_score += 8
        
        # Check for ecommerce tracking
        ecommerce_platforms = ['Shopify', 'WooCommerce', 'Magento', 'BigCommerce']
        for category, tools in technologies.items():
            for tool in tools:
                if any(ec.lower() in tool.lower() for ec in ecommerce_platforms):
                    technical_items.append(f"E-commerce Platform: {tool}")
                    technical_score += 7
        
        technical_score = min(technical_score, 25)  # Cap at 25 points
        score += technical_score
        
        sections.append({
            "title": "Technical Implementation",
            "score": technical_score,
            "max_score": 25,
            "status": "excellent" if technical_score >= 20 else "good" if technical_score >= 10 else "poor",
            "details": f"Found {len(technical_items)} technical implementations" if technical_items else "Basic technical setup",
            "items": technical_items
        })
        
        if technical_score < 10:
            recommendations.append({
                "priority": "medium",
                "category": "Technical Setup",
                "title": "Implement Tag Management",
                "description": "Setup Google Tag Manager to centralize tracking code management"
            })
        
        # Determine overall confidence based on data quality
        if len(technologies) > 3 and len(tracking_pixels) > 2:
            confidence = "HIGH"
        elif len(technologies) > 1 or len(tracking_pixels) > 1:
            confidence = "MEDIUM"  
        else:
            confidence = "LOW"
        
        # Generate summary
        if score >= 80:
            summary = "Excellent tracking setup with comprehensive analytics and conversion tracking."
        elif score >= 60:
            summary = "Good tracking foundation with some areas for improvement."
        elif score >= 40:
            summary = "Basic tracking in place but missing key components for optimal measurement."
        else:
            summary = "Limited tracking setup - significant improvements needed for effective measurement."
        
        return {
            "overall_score": score,
            "confidence": confidence,
            "summary": summary,
            "sections": sections,
            "recommendations": recommendations[:5]  # Top 5 recommendations
        }
    
    def _render_tracking_readiness_html(self, report_data: Dict) -> str:
        """Render tracking readiness report as HTML."""
        
        # Create template if it doesn't exist
        template_path = os.path.join(self.report_templates_dir, 'tracking_readiness.html')
        if not os.path.exists(template_path):
            self._create_tracking_readiness_template(template_path)
        
        try:
            template = self.jinja_env.get_template('tracking_readiness.html')
            return template.render(**report_data)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            # Fallback to simple HTML
            return self._render_simple_html_fallback(report_data)
    
    def _create_tracking_readiness_template(self, template_path: str):
        """Create the tracking readiness HTML template."""
        
        template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #eee; }
        .title { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; font-size: 16px; }
        .score-section { text-align: center; margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .score-circle { display: inline-block; width: 120px; height: 120px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto 15px; }
        .score-excellent { background: #27ae60; color: white; }
        .score-good { background: #f39c12; color: white; }
        .score-poor { background: #e74c3c; color: white; }
        .confidence { font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .summary { font-size: 18px; color: #2c3e50; margin: 20px 0; text-align: center; }
        .section { margin: 30px 0; padding: 20px; border: 1px solid #eee; border-radius: 8px; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .section-title { font-size: 20px; color: #2c3e50; margin: 0; }
        .section-score { font-weight: bold; padding: 5px 12px; border-radius: 20px; }
        .status-excellent { background: #d4edda; color: #155724; }
        .status-good { background: #fff3cd; color: #856404; }
        .status-poor { background: #f8d7da; color: #721c24; }
        .section-details { color: #666; margin: 10px 0; }
        .items-list { list-style: none; padding: 0; margin: 15px 0; }
        .items-list li { background: #f8f9fa; padding: 8px 12px; margin: 5px 0; border-radius: 4px; }
        .recommendations { margin-top: 40px; }
        .recommendation { margin: 15px 0; padding: 15px; border-left: 4px solid #3498db; background: #f8f9fa; }
        .rec-title { font-weight: bold; color: #2c3e50; margin-bottom: 5px; }
        .rec-priority { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }
        .priority-high { background: #e74c3c; color: white; }
        .priority-medium { background: #f39c12; color: white; }
        .priority-low { background: #95a5a6; color: white; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">Tracking Readiness Report</h1>
            <div class="subtitle">{{ website_title }} | {{ analysis_date }}</div>
        </div>

        <div class="score-section">
            <div class="score-circle {% if overall_score >= 70 %}score-excellent{% elif overall_score >= 40 %}score-good{% else %}score-poor{% endif %}">
                {{ overall_score }}/100
            </div>
            <div class="confidence">{{ confidence }} Confidence</div>
            <div class="summary">{{ summary }}</div>
        </div>

        {% for section in sections %}
        <div class="section">
            <div class="section-header">
                <h3 class="section-title">{{ section.title }}</h3>
                <span class="section-score status-{{ section.status }}">{{ section.score }}/{{ section.max_score }}</span>
            </div>
            <div class="section-details">{{ section.details }}</div>
            {% if section.items %}
            <ul class="items-list">
                {% for item in section.items %}
                <li>{{ item }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
        {% endfor %}

        {% if recommendations %}
        <div class="recommendations">
            <h3>Recommendations</h3>
            {% for rec in recommendations %}
            <div class="recommendation">
                <span class="rec-priority priority-{{ rec.priority }}">{{ rec.priority }} priority</span>
                <div class="rec-title">{{ rec.title }}</div>
                <div>{{ rec.description }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="footer">
            <p>Report generated by Synter Digital Marketing Intelligence Platform</p>
            <p>Website: {{ website_url }}</p>
        </div>
    </div>
</body>
</html>"""

        with open(template_path, 'w') as f:
            f.write(template_content)
        
        logger.info(f"Created tracking readiness template: {template_path}")
    
    def _render_simple_html_fallback(self, report_data: Dict) -> str:
        """Simple HTML fallback when template rendering fails."""
        
        return f"""
        <html>
        <head><title>Tracking Readiness Report</title></head>
        <body>
        <h1>Tracking Readiness Report</h1>
        <h2>{report_data.get('website_title', 'Website')}</h2>
        <p><strong>Score:</strong> {report_data.get('overall_score', 0)}/100</p>
        <p><strong>Confidence:</strong> {report_data.get('confidence', 'Unknown')}</p>
        <p><strong>Summary:</strong> {report_data.get('summary', 'Analysis completed')}</p>
        <p><strong>Generated:</strong> {report_data.get('analysis_date', 'Unknown')}</p>
        </body>
        </html>
        """
