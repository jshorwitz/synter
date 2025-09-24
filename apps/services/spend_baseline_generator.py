import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from jinja2 import Template
import uuid
from services.google_ads_connector import GoogleAdsConnector
from services.meta_ads_connector import MetaAdsConnector

logger = logging.getLogger(__name__)

class SpendBaselineGenerator:
    """Generate spend baseline reports from connected ad accounts."""
    
    def __init__(self):
        self.google_ads = GoogleAdsConnector()
        self.meta_ads = MetaAdsConnector()
        self.report_templates_dir = os.path.join(os.path.dirname(__file__), 'report_templates')
        os.makedirs(self.report_templates_dir, exist_ok=True)
    
    async def generate_spend_baseline_report(
        self, 
        ad_accounts: List[Dict],
        days: int = 90,
        user_id: str = "system",
        workspace_id: str = "default"
    ) -> Dict:
        """Generate spend baseline report from connected ad accounts."""
        
        logger.info(f"Generating spend baseline report for {len(ad_accounts)} accounts")
        
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())
        
        try:
            # Calculate date range
            end_date = date.today() - timedelta(days=1)
            start_date = end_date - timedelta(days=days-1)
            
            # Collect spend data from all accounts
            all_spend_data = []
            account_summaries = []
            
            for account in ad_accounts:
                account_data = await self._get_account_spend_data(account, start_date, end_date)
                if account_data:
                    all_spend_data.extend(account_data['spend_data'])
                    account_summaries.append(account_data['summary'])
            
            if not all_spend_data:
                logger.warning("No spend data available for baseline report")
                return self._create_no_data_report(report_id, user_id, workspace_id)
            
            # Analyze spend patterns
            analysis = self._analyze_spend_baseline(all_spend_data, account_summaries, days)
            
            # Generate report content
            report_data = {
                "accounts_analyzed": len(ad_accounts),
                "date_range": f"{start_date} to {end_date}",
                "analysis_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "summary": analysis['summary'],
                "platform_breakdown": analysis['platform_breakdown'],
                "spend_trends": analysis['spend_trends'],
                "performance_metrics": analysis['performance_metrics'],
                "recommendations": analysis['recommendations'],
                "account_summaries": account_summaries
            }
            
            # Render HTML report
            html_content = self._render_spend_baseline_html(report_data)
            
            # Calculate generation time
            generation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Create input hash
            input_hash = self._create_input_hash(ad_accounts, days)
            
            # Create report record
            report = {
                "id": report_id,
                "report_type": "SPEND_BASELINE",
                "website_id": None,  # Not tied to specific website
                "input_hash": input_hash,
                "title": f"Spend Baseline Report - {len(ad_accounts)} Account(s)",
                "summary": analysis['summary'],
                "data_json": json.dumps(report_data),
                "overall_score": analysis['overall_score'],
                "confidence": analysis['confidence'],
                "html_content": html_content,
                "status": "ready",
                "generation_time_ms": generation_time_ms,
                "credit_cost": 2,
                "user_id": user_id,
                "workspace_id": workspace_id
            }
            
            logger.info(f"Spend baseline report generated: {report_id} (score: {analysis['overall_score']})")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate spend baseline report: {e}")
            return self._create_error_report(report_id, str(e), user_id, workspace_id)
    
    async def _get_account_spend_data(self, account: Dict, start_date: date, end_date: date) -> Optional[Dict]:
        """Get spend data for a single account."""
        try:
            platform = account['platform'].lower()
            account_id = account['account_id']
            
            if platform == 'google':
                connector = self.google_ads
                spend_data = await connector.get_spend_data(
                    account.get('refresh_token', ''), account_id, start_date, end_date
                )
                campaigns = await connector.get_campaigns_summary(
                    account.get('refresh_token', ''), account_id, 
                    (end_date - start_date).days + 1
                )
                
            elif platform == 'meta':
                connector = self.meta_ads
                spend_data = await connector.get_spend_data(
                    account.get('access_token', ''), account_id, start_date, end_date
                )
                campaigns = await connector.get_campaigns_summary(
                    account.get('access_token', ''), account_id,
                    (end_date - start_date).days + 1
                )
                
            else:
                logger.warning(f"Unsupported platform: {platform}")
                return None
            
            # Calculate summary metrics
            total_spend = sum(record['spend'] for record in spend_data)
            total_impressions = sum(record['impressions'] for record in spend_data)
            total_clicks = sum(record['clicks'] for record in spend_data)
            total_conversions = sum(record['conversions'] for record in spend_data)
            
            summary = {
                "account_id": account_id,
                "account_name": account.get('account_name', f"{platform.title()} Account"),
                "platform": platform,
                "total_spend": round(total_spend, 2),
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": round(total_conversions, 2),
                "avg_daily_spend": round(total_spend / len(set(r['date'] for r in spend_data)), 2) if spend_data else 0,
                "overall_cpc": round(total_spend / total_clicks, 2) if total_clicks > 0 else 0,
                "overall_ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
                "overall_cpa": round(total_spend / total_conversions, 2) if total_conversions > 0 else 0,
                "campaigns_count": len(campaigns),
                "active_days": len(set(r['date'] for r in spend_data))
            }
            
            return {
                "spend_data": spend_data,
                "summary": summary,
                "campaigns": campaigns
            }
            
        except Exception as e:
            logger.error(f"Failed to get spend data for account {account.get('account_id')}: {e}")
            return None
    
    def _analyze_spend_baseline(self, all_spend_data: List[Dict], account_summaries: List[Dict], days: int) -> Dict:
        """Analyze spend baseline and generate insights."""
        
        # Platform breakdown
        platform_totals = {}
        for summary in account_summaries:
            platform = summary['platform']
            if platform not in platform_totals:
                platform_totals[platform] = {
                    'accounts': 0,
                    'total_spend': 0,
                    'total_impressions': 0,
                    'total_clicks': 0,
                    'total_conversions': 0
                }
            
            platform_totals[platform]['accounts'] += 1
            platform_totals[platform]['total_spend'] += summary['total_spend']
            platform_totals[platform]['total_impressions'] += summary['total_impressions']
            platform_totals[platform]['total_clicks'] += summary['total_clicks']
            platform_totals[platform]['total_conversions'] += summary['total_conversions']
        
        # Calculate platform metrics
        platform_breakdown = []
        total_spend_all = sum(p['total_spend'] for p in platform_totals.values())
        
        for platform, totals in platform_totals.items():
            spend_share = (totals['total_spend'] / total_spend_all * 100) if total_spend_all > 0 else 0
            avg_cpc = totals['total_spend'] / totals['total_clicks'] if totals['total_clicks'] > 0 else 0
            avg_ctr = totals['total_clicks'] / totals['total_impressions'] * 100 if totals['total_impressions'] > 0 else 0
            avg_cpa = totals['total_spend'] / totals['total_conversions'] if totals['total_conversions'] > 0 else 0
            
            platform_breakdown.append({
                'platform': platform.title(),
                'accounts': totals['accounts'],
                'total_spend': round(totals['total_spend'], 2),
                'spend_share': round(spend_share, 1),
                'avg_cpc': round(avg_cpc, 2),
                'avg_ctr': round(avg_ctr, 2),
                'avg_cpa': round(avg_cpa, 2),
                'total_conversions': round(totals['total_conversions'], 2)
            })
        
        # Spend trends (weekly aggregation)
        spend_trends = self._calculate_spend_trends(all_spend_data)
        
        # Performance benchmarks
        performance_metrics = self._calculate_performance_benchmarks(account_summaries)
        
        # Generate recommendations
        recommendations = self._generate_spend_recommendations(platform_breakdown, performance_metrics)
        
        # Calculate overall score and confidence
        overall_score = self._calculate_baseline_score(platform_breakdown, performance_metrics, days)
        confidence = "HIGH" if len(account_summaries) >= 2 and total_spend_all > 1000 else "MEDIUM" if len(account_summaries) >= 1 else "LOW"
        
        # Generate summary
        if overall_score >= 80:
            summary = f"Strong advertising baseline with ${total_spend_all:,.0f} total spend across {len(account_summaries)} account(s)."
        elif overall_score >= 60:
            summary = f"Good advertising foundation with ${total_spend_all:,.0f} spend, some optimization opportunities."
        else:
            summary = f"Early stage advertising with ${total_spend_all:,.0f} spend, significant growth potential."
        
        return {
            "overall_score": overall_score,
            "confidence": confidence,
            "summary": summary,
            "platform_breakdown": platform_breakdown,
            "spend_trends": spend_trends,
            "performance_metrics": performance_metrics,
            "recommendations": recommendations
        }
    
    def _calculate_spend_trends(self, spend_data: List[Dict]) -> List[Dict]:
        """Calculate weekly spend trends."""
        # Group by week
        weekly_data = {}
        
        for record in spend_data:
            record_date = record['date']
            # Get week start (Monday)
            week_start = record_date - timedelta(days=record_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    'week_start': week_start,
                    'total_spend': 0,
                    'total_clicks': 0,
                    'total_conversions': 0
                }
            
            weekly_data[week_key]['total_spend'] += record['spend']
            weekly_data[week_key]['total_clicks'] += record['clicks']
            weekly_data[week_key]['total_conversions'] += record['conversions']
        
        # Convert to sorted list
        trends = []
        for week_key in sorted(weekly_data.keys()):
            week_data = weekly_data[week_key]
            trends.append({
                'week_start': week_data['week_start'].strftime('%Y-%m-%d'),
                'total_spend': round(week_data['total_spend'], 2),
                'total_clicks': week_data['total_clicks'],
                'total_conversions': round(week_data['total_conversions'], 2)
            })
        
        return trends[-12:]  # Last 12 weeks
    
    def _calculate_performance_benchmarks(self, account_summaries: List[Dict]) -> Dict:
        """Calculate performance benchmarks across all accounts."""
        if not account_summaries:
            return {}
        
        # Aggregate metrics
        total_spend = sum(acc['total_spend'] for acc in account_summaries)
        total_clicks = sum(acc['total_clicks'] for acc in account_summaries)
        total_impressions = sum(acc['total_impressions'] for acc in account_summaries)
        total_conversions = sum(acc['total_conversions'] for acc in account_summaries)
        
        # Calculate benchmarks
        avg_cpc = total_spend / total_clicks if total_clicks > 0 else 0
        avg_ctr = total_clicks / total_impressions * 100 if total_impressions > 0 else 0
        avg_cpa = total_spend / total_conversions if total_conversions > 0 else 0
        conversion_rate = total_conversions / total_clicks * 100 if total_clicks > 0 else 0
        
        # Platform-specific performance
        platform_performance = {}
        for summary in account_summaries:
            platform = summary['platform']
            if platform not in platform_performance:
                platform_performance[platform] = []
            platform_performance[platform].append({
                'cpc': summary['overall_cpc'],
                'ctr': summary['overall_ctr'], 
                'cpa': summary['overall_cpa']
            })
        
        return {
            "total_spend": round(total_spend, 2),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "total_conversions": round(total_conversions, 2),
            "avg_cpc": round(avg_cpc, 2),
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpa": round(avg_cpa, 2),
            "conversion_rate": round(conversion_rate, 2),
            "avg_daily_spend": round(total_spend / (account_summaries[0]['active_days'] if account_summaries and account_summaries[0].get('active_days') else 1), 2),
            "platform_performance": platform_performance
        }
    
    def _generate_spend_recommendations(self, platform_breakdown: List[Dict], performance_metrics: Dict) -> List[Dict]:
        """Generate recommendations based on spend analysis."""
        recommendations = []
        
        total_spend = performance_metrics.get('total_spend', 0)
        avg_cpa = performance_metrics.get('avg_cpa', 0)
        avg_ctr = performance_metrics.get('avg_ctr', 0)
        
        # Budget allocation recommendations
        if len(platform_breakdown) > 1:
            # Find best performing platform
            best_platform = min(platform_breakdown, key=lambda x: x.get('avg_cpa', float('inf')))
            worst_platform = max(platform_breakdown, key=lambda x: x.get('avg_cpa', 0))
            
            if best_platform['avg_cpa'] > 0 and worst_platform['avg_cpa'] > best_platform['avg_cpa'] * 1.5:
                recommendations.append({
                    "priority": "high",
                    "category": "Budget Allocation",
                    "title": f"Shift Budget to {best_platform['platform']}",
                    "description": f"{best_platform['platform']} has {worst_platform['avg_cpa']/best_platform['avg_cpa']:.1f}x better CPA than {worst_platform['platform']}. Consider reallocating 20% of budget."
                })
        
        # Performance improvement recommendations
        if avg_ctr < 2.0:
            recommendations.append({
                "priority": "medium",
                "category": "Performance",
                "title": "Improve Click-Through Rates",
                "description": f"Average CTR of {avg_ctr:.1f}% is below industry average. Consider refreshing ad copy and testing new creatives."
            })
        
        if avg_cpa > 100:
            recommendations.append({
                "priority": "high", 
                "category": "Cost Efficiency",
                "title": "Optimize Cost Per Acquisition",
                "description": f"Average CPA of ${avg_cpa:.2f} suggests room for optimization. Review targeting, bidding strategies, and landing page experience."
            })
        
        # Budget recommendations
        if total_spend < 500:
            recommendations.append({
                "priority": "medium",
                "category": "Growth",
                "title": "Consider Budget Increase",
                "description": f"Current spend of ${total_spend:.0f} may limit reach. Test 20-30% budget increases on best-performing campaigns."
            })
        elif total_spend > 10000:
            recommendations.append({
                "priority": "low",
                "category": "Scale",
                "title": "Optimize for Scale",
                "description": f"High spend volume of ${total_spend:.0f} detected. Focus on automated bidding and audience expansion."
            })
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _calculate_baseline_score(self, platform_breakdown: List[Dict], performance_metrics: Dict, days: int) -> int:
        """Calculate overall baseline score."""
        score = 50  # Start at neutral
        
        # Multi-platform bonus
        if len(platform_breakdown) >= 2:
            score += 15
        elif len(platform_breakdown) == 1:
            score += 5
        
        # Spend volume (higher spend = more data = higher confidence)
        total_spend = performance_metrics.get('total_spend', 0)
        if total_spend >= 5000:
            score += 20
        elif total_spend >= 1000:
            score += 15
        elif total_spend >= 500:
            score += 10
        elif total_spend >= 100:
            score += 5
        
        # Performance quality
        avg_ctr = performance_metrics.get('avg_ctr', 0)
        avg_cpa = performance_metrics.get('avg_cpa', 0)
        
        if avg_ctr >= 3.0:
            score += 10
        elif avg_ctr >= 2.0:
            score += 5
        
        if avg_cpa > 0 and avg_cpa <= 50:
            score += 10
        elif avg_cpa <= 100:
            score += 5
        
        # Data recency bonus
        if days >= 90:
            score += 5
        
        return min(100, max(0, score))
    
    def _create_input_hash(self, ad_accounts: List[Dict], days: int) -> str:
        """Create input hash for caching."""
        import hashlib
        input_str = f"SPEND_BASELINE:{json.dumps(sorted([acc.get('account_id', '') for acc in ad_accounts]))}:{days}"
        return hashlib.sha256(input_str.encode()).hexdigest()
    
    def _render_spend_baseline_html(self, report_data: Dict) -> str:
        """Render spend baseline report as HTML."""
        template_content = """<!DOCTYPE html>
<html>
<head>
    <title>Spend Baseline Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }
        .header { text-align: center; margin-bottom: 30px; }
        .score { font-size: 48px; font-weight: bold; color: {% if overall_score >= 70 %}#27ae60{% elif overall_score >= 40 %}#f39c12{% else %}#e74c3c{% endif %}; }
        .summary { font-size: 18px; margin: 20px 0; text-align: center; }
        .section { margin: 30px 0; }
        .section-title { font-size: 24px; color: #2c3e50; margin-bottom: 15px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 28px; font-weight: bold; color: #2c3e50; }
        .metric-label { color: #666; font-size: 14px; margin-top: 5px; }
        .platform-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .platform-table th, .platform-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .platform-table th { background: #f8f9fa; font-weight: bold; }
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
            <h1>Spend Baseline Report</h1>
            <div class="score">{{ overall_score }}/100</div>
            <div>Confidence: {{ confidence }}</div>
            <div class="summary">{{ summary }}</div>
            <p>Analysis Period: {{ date_range }} | {{ accounts_analyzed }} Account(s)</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">Performance Overview</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">${{ "%.0f"|format(performance_metrics.total_spend) }}</div>
                    <div class="metric-label">Total Spend</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{{ "%.1f"|format(performance_metrics.avg_ctr) }}%</div>
                    <div class="metric-label">Avg CTR</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${{ "%.2f"|format(performance_metrics.avg_cpc) }}</div>
                    <div class="metric-label">Avg CPC</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${{ "%.0f"|format(performance_metrics.avg_cpa) }}</div>
                    <div class="metric-label">Avg CPA</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Platform Breakdown</h2>
            <table class="platform-table">
                <thead>
                    <tr>
                        <th>Platform</th>
                        <th>Accounts</th>
                        <th>Total Spend</th>
                        <th>Share</th>
                        <th>Avg CPC</th>
                        <th>Avg CTR</th>
                        <th>Avg CPA</th>
                    </tr>
                </thead>
                <tbody>
                    {% for platform in platform_breakdown %}
                    <tr>
                        <td><strong>{{ platform.platform }}</strong></td>
                        <td>{{ platform.accounts }}</td>
                        <td>${{ "%.0f"|format(platform.total_spend) }}</td>
                        <td>{{ "%.1f"|format(platform.spend_share) }}%</td>
                        <td>${{ "%.2f"|format(platform.avg_cpc) }}</td>
                        <td>{{ "%.1f"|format(platform.avg_ctr) }}%</td>
                        <td>${{ "%.0f"|format(platform.avg_cpa) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        {% if recommendations %}
        <div class="section">
            <h2 class="section-title">Recommendations</h2>
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
            <p>{{ analysis_date }}</p>
        </div>
    </div>
</body>
</html>"""

        try:
            template = Template(template_content)
            return template.render(**report_data)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            return f"<html><body><h1>Spend Baseline Report</h1><p>Score: {report_data.get('overall_score', 0)}/100</p></body></html>"
    
    def _create_no_data_report(self, report_id: str, user_id: str, workspace_id: str) -> Dict:
        """Create report when no data is available."""
        return {
            "id": report_id,
            "report_type": "SPEND_BASELINE",
            "title": "Spend Baseline Report - No Data Available",
            "summary": "No connected ad accounts with spend data found.",
            "overall_score": 0,
            "confidence": "LOW",
            "status": "ready",
            "html_content": "<html><body><h1>No Spend Data Available</h1><p>Connect ad accounts to generate spend baseline report.</p></body></html>",
            "credit_cost": 2,
            "user_id": user_id,
            "workspace_id": workspace_id
        }
    
    def _create_error_report(self, report_id: str, error_msg: str, user_id: str, workspace_id: str) -> Dict:
        """Create error report."""
        return {
            "id": report_id,
            "report_type": "SPEND_BASELINE",
            "title": "Spend Baseline Report - Generation Failed",
            "summary": f"Report generation failed: {error_msg}",
            "status": "failed",
            "credit_cost": 0,  # Don't charge for failed reports
            "user_id": user_id,
            "workspace_id": workspace_id
        }
