import requests
import os
import logging
from typing import Dict, List
import json
from urllib.parse import urlparse
import asyncio

logger = logging.getLogger(__name__)

class CompetitorResearcher:
    """Research competitors using SimilarWeb and SEMrush APIs."""
    
    def __init__(self):
        self.similarweb_api_key = os.getenv('SIMILARWEB_API_KEY')
        self.semrush_api_key = os.getenv('SEMRUSH_API_KEY')
        self.mock_similarweb = os.getenv('MOCK_SIMILARWEB', 'false').lower() == 'true'
        self.mock_semrush = os.getenv('MOCK_SEMRUSH', 'false').lower() == 'true'
    
    async def find_competitors(self, url: str, industry: str = None, key_topics: List[str] = None) -> List[Dict]:
        """Find competitors for a given website."""
        logger.info(f"Finding competitors for {url}")
        
        domain = urlparse(url).netloc
        
        try:
            # Get competitive data from SimilarWeb
            similarweb_competitors = await self._get_similarweb_competitors(domain)
            
            # Get competitive data from SEMrush
            semrush_competitors = await self._get_semrush_competitors(domain)
            
            # Combine and deduplicate competitors
            all_competitors = {}
            
            # Add SimilarWeb competitors
            for comp in similarweb_competitors:
                domain = comp.get('domain', '')
                if domain and domain != urlparse(url).netloc:
                    all_competitors[domain] = {
                        'url': f"https://{domain}",
                        'name': comp.get('name', domain),
                        'traffic_rank': comp.get('rank'),
                        'monthly_visits': comp.get('visits'),
                        'traffic_sources': comp.get('traffic_sources', {}),
                        'competitive_score': comp.get('score', 50),
                        'source': 'similarweb'
                    }
            
            # Add SEMrush competitors
            for comp in semrush_competitors:
                domain = comp.get('domain', '')
                if domain and domain != urlparse(url).netloc:
                    if domain in all_competitors:
                        # Merge data
                        all_competitors[domain].update({
                            'organic_keywords': comp.get('organic_keywords'),
                            'paid_keywords': comp.get('paid_keywords'),
                            'estimated_budget': comp.get('estimated_budget'),
                        })
                    else:
                        all_competitors[domain] = {
                            'url': f"https://{domain}",
                            'name': comp.get('name', domain),
                            'organic_keywords': comp.get('organic_keywords'),
                            'paid_keywords': comp.get('paid_keywords'),
                            'estimated_budget': comp.get('estimated_budget'),
                            'competitive_score': comp.get('score', 50),
                            'source': 'semrush'
                        }
            
            # Analyze key differences (simplified)
            for competitor_data in all_competitors.values():
                competitor_data['key_differences'] = await self._analyze_differences(
                    url, competitor_data['url'], key_topics
                )
            
            return list(all_competitors.values())
            
        except Exception as e:
            logger.error(f"Competitor research failed for {url}: {e}")
            return []
    
    async def _get_similarweb_competitors(self, domain: str) -> List[Dict]:
        """Get competitors from SimilarWeb API."""
        if self.mock_similarweb or not self.similarweb_api_key:
            logger.info(f"Using mock SimilarWeb data for {domain}")
            return self._get_mock_similarweb_data(domain)
        
        try:
            # SimilarWeb Similar Sites API
            url = f"https://api.similarweb.com/v1/website/{domain}/similar-sites"
            headers = {
                'Api-Key': self.similarweb_api_key
            }
            params = {
                'main_domain_only': 'false',
                'format': 'json'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            competitors = []
            
            if 'similar_sites' in data:
                for site in data['similar_sites'][:10]:  # Top 10
                    competitors.append({
                        'domain': site.get('url'),
                        'name': site.get('url'),
                        'score': site.get('score', 0.5) * 100,  # Convert to 0-100 scale
                        'rank': site.get('rank'),
                        'visits': site.get('visits')
                    })
            
            return competitors
            
        except Exception as e:
            logger.error(f"SimilarWeb API error for {domain}: {e}")
            return self._get_mock_similarweb_data(domain)
    
    async def _get_semrush_competitors(self, domain: str) -> List[Dict]:
        """Get competitors from SEMrush API."""
        if self.mock_semrush or not self.semrush_api_key:
            logger.info(f"Using mock SEMrush data for {domain}")
            return self._get_mock_semrush_data(domain)
        
        try:
            # SEMrush Domain Competitors API
            url = "https://api.semrush.com/"
            params = {
                'type': 'domain_organic_organic',
                'key': self.semrush_api_key,
                'domain': domain,
                'display_limit': 10,
                'export_columns': 'Dn,Cr,Np,Ad,At,Ot'
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            # Parse CSV response
            lines = response.text.strip().split('\n')
            competitors = []
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 6:
                        competitors.append({
                            'domain': parts[0],
                            'name': parts[0],
                            'competitive_relevance': float(parts[1]) if parts[1] else 0,
                            'organic_keywords': int(parts[2]) if parts[2] else 0,
                            'paid_keywords': int(parts[3]) if parts[3] else 0,
                            'estimated_budget': float(parts[4]) if parts[4] else 0,
                            'traffic': int(parts[5]) if parts[5] else 0,
                            'score': float(parts[1]) * 10 if parts[1] else 50  # Scale relevance to 0-100
                        })
            
            return competitors
            
        except Exception as e:
            logger.error(f"SEMrush API error for {domain}: {e}")
            return self._get_mock_semrush_data(domain)
    
    def _get_mock_similarweb_data(self, domain: str) -> List[Dict]:
        """Generate mock SimilarWeb competitor data."""
        # Generate realistic competitors based on domain type
        base_competitors = []
        
        if any(term in domain for term in ['shop', 'store', 'ecommerce']):
            base_competitors = ['shopify.com', 'woocommerce.com', 'bigcommerce.com']
        elif any(term in domain for term in ['saas', 'app', 'software']):
            base_competitors = ['salesforce.com', 'hubspot.com', 'zendesk.com']
        elif any(term in domain for term in ['marketing', 'ads']):
            base_competitors = ['google.com', 'facebook.com', 'linkedin.com']
        else:
            base_competitors = ['competitor1.com', 'competitor2.com', 'competitor3.com']
        
        competitors = []
        for i, comp_domain in enumerate(base_competitors):
            competitors.append({
                'domain': comp_domain,
                'name': comp_domain.replace('.com', '').title(),
                'score': max(30, 90 - i * 15),  # Decreasing scores
                'rank': (i + 1) * 1000,
                'visits': max(10000, 1000000 - i * 200000)
            })
        
        return competitors
    
    def _get_mock_semrush_data(self, domain: str) -> List[Dict]:
        """Generate mock SEMrush competitor data."""
        competitors = []
        
        base_names = ['competitor', 'rival', 'alternative']
        for i, name in enumerate(base_names):
            competitors.append({
                'domain': f"{name}-{i+1}.com",
                'name': f"{name.title()} {i+1}",
                'competitive_relevance': max(0.3, 0.9 - i * 0.2),
                'organic_keywords': max(100, 5000 - i * 1000),
                'paid_keywords': max(50, 2000 - i * 400),
                'estimated_budget': max(1000, 50000 - i * 10000),
                'traffic': max(5000, 500000 - i * 100000),
                'score': max(30, 90 - i * 20)
            })
        
        return competitors
    
    async def _analyze_differences(self, original_url: str, competitor_url: str, key_topics: List[str] = None) -> List[str]:
        """Analyze key differences between websites (simplified version)."""
        try:
            # This is a simplified version. In production, you'd want to:
            # 1. Scrape competitor website
            # 2. Compare content, positioning, features
            # 3. Use more sophisticated NLP
            
            differences = [
                "Different pricing model",
                "Different target market focus", 
                "Alternative feature set",
                "Different geographic focus"
            ]
            
            # Add topic-based differences if available
            if key_topics:
                topic_diffs = [f"Different approach to {topic}" for topic in key_topics[:2]]
                differences.extend(topic_diffs)
            
            return differences[:4]  # Return top 4 differences
            
        except Exception as e:
            logger.error(f"Difference analysis failed: {e}")
            return ["Analysis not available"]
