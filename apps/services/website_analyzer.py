import requests
import os
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from typing import Dict, List, Optional
import re
from textblob import TextBlob
import asyncio

logger = logging.getLogger(__name__)

class WebsiteAnalyzer:
    """Analyze websites for marketing insights."""
    
    def __init__(self):
        self.builtwith_api_key = os.getenv('BUILTWITH_API_KEY')
        self.mock_builtwith = os.getenv('MOCK_BUILTWITH', 'false').lower() == 'true'
        
    async def analyze_website(self, url: str, deep_analysis: bool = True) -> Dict:
        """Perform comprehensive website analysis."""
        logger.info(f"Analyzing website: {url}")
        
        try:
            # Fetch and parse website content
            content_data = await self._scrape_website(url)
            
            # Extract business insights
            business_data = self._analyze_business_model(content_data)
            
            # Get technical stack (if deep analysis requested)
            tech_data = {}
            if deep_analysis:
                tech_data = await self._get_tech_stack(url)
            
            # Combine all analysis
            return {
                **content_data,
                **business_data,
                **tech_data,
                'analyzed_url': url
            }
            
        except Exception as e:
            logger.error(f"Website analysis failed for {url}: {e}")
            return {
                'title': None,
                'description': None,
                'industry': 'unknown',
                'business_model': 'unknown',
                'content_summary': f"Analysis failed: {str(e)}",
                'key_topics': [],
                'value_propositions': [],
                'technologies': {},
                'tracking_pixels': []
            }
    
    async def _scrape_website(self, url: str) -> Dict:
        """Scrape website content and extract basic information."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract basic metadata
            title = soup.find('title')
            title_text = title.get_text().strip() if title else None
            
            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '').strip() if meta_desc else None
            
            # Extract main content
            content_text = self._extract_content_text(soup)
            
            # Extract key topics from content
            key_topics = self._extract_key_topics(content_text)
            
            # Extract value propositions
            value_props = self._extract_value_propositions(content_text, soup)
            
            return {
                'title': title_text,
                'description': description,
                'content_summary': content_text[:1000] + "..." if len(content_text) > 1000 else content_text,
                'key_topics': key_topics,
                'value_propositions': value_props
            }
            
        except Exception as e:
            logger.error(f"Website scraping failed for {url}: {e}")
            raise
    
    def _extract_content_text(self, soup: BeautifulSoup) -> str:
        """Extract main content text from HTML."""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        
        # Get text from main content areas
        content_selectors = [
            'main', '[role="main"]', '.main-content', '#main-content',
            '.content', '#content', 'article', '.article'
        ]
        
        content_text = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content_text = elements[0].get_text()
                break
        
        # Fallback to body
        if not content_text:
            content_text = soup.body.get_text() if soup.body else soup.get_text()
        
        # Clean up whitespace
        content_text = re.sub(r'\s+', ' ', content_text).strip()
        
        return content_text
    
    def _extract_key_topics(self, content_text: str) -> List[str]:
        """Extract key topics from content using simple NLP."""
        try:
            # Use TextBlob for basic topic extraction
            blob = TextBlob(content_text)
            
            # Get noun phrases as potential topics
            noun_phrases = [str(phrase).lower() for phrase in blob.noun_phrases]
            
            # Filter and clean topics
            topics = []
            for phrase in noun_phrases:
                # Skip short phrases and common words
                if len(phrase) > 3 and len(phrase.split()) <= 3:
                    if not any(common in phrase for common in ['the', 'this', 'that', 'your', 'our']):
                        topics.append(phrase)
            
            # Get most common topics
            from collections import Counter
            topic_counts = Counter(topics)
            return [topic for topic, count in topic_counts.most_common(10)]
            
        except Exception as e:
            logger.error(f"Topic extraction failed: {e}")
            return []
    
    def _extract_value_propositions(self, content_text: str, soup: BeautifulSoup) -> List[str]:
        """Extract value propositions from content."""
        value_props = []
        
        # Look for common value prop patterns in headings
        headings = soup.find_all(['h1', 'h2', 'h3'])
        for heading in headings:
            text = heading.get_text().strip()
            if len(text) > 10 and len(text) < 100:
                # Check for value prop keywords
                value_keywords = ['solution', 'benefit', 'advantage', 'value', 'help', 'improve', 'increase', 'reduce', 'save', 'achieve']
                if any(keyword in text.lower() for keyword in value_keywords):
                    value_props.append(text)
        
        # Look for bullet points and lists
        lists = soup.find_all(['ul', 'ol'])
        for list_elem in lists:
            items = list_elem.find_all('li')
            for item in items[:3]:  # Limit to first 3 items
                text = item.get_text().strip()
                if 20 < len(text) < 150:
                    value_props.append(text)
        
        return value_props[:5]  # Return top 5
    
    def _analyze_business_model(self, content_data: Dict) -> Dict:
        """Analyze business model and industry from content."""
        content = (content_data.get('content_summary', '') + ' ' + 
                  ' '.join(content_data.get('value_propositions', []))).lower()
        
        # Industry detection patterns
        industry_patterns = {
            'saas': ['software as a service', 'saas', 'cloud platform', 'api', 'dashboard'],
            'ecommerce': ['shop', 'store', 'buy', 'cart', 'checkout', 'product'],
            'fintech': ['financial', 'banking', 'payment', 'money', 'finance', 'loan'],
            'healthcare': ['health', 'medical', 'patient', 'doctor', 'healthcare'],
            'education': ['education', 'learning', 'course', 'student', 'teach'],
            'marketing': ['marketing', 'advertising', 'campaign', 'brand', 'promotion'],
            'consulting': ['consulting', 'advisory', 'expert', 'professional services'],
            'technology': ['technology', 'tech', 'innovation', 'digital', 'software']
        }
        
        # Business model patterns
        model_patterns = {
            'b2b': ['enterprise', 'business', 'companies', 'organizations', 'teams'],
            'b2c': ['consumers', 'individuals', 'personal', 'family', 'lifestyle'],
            'marketplace': ['marketplace', 'connect', 'platform', 'buyers', 'sellers'],
            'subscription': ['subscription', 'monthly', 'plan', 'pricing tiers']
        }
        
        # Detect industry
        industry_scores = {}
        for industry, keywords in industry_patterns.items():
            score = sum(1 for keyword in keywords if keyword in content)
            if score > 0:
                industry_scores[industry] = score
        
        # Detect business model
        model_scores = {}
        for model, keywords in model_patterns.items():
            score = sum(1 for keyword in keywords if keyword in content)
            if score > 0:
                model_scores[model] = score
        
        # Get best matches
        industry = max(industry_scores, key=industry_scores.get) if industry_scores else 'technology'
        business_model = max(model_scores, key=model_scores.get) if model_scores else 'b2b'
        
        return {
            'industry': industry,
            'business_model': business_model
        }
    
    async def _get_tech_stack(self, url: str) -> Dict:
        """Get technology stack using BuiltWith API or mock data."""
        if self.mock_builtwith:
            return self._get_mock_tech_data(url)
        
        if not self.builtwith_api_key:
            logger.warning("No BuiltWith API key provided, using mock data")
            return self._get_mock_tech_data(url)
        
        try:
            # BuiltWith API call
            api_url = f"https://api.builtwith.com/v21/api.json"
            params = {
                'KEY': self.builtwith_api_key,
                'LOOKUP': url,
                'NOMETA': '1',
                'NOPII': '1'
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse BuiltWith response
            technologies = {}
            tracking_pixels = []
            
            if 'Results' in data and data['Results']:
                result = data['Results'][0]
                paths = result.get('Result', {}).get('Paths', [])
                
                for path in paths:
                    technologies_list = path.get('Technologies', [])
                    for tech in technologies_list:
                        category = tech.get('Categories', [{}])[0].get('Name', 'Other')
                        tech_name = tech.get('Name', '')
                        
                        if category not in technologies:
                            technologies[category] = []
                        technologies[category].append(tech_name)
                        
                        # Check for tracking pixels
                        if 'analytics' in category.lower() or 'advertising' in category.lower():
                            tracking_pixels.append(tech_name)
            
            return {
                'technologies': technologies,
                'tracking_pixels': tracking_pixels
            }
            
        except Exception as e:
            logger.error(f"BuiltWith API call failed for {url}: {e}")
            return self._get_mock_tech_data(url)
    
    def _get_mock_tech_data(self, url: str) -> Dict:
        """Generate mock technology data for development."""
        domain = urlparse(url).netloc.lower()
        
        # Generate realistic mock data based on domain patterns
        mock_technologies = {
            'Web Frameworks': ['React', 'Next.js'],
            'Analytics': ['Google Analytics', 'Mixpanel'],
            'JavaScript Libraries': ['jQuery', 'Lodash'],
            'CDN': ['CloudFlare']
        }
        
        mock_pixels = ['Google Analytics', 'Facebook Pixel', 'LinkedIn Insight Tag']
        
        # Add some variation based on domain
        if 'shopify' in domain:
            mock_technologies['E-commerce'] = ['Shopify']
        elif any(word in domain for word in ['app', 'api', 'dev']):
            mock_technologies['Development'] = ['Docker', 'AWS']
        
        return {
            'technologies': mock_technologies,
            'tracking_pixels': mock_pixels
        }
