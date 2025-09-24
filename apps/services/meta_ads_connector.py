import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
import json
import requests

logger = logging.getLogger(__name__)

class MetaAdsConnector:
    """Meta (Facebook) Ads API connector for reading spend data."""
    
    def __init__(self):
        self.app_id = os.getenv('META_APP_ID')
        self.app_secret = os.getenv('META_APP_SECRET')
        self.api_version = os.getenv('META_API_VERSION', 'v18.0')
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.mock_mode = os.getenv('MOCK_META', 'true').lower() == 'true'
        
        if not self.mock_mode and not all([self.app_id, self.app_secret]):
            logger.warning("Meta Ads API credentials not found, using mock mode")
            self.mock_mode = True
        else:
            logger.info("Meta Ads API client configured" if not self.mock_mode else "Using Meta Ads mock mode")
    
    async def test_connection(self, access_token: str, account_id: str) -> Dict:
        """Test connection to Meta Ads API."""
        try:
            if self.mock_mode:
                return self._mock_test_connection(account_id)
            
            # Test API connection
            url = f"{self.base_url}/act_{account_id}"
            params = {
                'access_token': access_token,
                'fields': 'name,currency,account_status,timezone_name'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "success": True,
                "account_name": data.get('name', 'Unknown Account'),
                "account_id": account_id,
                "currency": data.get('currency', 'USD'),
                "timezone": data.get('timezone_name', 'UTC'),
                "status": "active" if data.get('account_status') == 1 else "inactive"
            }
            
        except Exception as e:
            logger.error(f"Meta Ads connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_account_info(self, access_token: str, account_id: str) -> Dict:
        """Get account information."""
        try:
            if self.mock_mode:
                return self._mock_account_info(account_id)
            
            url = f"{self.base_url}/act_{account_id}"
            params = {
                'access_token': access_token,
                'fields': 'name,currency,account_status,timezone_name,business_name'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "account_id": account_id,
                "account_name": data.get('name', 'Unknown Account'),
                "business_name": data.get('business_name'),
                "currency": data.get('currency', 'USD'),
                "timezone": data.get('timezone_name', 'UTC'),
                "status": "active" if data.get('account_status') == 1 else "inactive"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Meta Ads account info: {e}")
            return self._mock_account_info(account_id)
    
    async def get_spend_data(self, access_token: str, account_id: str, 
                           start_date: date, end_date: date) -> List[Dict]:
        """Get spend data for date range."""
        try:
            if self.mock_mode:
                return self._mock_spend_data(account_id, start_date, end_date)
            
            # Get insights from Meta Ads API
            url = f"{self.base_url}/act_{account_id}/insights"
            params = {
                'access_token': access_token,
                'time_range': json.dumps({
                    'since': start_date.strftime('%Y-%m-%d'),
                    'until': end_date.strftime('%Y-%m-%d')
                }),
                'time_increment': 1,  # Daily breakdown
                'level': 'adset',
                'fields': [
                    'date_start',
                    'campaign_id', 
                    'campaign_name',
                    'adset_id',
                    'adset_name',
                    'spend',
                    'impressions',
                    'clicks',
                    'actions'
                ],
                'limit': 1000
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            spend_data = []
            
            for record in data.get('data', []):
                # Extract conversions from actions array
                conversions = 0
                if 'actions' in record:
                    for action in record['actions']:
                        if action.get('action_type') in ['purchase', 'lead', 'complete_registration']:
                            conversions += float(action.get('value', 0))
                
                spend = float(record.get('spend', 0))
                impressions = int(record.get('impressions', 0))
                clicks = int(record.get('clicks', 0))
                
                # Calculate derived metrics
                cpm = (spend / impressions * 1000) if impressions > 0 else 0
                cpc = (spend / clicks) if clicks > 0 else 0
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
                cpa = (spend / conversions) if conversions > 0 else 0
                
                spend_record = {
                    "date": datetime.strptime(record['date_start'], '%Y-%m-%d').date(),
                    "campaign_id": record.get('campaign_id', ''),
                    "campaign_name": record.get('campaign_name', ''),
                    "ad_group_id": record.get('adset_id', ''),  # AdSet = Ad Group in Meta
                    "ad_group_name": record.get('adset_name', ''),
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "cpm": round(cpm, 2),
                    "cpc": round(cpc, 2),
                    "ctr": round(ctr, 2),
                    "conversion_rate": round(conversion_rate, 2),
                    "cpa": round(cpa, 2),
                    "currency": "USD"  # Would get from account info
                }
                
                spend_data.append(spend_record)
            
            logger.info(f"Retrieved {len(spend_data)} spend records from Meta Ads")
            return spend_data
            
        except Exception as e:
            logger.error(f"Failed to get Meta Ads spend data: {e}")
            return self._mock_spend_data(account_id, start_date, end_date)
    
    def _mock_test_connection(self, account_id: str) -> Dict:
        """Mock connection test for development."""
        return {
            "success": True,
            "account_name": f"Test Meta Ads Account {account_id[-4:]}",
            "account_id": account_id,
            "currency": "USD",
            "timezone": "America/Los_Angeles",
            "status": "active"
        }
    
    def _mock_account_info(self, account_id: str) -> Dict:
        """Mock account info for development."""
        return {
            "account_id": account_id,
            "account_name": f"Test Meta Ads Account {account_id[-4:]}",
            "business_name": f"Test Business {account_id[-4:]}",
            "currency": "USD",
            "timezone": "America/Los_Angeles",
            "status": "active"
        }
    
    def _mock_spend_data(self, account_id: str, start_date: date, end_date: date) -> List[Dict]:
        """Generate mock spend data for development."""
        spend_data = []
        
        # Generate daily data for the date range
        current_date = start_date
        campaign_id = f"meta_camp_{account_id[-4:]}_001"
        adset_id = f"meta_adset_{account_id[-4:]}_001"
        
        while current_date <= end_date:
            # Generate realistic mock data with some variation
            base_spend = 200 + (hash(str(current_date)) % 150)  # $200-350/day
            impressions = base_spend * 6  # ~$0.17 CPM (higher than Google)
            clicks = int(impressions * 0.015)  # 1.5% CTR (lower than Google)
            conversions = clicks * 0.08  # 8% conversion rate (higher than Google)
            
            spend_record = {
                "date": current_date,
                "campaign_id": campaign_id,
                "campaign_name": "Facebook Prospecting Campaign",
                "ad_group_id": adset_id,
                "ad_group_name": "Interest Targeting",
                "spend": round(base_spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": round(conversions, 2),
                "cpm": round(base_spend / impressions * 1000, 2),
                "cpc": round(base_spend / clicks, 2),
                "ctr": 1.5,
                "conversion_rate": 8.0,
                "cpa": round(base_spend / conversions, 2) if conversions > 0 else 0,
                "currency": "USD"
            }
            
            spend_data.append(spend_record)
            current_date += timedelta(days=1)
        
        # Add retargeting campaign
        current_date = start_date
        campaign_id_2 = f"meta_camp_{account_id[-4:]}_002"
        adset_id_2 = f"meta_adset_{account_id[-4:]}_002"
        
        while current_date <= end_date:
            base_spend = 100 + (hash(str(current_date + timedelta(days=2))) % 75)  # $100-175/day
            impressions = base_spend * 4  # Higher CPM for retargeting
            clicks = int(impressions * 0.025)  # Higher CTR for retargeting
            conversions = clicks * 0.12  # Higher conversion rate
            
            spend_record = {
                "date": current_date,
                "campaign_id": campaign_id_2,
                "campaign_name": "Facebook Retargeting Campaign",
                "ad_group_id": adset_id_2,
                "ad_group_name": "Website Visitors",
                "spend": round(base_spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": round(conversions, 2),
                "cpm": round(base_spend / impressions * 1000, 2),
                "cpc": round(base_spend / clicks, 2),
                "ctr": 2.5,
                "conversion_rate": 12.0,
                "cpa": round(base_spend / conversions, 2) if conversions > 0 else 0,
                "currency": "USD"
            }
            
            spend_data.append(spend_record)
            current_date += timedelta(days=1)
        
        logger.info(f"Generated {len(spend_data)} mock spend records for Meta Ads")
        return spend_data
    
    def create_account_id(self, account_id: str) -> str:
        """Create internal account ID."""
        return f"meta_ads_{account_id}"
    
    async def get_campaigns_summary(self, access_token: str, account_id: str, days: int = 30) -> List[Dict]:
        """Get campaign-level summary for the last N days."""
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=days-1)
        
        spend_data = await self.get_spend_data(access_token, account_id, start_date, end_date)
        
        # Aggregate by campaign
        campaigns = {}
        for record in spend_data:
            campaign_id = record['campaign_id']
            if campaign_id not in campaigns:
                campaigns[campaign_id] = {
                    'campaign_id': campaign_id,
                    'campaign_name': record['campaign_name'],
                    'total_spend': 0,
                    'total_impressions': 0,
                    'total_clicks': 0,
                    'total_conversions': 0,
                    'days_active': 0
                }
            
            campaigns[campaign_id]['total_spend'] += record['spend']
            campaigns[campaign_id]['total_impressions'] += record['impressions']
            campaigns[campaign_id]['total_clicks'] += record['clicks']
            campaigns[campaign_id]['total_conversions'] += record['conversions']
            campaigns[campaign_id]['days_active'] += 1
        
        # Calculate averages
        campaign_summary = []
        for campaign_data in campaigns.values():
            avg_daily_spend = campaign_data['total_spend'] / campaign_data['days_active']
            ctr = (campaign_data['total_clicks'] / campaign_data['total_impressions'] * 100) if campaign_data['total_impressions'] > 0 else 0
            cpc = campaign_data['total_spend'] / campaign_data['total_clicks'] if campaign_data['total_clicks'] > 0 else 0
            conversion_rate = (campaign_data['total_conversions'] / campaign_data['total_clicks'] * 100) if campaign_data['total_clicks'] > 0 else 0
            cpa = campaign_data['total_spend'] / campaign_data['total_conversions'] if campaign_data['total_conversions'] > 0 else 0
            
            campaign_summary.append({
                **campaign_data,
                'avg_daily_spend': round(avg_daily_spend, 2),
                'ctr': round(ctr, 2),
                'cpc': round(cpc, 2),
                'conversion_rate': round(conversion_rate, 2),
                'cpa': round(cpa, 2)
            })
        
        return campaign_summary
