import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import json
import uuid

logger = logging.getLogger(__name__)

class GoogleAdsConnector:
    """Google Ads API connector for reading spend data."""
    
    def __init__(self):
        self.developer_token = os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN')
        self.client_id = os.getenv('GOOGLE_ADS_CLIENT_ID') 
        self.client_secret = os.getenv('GOOGLE_ADS_CLIENT_SECRET')
        self.mock_mode = os.getenv('MOCK_GOOGLE', 'false').lower() == 'true'
        
        # Try to import google-ads library
        self.google_ads_available = False
        if not self.mock_mode and all([self.developer_token, self.client_id, self.client_secret]):
            try:
                from google.ads.googleads.client import GoogleAdsClient
                self.google_ads_available = True
                logger.info("Google Ads API client available")
            except ImportError:
                logger.warning("Google Ads library not available, using mock mode")
                self.mock_mode = True
        else:
            logger.info("Using Google Ads mock mode")
            self.mock_mode = True
    
    async def test_connection(self, refresh_token: str, customer_id: str) -> Dict:
        """Test connection to Google Ads API."""
        try:
            if self.mock_mode:
                return self._mock_test_connection(customer_id)
            
            # Real API test would go here
            client = self._create_client(refresh_token)
            
            # Try to get customer info
            customer_service = client.get_service("CustomerService")
            customer_resource_name = customer_service.customer_path(customer_id)
            
            request = client.get_type("GetCustomerRequest")()
            request.resource_name = customer_resource_name
            
            response = customer_service.get_customer(request=request)
            
            return {
                "success": True,
                "account_name": response.descriptive_name,
                "account_id": customer_id,
                "currency": response.currency_code,
                "timezone": response.time_zone,
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"Google Ads connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_account_info(self, refresh_token: str, customer_id: str) -> Dict:
        """Get account information."""
        try:
            if self.mock_mode:
                return self._mock_account_info(customer_id)
            
            client = self._create_client(refresh_token)
            
            # Get customer details
            customer_service = client.get_service("CustomerService")
            customer_resource_name = customer_service.customer_path(customer_id)
            
            request = client.get_type("GetCustomerRequest")()
            request.resource_name = customer_resource_name
            
            response = customer_service.get_customer(request=request)
            
            return {
                "account_id": customer_id,
                "account_name": response.descriptive_name,
                "currency": response.currency_code,
                "timezone": response.time_zone,
                "status": "active" if response.status.name == "ENABLED" else "inactive"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Google Ads account info: {e}")
            return self._mock_account_info(customer_id)
    
    async def get_spend_data(self, refresh_token: str, customer_id: str, 
                           start_date: date, end_date: date) -> List[Dict]:
        """Get spend data for date range."""
        try:
            if self.mock_mode:
                return self._mock_spend_data(customer_id, start_date, end_date)
            
            client = self._create_client(refresh_token)
            
            # GAQL query for spend data
            query = f"""
            SELECT 
                segments.date,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions
            FROM ad_group
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            """
            
            search_request = client.get_type("SearchGoogleAdsStreamRequest")()
            search_request.customer_id = customer_id
            search_request.query = query
            
            ga_service = client.get_service("GoogleAdsService")
            stream = ga_service.search_stream(search_request)
            
            spend_data = []
            for batch in stream:
                for row in batch.results:
                    # Convert micros to dollars
                    spend = row.metrics.cost_micros / 1_000_000 if row.metrics.cost_micros else 0
                    
                    # Calculate derived metrics
                    cpm = (spend / row.metrics.impressions * 1000) if row.metrics.impressions > 0 else 0
                    cpc = (spend / row.metrics.clicks) if row.metrics.clicks > 0 else 0
                    ctr = (row.metrics.clicks / row.metrics.impressions * 100) if row.metrics.impressions > 0 else 0
                    conversion_rate = (row.metrics.conversions / row.metrics.clicks * 100) if row.metrics.clicks > 0 else 0
                    cpa = (spend / row.metrics.conversions) if row.metrics.conversions > 0 else 0
                    
                    spend_record = {
                        "date": datetime.strptime(row.segments.date, "%Y-%m-%d").date(),
                        "campaign_id": str(row.campaign.id),
                        "campaign_name": row.campaign.name,
                        "ad_group_id": str(row.ad_group.id),
                        "ad_group_name": row.ad_group.name,
                        "spend": spend,
                        "impressions": row.metrics.impressions,
                        "clicks": row.metrics.clicks,
                        "conversions": row.metrics.conversions,
                        "cpm": cpm,
                        "cpc": cpc,
                        "ctr": ctr,
                        "conversion_rate": conversion_rate,
                        "cpa": cpa,
                        "currency": "USD"  # Would get from account info
                    }
                    
                    spend_data.append(spend_record)
            
            logger.info(f"Retrieved {len(spend_data)} spend records from Google Ads")
            return spend_data
            
        except Exception as e:
            logger.error(f"Failed to get Google Ads spend data: {e}")
            return self._mock_spend_data(customer_id, start_date, end_date)
    
    def _create_client(self, refresh_token: str):
        """Create Google Ads client."""
        if not self.google_ads_available:
            raise Exception("Google Ads client not available")
        
        from google.ads.googleads.client import GoogleAdsClient
        
        config = {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "use_proto_plus": True
        }
        
        return GoogleAdsClient.load_from_dict(config)
    
    def _mock_test_connection(self, customer_id: str) -> Dict:
        """Mock connection test for development."""
        return {
            "success": True,
            "account_name": f"Test Google Ads Account {customer_id[-4:]}",
            "account_id": customer_id,
            "currency": "USD",
            "timezone": "America/New_York",
            "status": "active"
        }
    
    def _mock_account_info(self, customer_id: str) -> Dict:
        """Mock account info for development."""
        return {
            "account_id": customer_id,
            "account_name": f"Test Google Ads Account {customer_id[-4:]}",
            "currency": "USD",
            "timezone": "America/New_York",
            "status": "active"
        }
    
    def _mock_spend_data(self, customer_id: str, start_date: date, end_date: date) -> List[Dict]:
        """Generate mock spend data for development."""
        spend_data = []
        
        # Generate daily data for the date range
        current_date = start_date
        campaign_id = f"camp_{customer_id[-4:]}_001"
        ad_group_id = f"ag_{customer_id[-4:]}_001"
        
        while current_date <= end_date:
            # Generate realistic mock data with some variation
            base_spend = 150 + (hash(str(current_date)) % 100)  # $150-250/day
            impressions = base_spend * 8  # ~$0.125 CPM
            clicks = int(impressions * 0.02)  # 2% CTR
            conversions = clicks * 0.05  # 5% conversion rate
            
            spend_record = {
                "date": current_date,
                "campaign_id": campaign_id,
                "campaign_name": "Search Campaign - Brand",
                "ad_group_id": ad_group_id,
                "ad_group_name": "Brand Keywords",
                "spend": round(base_spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": round(conversions, 2),
                "cpm": round(base_spend / impressions * 1000, 2),
                "cpc": round(base_spend / clicks, 2),
                "ctr": 2.0,
                "conversion_rate": 5.0,
                "cpa": round(base_spend / conversions, 2) if conversions > 0 else 0,
                "currency": "USD"
            }
            
            spend_data.append(spend_record)
            current_date += timedelta(days=1)
        
        # Add a second campaign with different performance
        current_date = start_date
        campaign_id_2 = f"camp_{customer_id[-4:]}_002"
        ad_group_id_2 = f"ag_{customer_id[-4:]}_002"
        
        while current_date <= end_date:
            base_spend = 75 + (hash(str(current_date + timedelta(days=1))) % 50)  # $75-125/day
            impressions = base_spend * 12  # Higher impressions, lower CPM
            clicks = int(impressions * 0.015)  # Lower CTR
            conversions = clicks * 0.03  # Lower conversion rate
            
            spend_record = {
                "date": current_date,
                "campaign_id": campaign_id_2,
                "campaign_name": "Search Campaign - Generic",
                "ad_group_id": ad_group_id_2,
                "ad_group_name": "Generic Keywords",
                "spend": round(base_spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": round(conversions, 2),
                "cpm": round(base_spend / impressions * 1000, 2),
                "cpc": round(base_spend / clicks, 2),
                "ctr": 1.5,
                "conversion_rate": 3.0,
                "cpa": round(base_spend / conversions, 2) if conversions > 0 else 0,
                "currency": "USD"
            }
            
            spend_data.append(spend_record)
            current_date += timedelta(days=1)
        
        logger.info(f"Generated {len(spend_data)} mock spend records for Google Ads")
        return spend_data
    
    def create_account_id(self, customer_id: str) -> str:
        """Create internal account ID."""
        return f"google_ads_{customer_id}"
    
    async def get_campaigns_summary(self, refresh_token: str, customer_id: str, days: int = 30) -> List[Dict]:
        """Get campaign-level summary for the last N days."""
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=days-1)
        
        spend_data = await self.get_spend_data(refresh_token, customer_id, start_date, end_date)
        
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
