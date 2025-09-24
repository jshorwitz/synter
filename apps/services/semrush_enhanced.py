import os
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, date
import json
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SEMrushEnhanced:
    """Enhanced SEMrush integration for competitor analysis and keyword gap analysis."""
    
    def __init__(self):
        self.api_key = os.getenv('SEMRUSH_API_KEY')
        self.base_url = "https://api.semrush.com/"
        self.mock_mode = os.getenv('MOCK_SEMRUSH', 'false').lower() == 'true'
        
        if not self.api_key or self.mock_mode:
            logger.info("Using SEMrush mock mode")
            self.mock_mode = True
        else:
            logger.info("SEMrush API integration enabled")
    
    async def get_competitor_overview(self, domain: str, limit: int = 10) -> Dict:
        """Get comprehensive competitor overview."""
        try:
            if self.mock_mode:
                return self._mock_competitor_overview(domain, limit)
            
            # Get organic competitors
            organic_competitors = await self._get_organic_competitors(domain, limit)
            
            # Get paid competitors  
            paid_competitors = await self._get_paid_competitors(domain, limit)
            
            # Get domain overview
            domain_overview = await self._get_domain_overview(domain)
            
            # Get top keywords
            top_keywords = await self._get_top_keywords(domain, limit=20)
            
            # Get ad copy examples
            ad_copies = await self._get_ad_copies(domain, limit=10)
            
            return {
                "domain": domain,
                "overview": domain_overview,
                "organic_competitors": organic_competitors,
                "paid_competitors": paid_competitors, 
                "top_keywords": top_keywords,
                "ad_copies": ad_copies,
                "analysis_date": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"SEMrush competitor overview failed for {domain}: {e}")
            return self._mock_competitor_overview(domain, limit)
    
    async def get_keyword_gap_analysis(self, target_domain: str, competitor_domains: List[str]) -> Dict:
        """Perform keyword gap analysis between target and competitors."""
        try:
            if self.mock_mode:
                return self._mock_keyword_gap_analysis(target_domain, competitor_domains)
            
            # Get keywords for target domain
            target_keywords = await self._get_domain_keywords(target_domain, limit=200)
            
            # Get keywords for each competitor
            competitor_keywords = {}
            for comp_domain in competitor_domains[:3]:  # Limit to 3 competitors
                comp_keywords = await self._get_domain_keywords(comp_domain, limit=200)
                competitor_keywords[comp_domain] = comp_keywords
            
            # Analyze gaps
            gap_analysis = self._analyze_keyword_gaps(target_keywords, competitor_keywords)
            
            return {
                "target_domain": target_domain,
                "competitor_domains": competitor_domains,
                "target_keywords_count": len(target_keywords),
                "competitor_keywords": {domain: len(keywords) for domain, keywords in competitor_keywords.items()},
                "keyword_gaps": gap_analysis,
                "analysis_date": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Keyword gap analysis failed: {e}")
            return self._mock_keyword_gap_analysis(target_domain, competitor_domains)
    
    async def _get_organic_competitors(self, domain: str, limit: int = 10) -> List[Dict]:
        """Get organic search competitors."""
        if self.mock_mode:
            return self._mock_organic_competitors(domain, limit)
        
        try:
            params = {
                'type': 'domain_organic_organic',
                'key': self.api_key,
                'domain': domain,
                'display_limit': limit,
                'export_columns': 'Dn,Cr,Np,Ad,At,Ot,Kn'
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            competitors = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 7:
                        competitors.append({
                            'domain': parts[0],
                            'competitive_relevance': float(parts[1]) if parts[1] else 0,
                            'common_keywords': int(parts[2]) if parts[2] else 0,
                            'ad_keywords': int(parts[3]) if parts[3] else 0,
                            'ad_traffic': int(parts[4]) if parts[4] else 0,
                            'organic_traffic': int(parts[5]) if parts[5] else 0,
                            'total_keywords': int(parts[6]) if parts[6] else 0
                        })
            
            return competitors
            
        except Exception as e:
            logger.error(f"Failed to get organic competitors: {e}")
            return self._mock_organic_competitors(domain, limit)
    
    async def _get_paid_competitors(self, domain: str, limit: int = 10) -> List[Dict]:
        """Get paid search competitors."""
        if self.mock_mode:
            return self._mock_paid_competitors(domain, limit)
        
        try:
            params = {
                'type': 'domain_adwords_adwords',
                'key': self.api_key,
                'domain': domain,
                'display_limit': limit,
                'export_columns': 'Dn,Cr,Np,Ad,At,Ac,Pc'
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            competitors = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 7:
                        competitors.append({
                            'domain': parts[0],
                            'competitive_relevance': float(parts[1]) if parts[1] else 0,
                            'common_keywords': int(parts[2]) if parts[2] else 0,
                            'ad_keywords': int(parts[3]) if parts[3] else 0,
                            'ad_traffic': int(parts[4]) if parts[4] else 0,
                            'ad_cost': float(parts[5]) if parts[5] else 0,
                            'price_cpc': float(parts[6]) if parts[6] else 0
                        })
            
            return competitors
            
        except Exception as e:
            logger.error(f"Failed to get paid competitors: {e}")
            return self._mock_paid_competitors(domain, limit)
    
    async def _get_domain_overview(self, domain: str) -> Dict:
        """Get domain overview metrics."""
        if self.mock_mode:
            return self._mock_domain_overview(domain)
        
        try:
            params = {
                'type': 'domain_organic',
                'key': self.api_key,
                'domain': domain,
                'export_columns': 'Dn,Rk,Or,Ot,Oc,Ad'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split(';')
                if len(parts) >= 6:
                    return {
                        'domain': parts[0],
                        'organic_rank': int(parts[1]) if parts[1] else 0,
                        'organic_keywords': int(parts[2]) if parts[2] else 0,
                        'organic_traffic': int(parts[3]) if parts[3] else 0,
                        'organic_cost': float(parts[4]) if parts[4] else 0,
                        'ad_keywords': int(parts[5]) if parts[5] else 0
                    }
            
            return self._mock_domain_overview(domain)
            
        except Exception as e:
            logger.error(f"Failed to get domain overview: {e}")
            return self._mock_domain_overview(domain)
    
    async def _get_top_keywords(self, domain: str, limit: int = 20) -> List[Dict]:
        """Get top keywords for domain."""
        if self.mock_mode:
            return self._mock_top_keywords(domain, limit)
        
        try:
            params = {
                'type': 'domain_organic',
                'key': self.api_key,
                'domain': domain,
                'display_limit': limit,
                'export_columns': 'Ph,Po,Pp,Pd,Nq,Cp,Ur,Tr,Tc,Co,Nr'
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            keywords = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 11:
                        keywords.append({
                            'keyword': parts[0],
                            'position': int(parts[1]) if parts[1] else 0,
                            'previous_position': int(parts[2]) if parts[2] else 0,
                            'position_difference': int(parts[3]) if parts[3] else 0,
                            'search_volume': int(parts[4]) if parts[4] else 0,
                            'cpc': float(parts[5]) if parts[5] else 0,
                            'url': parts[6],
                            'traffic': float(parts[7]) if parts[7] else 0,
                            'traffic_cost': float(parts[8]) if parts[8] else 0,
                            'competition': float(parts[9]) if parts[9] else 0,
                            'results': int(parts[10]) if parts[10] else 0
                        })
            
            return keywords
            
        except Exception as e:
            logger.error(f"Failed to get top keywords: {e}")
            return self._mock_top_keywords(domain, limit)
    
    async def _get_ad_copies(self, domain: str, limit: int = 10) -> List[Dict]:
        """Get ad copy examples from competitors."""
        if self.mock_mode:
            return self._mock_ad_copies(domain, limit)
        
        try:
            params = {
                'type': 'domain_adwords_historical',
                'key': self.api_key,
                'domain': domain,
                'display_limit': limit,
                'export_columns': 'Ur,Tt,Dt,Dd,Vu,Ts,Tf'
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            ad_copies = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 7:
                        ad_copies.append({
                            'visible_url': parts[0],
                            'title': parts[1],
                            'text': parts[2],
                            'description': parts[3],
                            'url': parts[4],
                            'first_seen': parts[5],
                            'last_seen': parts[6]
                        })
            
            return ad_copies
            
        except Exception as e:
            logger.error(f"Failed to get ad copies: {e}")
            return self._mock_ad_copies(domain, limit)
    
    async def _get_domain_keywords(self, domain: str, limit: int = 200) -> List[Dict]:
        """Get keywords for a domain for gap analysis."""
        if self.mock_mode:
            return self._mock_domain_keywords(domain, limit)
        
        try:
            params = {
                'type': 'domain_organic',
                'key': self.api_key,
                'domain': domain,
                'display_limit': limit,
                'export_columns': 'Ph,Po,Nq,Cp,Co'
            }
            
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            
            keywords = []
            lines = response.text.strip().split('\n')
            
            for line in lines[1:]:  # Skip header
                if line:
                    parts = line.split(';')
                    if len(parts) >= 5:
                        keywords.append({
                            'keyword': parts[0],
                            'position': int(parts[1]) if parts[1] else 0,
                            'search_volume': int(parts[2]) if parts[2] else 0,
                            'cpc': float(parts[3]) if parts[3] else 0,
                            'competition': float(parts[4]) if parts[4] else 0
                        })
            
            return keywords
            
        except Exception as e:
            logger.error(f"Failed to get domain keywords: {e}")
            return self._mock_domain_keywords(domain, limit)
    
    def _analyze_keyword_gaps(self, target_keywords: List[Dict], competitor_keywords: Dict[str, List[Dict]]) -> Dict:
        """Analyze keyword gaps between target and competitors."""
        
        # Create sets of keywords for easier analysis
        target_keyword_set = {kw['keyword'].lower() for kw in target_keywords}
        
        competitor_keyword_sets = {}
        for domain, keywords in competitor_keywords.items():
            competitor_keyword_sets[domain] = {kw['keyword'].lower() for kw in keywords}
        
        # Find gaps (keywords competitors rank for but target doesn't)
        keyword_gaps = {}
        keyword_opportunities = []
        
        for comp_domain, comp_keywords in competitor_keywords.items():
            gaps = []
            for kw in comp_keywords:
                kw_lower = kw['keyword'].lower()
                if kw_lower not in target_keyword_set:
                    # This is a gap - competitor ranks but target doesn't
                    gap_data = {
                        **kw,
                        'competitor_domain': comp_domain,
                        'opportunity_score': self._calculate_opportunity_score(kw)
                    }
                    gaps.append(gap_data)
                    
                    # Add to opportunities if high-value
                    if gap_data['opportunity_score'] >= 70:
                        keyword_opportunities.append(gap_data)
            
            keyword_gaps[comp_domain] = sorted(gaps, key=lambda x: x['opportunity_score'], reverse=True)[:20]
        
        # Find common competitor keywords (opportunities multiple competitors are targeting)
        all_comp_keywords = set()
        for comp_keywords in competitor_keyword_sets.values():
            all_comp_keywords.update(comp_keywords)
        
        common_opportunities = []
        for keyword in all_comp_keywords:
            if keyword not in target_keyword_set:
                # Count how many competitors target this
                competitor_count = sum(1 for comp_set in competitor_keyword_sets.values() if keyword in comp_set)
                if competitor_count >= 2:  # Multiple competitors target this
                    # Find the best performing version
                    best_kw_data = None
                    for comp_keywords in competitor_keywords.values():
                        for kw in comp_keywords:
                            if kw['keyword'].lower() == keyword:
                                if not best_kw_data or kw.get('search_volume', 0) > best_kw_data.get('search_volume', 0):
                                    best_kw_data = kw
                    
                    if best_kw_data:
                        common_opportunities.append({
                            **best_kw_data,
                            'competitor_count': competitor_count,
                            'opportunity_score': self._calculate_opportunity_score(best_kw_data, competitor_count)
                        })
        
        # Sort opportunities by score
        keyword_opportunities = sorted(keyword_opportunities, key=lambda x: x['opportunity_score'], reverse=True)[:20]
        common_opportunities = sorted(common_opportunities, key=lambda x: x['opportunity_score'], reverse=True)[:15]
        
        return {
            "keyword_gaps_by_competitor": keyword_gaps,
            "top_keyword_opportunities": keyword_opportunities,
            "common_competitor_keywords": common_opportunities,
            "summary": {
                "total_target_keywords": len(target_keywords),
                "total_gap_opportunities": sum(len(gaps) for gaps in keyword_gaps.values()),
                "high_value_opportunities": len(keyword_opportunities),
                "multi_competitor_opportunities": len(common_opportunities)
            }
        }
    
    def _calculate_opportunity_score(self, keyword_data: Dict, competitor_count: int = 1) -> int:
        """Calculate opportunity score for a keyword gap."""
        score = 50  # Base score
        
        # Search volume factor (0-30 points)
        volume = keyword_data.get('search_volume', 0)
        if volume >= 10000:
            score += 30
        elif volume >= 1000:
            score += 20
        elif volume >= 100:
            score += 10
        elif volume >= 10:
            score += 5
        
        # Competition factor (0-20 points, inverse relationship)
        competition = keyword_data.get('competition', 0.5)
        if competition <= 0.3:
            score += 20  # Low competition is good
        elif competition <= 0.6:
            score += 10
        elif competition <= 0.8:
            score += 5
        
        # CPC factor (indicates commercial value, 0-15 points)
        cpc = keyword_data.get('cpc', 0)
        if cpc >= 10:
            score += 15  # High CPC indicates commercial value
        elif cpc >= 5:
            score += 10
        elif cpc >= 1:
            score += 5
        
        # Multiple competitor factor (0-10 points)
        if competitor_count >= 3:
            score += 10
        elif competitor_count >= 2:
            score += 5
        
        # Position factor (if competitor ranks well, it's a good opportunity)
        position = keyword_data.get('position', 100)
        if position <= 3:
            score += 15
        elif position <= 10:
            score += 10
        elif position <= 20:
            score += 5
        
        return min(100, max(0, score))
    
    # Mock data methods for development
    def _mock_competitor_overview(self, domain: str, limit: int) -> Dict:
        """Generate mock competitor overview."""
        return {
            "domain": domain,
            "overview": self._mock_domain_overview(domain),
            "organic_competitors": self._mock_organic_competitors(domain, limit),
            "paid_competitors": self._mock_paid_competitors(domain, limit),
            "top_keywords": self._mock_top_keywords(domain, 20),
            "ad_copies": self._mock_ad_copies(domain, 10),
            "analysis_date": datetime.utcnow().isoformat()
        }
    
    def _mock_domain_overview(self, domain: str) -> Dict:
        """Mock domain overview."""
        base_hash = hash(domain) % 10000
        return {
            'domain': domain,
            'organic_rank': max(1000, 50000 - base_hash),
            'organic_keywords': max(100, 5000 - base_hash),
            'organic_traffic': max(1000, 100000 - base_hash * 10),
            'organic_cost': max(500, 50000 - base_hash * 5),
            'ad_keywords': max(50, 2000 - base_hash)
        }
    
    def _mock_organic_competitors(self, domain: str, limit: int) -> List[Dict]:
        """Mock organic competitors."""
        competitors = []
        base_names = ['techcompetitor', 'rivalsite', 'alternativesolution', 'competingplatform', 'industryplayer']
        
        for i in range(min(limit, 5)):
            base_hash = hash(f"{domain}_{i}") % 1000
            competitors.append({
                'domain': f"{base_names[i]}.com",
                'competitive_relevance': max(0.3, 0.9 - i * 0.15),
                'common_keywords': max(50, 500 - base_hash),
                'ad_keywords': max(20, 200 - base_hash // 2),
                'ad_traffic': max(1000, 50000 - base_hash * 50),
                'organic_traffic': max(5000, 200000 - base_hash * 100),
                'total_keywords': max(100, 1000 - base_hash)
            })
        
        return competitors
    
    def _mock_paid_competitors(self, domain: str, limit: int) -> List[Dict]:
        """Mock paid competitors."""
        competitors = []
        base_names = ['adcompetitor', 'ppcrivals', 'paidadssolution', 'adspendplatform', 'paidcompetitor']
        
        for i in range(min(limit, 5)):
            base_hash = hash(f"{domain}_paid_{i}") % 1000
            competitors.append({
                'domain': f"{base_names[i]}.com",
                'competitive_relevance': max(0.4, 0.85 - i * 0.12),
                'common_keywords': max(30, 300 - base_hash),
                'ad_keywords': max(50, 400 - base_hash),
                'ad_traffic': max(2000, 80000 - base_hash * 60),
                'ad_cost': max(1000, 25000 - base_hash * 20),
                'price_cpc': max(0.5, 15 - base_hash * 0.01)
            })
        
        return competitors
    
    def _mock_top_keywords(self, domain: str, limit: int) -> List[Dict]:
        """Mock top keywords."""
        keywords = []
        
        # Generate industry-relevant keywords based on domain
        domain_lower = domain.lower()
        if 'tech' in domain_lower or 'software' in domain_lower or 'app' in domain_lower:
            base_keywords = ['software solution', 'tech platform', 'application development', 'digital tool', 'automation software']
        elif 'marketing' in domain_lower:
            base_keywords = ['marketing platform', 'advertising tool', 'campaign management', 'digital marketing', 'marketing automation']
        else:
            base_keywords = ['business solution', 'professional service', 'enterprise platform', 'business tool', 'corporate solution']
        
        for i, base_kw in enumerate(base_keywords):
            if i >= limit:
                break
                
            base_hash = hash(f"{domain}_{base_kw}") % 1000
            keywords.append({
                'keyword': base_kw,
                'position': min(50, i + 1 + base_hash % 10),
                'previous_position': min(50, i + 2 + base_hash % 15),
                'position_difference': -1,  # Improving
                'search_volume': max(100, 5000 - base_hash * 3),
                'cpc': max(0.5, 10 - base_hash * 0.008),
                'url': f"https://{domain}/product",
                'traffic': max(10, 1000 - base_hash),
                'traffic_cost': max(50, 2000 - base_hash * 2),
                'competition': min(1.0, 0.2 + base_hash * 0.0005),
                'results': max(1000, 100000 - base_hash * 50)
            })
            
            # Add variations
            for j, suffix in enumerate(['tools', 'platform', 'service']):
                if len(keywords) >= limit:
                    break
                variation_kw = f"{base_kw} {suffix}"
                variation_hash = hash(f"{domain}_{variation_kw}") % 500
                keywords.append({
                    'keyword': variation_kw,
                    'position': min(50, 10 + j * 5 + variation_hash % 8),
                    'previous_position': min(50, 12 + j * 5 + variation_hash % 10),
                    'position_difference': 0,
                    'search_volume': max(50, 2000 - variation_hash * 2),
                    'cpc': max(0.3, 8 - variation_hash * 0.01),
                    'url': f"https://{domain}/features",
                    'traffic': max(5, 500 - variation_hash),
                    'traffic_cost': max(20, 1000 - variation_hash),
                    'competition': min(1.0, 0.3 + variation_hash * 0.0008),
                    'results': max(500, 50000 - variation_hash * 30)
                })
        
        return keywords[:limit]
    
    def _mock_ad_copies(self, domain: str, limit: int) -> List[Dict]:
        """Mock ad copy examples."""
        ad_copies = []
        
        base_titles = [
            "Transform Your Business Today",
            "The Complete Solution You Need", 
            "Streamline Operations Instantly",
            "Boost Productivity & Efficiency",
            "Professional Grade Platform"
        ]
        
        base_descriptions = [
            "Discover how leading companies improve efficiency with our platform. Start your free trial today.",
            "Join thousands of professionals who trust our solution. Get started in minutes with expert support.",
            "Revolutionary approach to business optimization. See immediate results with our proven methodology.",
            "Enterprise-grade solution designed for modern businesses. Secure, scalable, and user-friendly.",
            "Unlock your team's potential with advanced automation. Integrate seamlessly with existing workflows."
        ]
        
        for i in range(min(limit, 5)):
            ad_copies.append({
                'visible_url': f"{domain}/solution",
                'title': base_titles[i],
                'text': base_descriptions[i],
                'description': base_descriptions[i][:100],
                'url': f"https://{domain}/landing",
                'first_seen': '2025-01-15',
                'last_seen': '2025-09-20'
            })
        
        return ad_copies
    
    def _mock_domain_keywords(self, domain: str, limit: int) -> List[Dict]:
        """Mock domain keywords for gap analysis."""
        return self._mock_top_keywords(domain, limit)
    
    def _mock_keyword_gap_analysis(self, target_domain: str, competitor_domains: List[str]) -> Dict:
        """Mock keyword gap analysis."""
        # Generate mock gaps
        keyword_gaps = {}
        all_opportunities = []
        
        for i, comp_domain in enumerate(competitor_domains[:3]):
            gaps = []
            for j in range(10):  # 10 gaps per competitor
                keyword = f"competitor keyword {i+1}-{j+1}"
                opportunity_score = max(30, 90 - j * 5 - i * 10)
                
                gap_data = {
                    'keyword': keyword,
                    'position': j + 1,
                    'search_volume': max(100, 5000 - j * 300),
                    'cpc': max(0.5, 8 - j * 0.5),
                    'competition': min(1.0, 0.2 + j * 0.08),
                    'competitor_domain': comp_domain,
                    'opportunity_score': opportunity_score
                }
                gaps.append(gap_data)
                
                if opportunity_score >= 70:
                    all_opportunities.append(gap_data)
            
            keyword_gaps[comp_domain] = gaps
        
        # Generate common opportunities
        common_opportunities = []
        for i in range(5):
            common_opportunities.append({
                'keyword': f"high value keyword {i+1}",
                'position': i + 1,
                'search_volume': 8000 - i * 1000,
                'cpc': 12 - i * 2,
                'competition': 0.3 + i * 0.1,
                'competitor_count': 3 - i // 2,
                'opportunity_score': 95 - i * 5
            })
        
        return {
            "keyword_gaps_by_competitor": keyword_gaps,
            "top_keyword_opportunities": all_opportunities[:20],
            "common_competitor_keywords": common_opportunities,
            "summary": {
                "total_target_keywords": 150 + hash(target_domain) % 100,
                "total_gap_opportunities": sum(len(gaps) for gaps in keyword_gaps.values()),
                "high_value_opportunities": len(all_opportunities),
                "multi_competitor_opportunities": len(common_opportunities)
            }
        }
