import logging
import os
from typing import Dict, List
import json
import re
from models import Competitor

# Import existing OpenAI integration
try:
    import sys
    sys.path.append('/Users/joelhorwitz/dev/synter/ai-adwords/src')
    from ai_agency.llm_clients import AIAgencyManager
    OPENAI_INTEGRATION_AVAILABLE = True
except ImportError:
    OPENAI_INTEGRATION_AVAILABLE = False

logger = logging.getLogger(__name__)

class PersonaGenerator:
    """Generate customer personas based on website analysis and competitive data."""
    
    def __init__(self):
        self.industry_personas = self._load_industry_persona_templates()
        self.ai_agency_manager = None
        self.use_openai = OPENAI_INTEGRATION_AVAILABLE and bool(os.getenv('OPENAI_API_KEY'))
        
        if self.use_openai:
            try:
                self.ai_agency_manager = AIAgencyManager()
                logger.info("OpenAI persona generation enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI integration: {e}")
                self.use_openai = False
    
    async def generate_personas(self, website_analysis: Dict, competitors: List[Competitor] = None) -> List[Dict]:
        """Generate customer personas based on website analysis."""
        logger.info("Generating customer personas")
        
        industry = website_analysis.get('industry', 'technology')
        business_model = website_analysis.get('business_model', 'b2b')
        key_topics = website_analysis.get('key_topics', [])
        value_props = website_analysis.get('value_propositions', [])
        
        try:
            # Use OpenAI if available
            if self.use_openai and self.ai_agency_manager:
                logger.info("Using OpenAI GPT-4 for persona generation")
                return await self._generate_personas_with_openai(website_analysis, competitors)
            else:
                logger.info("Using template-based persona generation")
                return await self._generate_personas_with_templates(
                    industry, business_model, key_topics, value_props, competitors
                )
            
        except Exception as e:
            logger.error(f"Persona generation failed: {e}")
            return self._get_fallback_personas(business_model)
    
    async def _generate_personas_with_openai(self, website_analysis: Dict, competitors: List[Competitor] = None) -> List[Dict]:
        """Generate personas using OpenAI GPT-4."""
        try:
            # Prepare keywords from topics for OpenAI analysis
            keywords = website_analysis.get('key_topics', [])[:8]
            if not keywords:
                keywords = ['business solution', 'efficiency', 'growth']
            
            # Get OpenAI audience insights
            audience_insights = await self.ai_agency_manager.generate_audience_insights(
                website_analysis, keywords
            )
            
            # Parse OpenAI response into structured personas
            personas = self._parse_openai_personas(audience_insights, website_analysis)
            
            if personas:
                logger.info(f"Generated {len(personas)} personas using OpenAI GPT-4")
                return personas
            else:
                # Fallback to template-based generation
                logger.warning("OpenAI response parsing failed, falling back to templates")
                return await self._generate_personas_with_templates(
                    website_analysis.get('industry', 'technology'),
                    website_analysis.get('business_model', 'b2b'),
                    website_analysis.get('key_topics', []),
                    website_analysis.get('value_propositions', []),
                    competitors
                )
                
        except Exception as e:
            logger.error(f"OpenAI persona generation failed: {e}")
            # Fallback to template-based generation
            return await self._generate_personas_with_templates(
                website_analysis.get('industry', 'technology'),
                website_analysis.get('business_model', 'b2b'),
                website_analysis.get('key_topics', []),
                website_analysis.get('value_propositions', []),
                competitors
            )
    
    async def _generate_personas_with_templates(self, industry: str, business_model: str, 
                                              key_topics: List[str], value_props: List[str], 
                                              competitors: List[Competitor] = None) -> List[Dict]:
        """Generate personas using template-based approach."""
        # Get base personas for industry
        base_personas = self.industry_personas.get(industry, self.industry_personas['technology'])
        
        # Customize personas based on business model
        personas = []
        for base_persona in base_personas[:3]:  # Limit to 3 personas
            persona = self._customize_persona(
                base_persona,
                business_model,
                key_topics,
                value_props,
                competitors
            )
            personas.append(persona)
        
        return personas
    
    def _parse_openai_personas(self, audience_insights: str, website_analysis: Dict) -> List[Dict]:
        """Parse OpenAI audience insights into structured persona data."""
        try:
            personas = []
            
            # Look for persona sections in the OpenAI response
            lines = audience_insights.split('\n')
            current_persona = None
            persona_count = 0
            
            for line in lines:
                line = line.strip()
                
                # Check if this line starts a new persona section
                if any(keyword in line.lower() for keyword in ['persona', 'audience', 'segment', 'target']):
                    if current_persona and persona_count < 3:
                        personas.append(current_persona)
                    
                    # Start new persona
                    current_persona = {
                        'name': self._extract_persona_name(line),
                        'job_title': 'Professional',
                        'industry': website_analysis.get('industry', 'Technology'),
                        'company_size': 'Mid-market (100-1000 employees)',
                        'pain_points': [],
                        'goals': [],
                        'motivations': [],
                        'search_behaviors': [],
                        'preferred_channels': [],
                        'keywords': [],
                        'ad_copy_themes': [],
                        'confidence_score': 0.8  # High confidence for OpenAI-generated
                    }
                    persona_count += 1
                
                elif current_persona:
                    # Extract information from the line
                    self._extract_persona_details(line, current_persona)
            
            # Add the last persona
            if current_persona and len(personas) < 3:
                personas.append(current_persona)
            
            # If we didn't get structured personas, create them from the general insights
            if not personas:
                personas = self._create_personas_from_insights(audience_insights, website_analysis)
            
            return personas[:3]  # Return max 3 personas
            
        except Exception as e:
            logger.error(f"Failed to parse OpenAI personas: {e}")
            return []
    
    def _extract_persona_name(self, line: str) -> str:
        """Extract persona name from a line."""
        # Look for common patterns
        line = line.replace('*', '').replace('#', '').strip()
        
        if ':' in line:
            name = line.split(':')[0].strip()
        elif 'persona' in line.lower():
            name = line.replace('persona', '').strip()
        else:
            name = line.strip()
        
        # Clean up common prefixes
        name = re.sub(r'^\d+\.?\s*', '', name)  # Remove numbering
        name = re.sub(r'^primary\s+', '', name, flags=re.IGNORECASE)
        
        return name[:50] if name else "Target Audience"
    
    def _extract_persona_details(self, line: str, persona: Dict):
        """Extract specific details from a line and add to persona."""
        line_lower = line.lower()
        
        # Pain points
        if any(keyword in line_lower for keyword in ['pain', 'problem', 'challenge', 'struggle']):
            if ':' in line:
                detail = line.split(':', 1)[1].strip()
                if detail and len(detail) > 5:
                    persona['pain_points'].append(detail)
        
        # Goals
        elif any(keyword in line_lower for keyword in ['goal', 'objective', 'want', 'need', 'achieve']):
            if ':' in line:
                detail = line.split(':', 1)[1].strip()
                if detail and len(detail) > 5:
                    persona['goals'].append(detail)
        
        # Demographics
        elif any(keyword in line_lower for keyword in ['title', 'role', 'position', 'job']):
            if ':' in line:
                title = line.split(':', 1)[1].strip()
                if title and len(title) > 2:
                    persona['job_title'] = title[:100]
        
        # Keywords/search terms
        elif any(keyword in line_lower for keyword in ['search', 'keyword', 'term']):
            keywords = re.findall(r'"([^"]*)"', line)  # Extract quoted terms
            persona['keywords'].extend(keywords[:5])
    
    def _create_personas_from_insights(self, insights: str, website_analysis: Dict) -> List[Dict]:
        """Create basic personas from general insights text."""
        business_model = website_analysis.get('business_model', 'b2b')
        industry = website_analysis.get('industry', 'technology')
        
        # Create 2-3 basic personas from the insights
        personas = [
            {
                'name': 'Primary Decision Maker',
                'job_title': 'Director/VP',
                'industry': industry,
                'company_size': 'Mid-market (100-1000 employees)' if business_model == 'b2b' else 'Individual',
                'pain_points': ['Operational challenges', 'Growth limitations', 'Resource constraints'],
                'goals': ['Improve efficiency', 'Drive growth', 'Reduce costs'],
                'motivations': ['Performance', 'Results', 'Innovation'],
                'search_behaviors': ['Research solutions', 'Compare options', 'Read reviews'],
                'preferred_channels': ['Search', 'LinkedIn', 'Industry publications'],
                'keywords': website_analysis.get('key_topics', ['business solution'])[:5],
                'ad_copy_themes': ['results_focused', 'professional'],
                'confidence_score': 0.7
            },
            {
                'name': 'End User/Influencer',
                'job_title': 'Manager/Specialist',
                'industry': industry,
                'company_size': 'Mid-market (100-1000 employees)' if business_model == 'b2b' else 'Individual',
                'pain_points': ['Daily workflow issues', 'Tool limitations', 'Time constraints'],
                'goals': ['Streamline work', 'Better tools', 'Productivity gains'],
                'motivations': ['Efficiency', 'Ease of use', 'Time savings'],
                'search_behaviors': ['Feature comparisons', 'User reviews', 'Best practices'],
                'preferred_channels': ['Search', 'Social media', 'Forums'],
                'keywords': website_analysis.get('key_topics', ['solution'])[:5],
                'ad_copy_themes': ['user_friendly', 'time_saving'],
                'confidence_score': 0.6
            }
        ]
        
        return personas
    
    def _load_industry_persona_templates(self) -> Dict:
        """Load persona templates by industry."""
        return {
            'saas': [
                {
                    'name': 'Technical Decision Maker',
                    'job_title': 'CTO',
                    'company_size': 'Mid-market (100-1000 employees)',
                    'pain_points': ['Technical scalability', 'Integration complexity', 'Security concerns'],
                    'goals': ['Streamline operations', 'Reduce technical debt', 'Improve team productivity'],
                    'motivations': ['Innovation', 'Efficiency', 'Risk mitigation'],
                    'search_behaviors': ['Technical comparisons', 'Reviews and case studies', 'Implementation guides'],
                    'preferred_channels': ['Search', 'LinkedIn', 'Technical blogs']
                },
                {
                    'name': 'Business Stakeholder', 
                    'job_title': 'VP Operations',
                    'company_size': 'Mid-market (100-1000 employees)',
                    'pain_points': ['Cost management', 'Process inefficiencies', 'ROI measurement'],
                    'goals': ['Reduce operational costs', 'Improve process efficiency', 'Drive growth'],
                    'motivations': ['Performance', 'Cost savings', 'Business impact'],
                    'search_behaviors': ['ROI calculators', 'Business case studies', 'Pricing research'],
                    'preferred_channels': ['Search', 'LinkedIn', 'Industry publications']
                },
                {
                    'name': 'End User Champion',
                    'job_title': 'Product Manager',
                    'company_size': 'Mid-market (100-1000 employees)', 
                    'pain_points': ['Tool adoption', 'User experience', 'Feature gaps'],
                    'goals': ['Improve user satisfaction', 'Increase adoption', 'Deliver better products'],
                    'motivations': ['User success', 'Product excellence', 'Team collaboration'],
                    'search_behaviors': ['Feature comparisons', 'User reviews', 'Demo requests'],
                    'preferred_channels': ['Search', 'Product Hunt', 'Reddit']
                }
            ],
            'ecommerce': [
                {
                    'name': 'E-commerce Manager',
                    'job_title': 'E-commerce Manager',
                    'company_size': 'SMB (10-100 employees)',
                    'pain_points': ['Conversion optimization', 'Cart abandonment', 'Customer acquisition costs'],
                    'goals': ['Increase sales', 'Improve conversion rates', 'Reduce CAC'],
                    'motivations': ['Revenue growth', 'Performance optimization', 'Customer satisfaction'],
                    'search_behaviors': ['Best practices', 'Tool comparisons', 'Case studies'],
                    'preferred_channels': ['Search', 'Facebook', 'E-commerce forums']
                },
                {
                    'name': 'Digital Marketing Specialist',
                    'job_title': 'Digital Marketing Manager',
                    'company_size': 'SMB (10-100 employees)',
                    'pain_points': ['Attribution tracking', 'Multi-channel management', 'ROAS optimization'],
                    'goals': ['Improve marketing ROI', 'Better attribution', 'Scale campaigns'],
                    'motivations': ['Marketing performance', 'Data-driven decisions', 'Growth'],
                    'search_behaviors': ['Marketing tools', 'Analytics solutions', 'Best practices'],
                    'preferred_channels': ['Search', 'LinkedIn', 'Marketing blogs']
                }
            ],
            'fintech': [
                {
                    'name': 'Financial Services Executive',
                    'job_title': 'Chief Risk Officer',
                    'company_size': 'Enterprise (1000+ employees)',
                    'pain_points': ['Regulatory compliance', 'Risk management', 'Legacy system integration'],
                    'goals': ['Ensure compliance', 'Minimize risk', 'Modernize infrastructure'],
                    'motivations': ['Compliance', 'Risk mitigation', 'Innovation'],
                    'search_behaviors': ['Regulatory guidance', 'Compliance solutions', 'Security assessments'],
                    'preferred_channels': ['Search', 'Industry publications', 'LinkedIn']
                }
            ],
            'healthcare': [
                {
                    'name': 'Healthcare Administrator',
                    'job_title': 'Hospital Administrator',
                    'company_size': 'Large organization (500+ employees)',
                    'pain_points': ['Patient outcomes', 'Operational efficiency', 'Cost management'],
                    'goals': ['Improve patient care', 'Reduce costs', 'Streamline operations'],
                    'motivations': ['Patient care', 'Efficiency', 'Cost control'],
                    'search_behaviors': ['Healthcare solutions', 'Best practices', 'Outcome studies'],
                    'preferred_channels': ['Search', 'Medical journals', 'Industry events']
                }
            ],
            'marketing': [
                {
                    'name': 'Marketing Director',
                    'job_title': 'Marketing Director',
                    'company_size': 'Mid-market (100-1000 employees)',
                    'pain_points': ['Attribution', 'Campaign optimization', 'Budget allocation'],
                    'goals': ['Improve marketing ROI', 'Better insights', 'Scale successful campaigns'],
                    'motivations': ['Performance', 'Growth', 'Data-driven decisions'],
                    'search_behaviors': ['Marketing tools', 'Best practices', 'Case studies'],
                    'preferred_channels': ['Search', 'LinkedIn', 'Marketing publications']
                }
            ],
            'technology': [  # Fallback
                {
                    'name': 'Technology Leader',
                    'job_title': 'VP Engineering',
                    'company_size': 'Mid-market (100-1000 employees)',
                    'pain_points': ['Technical scalability', 'Team productivity', 'System reliability'],
                    'goals': ['Improve development velocity', 'Ensure system reliability', 'Drive innovation'],
                    'motivations': ['Technical excellence', 'Team success', 'Innovation'],
                    'search_behaviors': ['Technical solutions', 'Best practices', 'Tool evaluations'],
                    'preferred_channels': ['Search', 'Technical blogs', 'GitHub']
                }
            ]
        }
    
    def _customize_persona(self, base_persona: Dict, business_model: str, key_topics: List[str], 
                          value_props: List[str], competitors: List[Competitor] = None) -> Dict:
        """Customize a base persona with website-specific data."""
        
        # Deep copy base persona
        persona = {key: list(value) if isinstance(value, list) else value 
                  for key, value in base_persona.items()}
        
        # Adjust based on business model
        if business_model == 'b2c':
            persona['company_size'] = 'Individual/Consumer'
            persona['job_title'] = self._get_b2c_job_title(persona['job_title'])
        elif business_model == 'smb':
            persona['company_size'] = 'Small business (1-50 employees)'
        
        # Generate keywords based on topics and pain points
        keywords = self._generate_keywords(persona, key_topics, value_props)
        persona['keywords'] = keywords
        
        # Generate ad copy themes
        ad_copy_themes = self._generate_ad_copy_themes(persona, value_props)
        persona['ad_copy_themes'] = ad_copy_themes
        
        # Calculate confidence score
        confidence = self._calculate_confidence_score(persona, key_topics, value_props, competitors)
        persona['confidence_score'] = confidence
        
        return persona
    
    def _get_b2c_job_title(self, b2b_title: str) -> str:
        """Convert B2B job title to B2C equivalent."""
        b2c_mapping = {
            'CTO': 'Tech-Savvy Consumer',
            'VP Operations': 'Small Business Owner',
            'Product Manager': 'Professional User',
            'Marketing Director': 'Marketing Professional',
            'Hospital Administrator': 'Healthcare Professional'
        }
        return b2c_mapping.get(b2b_title, 'Consumer')
    
    def _generate_keywords(self, persona: Dict, key_topics: List[str], value_props: List[str]) -> List[str]:
        """Generate relevant keywords for the persona."""
        keywords = []
        
        # Job title-based keywords
        job_title = persona.get('job_title', '').lower()
        if 'cto' in job_title or 'technical' in job_title:
            keywords.extend(['technical solution', 'API integration', 'scalable platform'])
        elif 'marketing' in job_title:
            keywords.extend(['marketing tool', 'campaign optimization', 'ROI tracking'])
        elif 'operations' in job_title:
            keywords.extend(['operational efficiency', 'process automation', 'workflow management'])
        
        # Pain point-based keywords
        pain_points = persona.get('pain_points', [])
        for pain in pain_points:
            pain_lower = pain.lower()
            if 'cost' in pain_lower:
                keywords.extend(['cost reduction', 'budget optimization', 'affordable solution'])
            elif 'efficiency' in pain_lower:
                keywords.extend(['improve efficiency', 'streamline process', 'productivity tool'])
            elif 'integration' in pain_lower:
                keywords.extend(['easy integration', 'API connectivity', 'seamless workflow'])
        
        # Topic-based keywords
        for topic in key_topics[:3]:
            keywords.append(f"{topic} solution")
            keywords.append(f"best {topic}")
        
        # Remove duplicates and return top 10
        unique_keywords = list(set(keywords))
        return unique_keywords[:10]
    
    def _generate_ad_copy_themes(self, persona: Dict, value_props: List[str]) -> List[str]:
        """Generate ad copy themes for the persona."""
        themes = []
        
        # Goal-based themes
        goals = persona.get('goals', [])
        for goal in goals:
            goal_lower = goal.lower()
            if 'improve' in goal_lower:
                themes.append('improvement_focused')
            elif 'reduce' in goal_lower:
                themes.append('cost_savings')
            elif 'increase' in goal_lower or 'grow' in goal_lower:
                themes.append('growth_oriented')
        
        # Motivation-based themes
        motivations = persona.get('motivations', [])
        for motivation in motivations:
            motivation_lower = motivation.lower()
            if 'performance' in motivation_lower:
                themes.append('performance_driven')
            elif 'innovation' in motivation_lower:
                themes.append('innovation_focused')
            elif 'risk' in motivation_lower:
                themes.append('risk_mitigation')
        
        # Value proposition themes
        for value_prop in value_props[:2]:
            if len(value_prop) > 20:  # Only substantial value props
                themes.append('value_proposition')
        
        # Remove duplicates
        unique_themes = list(set(themes))
        return unique_themes[:5]
    
    def _calculate_confidence_score(self, persona: Dict, key_topics: List[str], 
                                  value_props: List[str], competitors: List[Competitor] = None) -> float:
        """Calculate confidence score for the persona."""
        base_confidence = 0.5
        
        # Higher confidence if we have key topics
        if key_topics:
            base_confidence += 0.2
        
        # Higher confidence if we have value propositions
        if value_props:
            base_confidence += 0.15
        
        # Higher confidence if we have competitor data
        if competitors:
            base_confidence += 0.1
        
        # Slight boost for complete personas
        if all(persona.get(field) for field in ['job_title', 'pain_points', 'goals']):
            base_confidence += 0.05
        
        return min(1.0, base_confidence)
    
    def _get_fallback_personas(self, business_model: str) -> List[Dict]:
        """Get basic fallback personas when analysis fails."""
        if business_model == 'b2c':
            return [{
                'name': 'Consumer User',
                'job_title': 'Consumer', 
                'company_size': 'Individual',
                'pain_points': ['Finding the right solution', 'Price sensitivity', 'Ease of use'],
                'goals': ['Solve immediate problem', 'Get value for money', 'Simple experience'],
                'motivations': ['Convenience', 'Value', 'Quality'],
                'search_behaviors': ['Product reviews', 'Price comparisons', 'How-to guides'],
                'preferred_channels': ['Search', 'Social media', 'Review sites'],
                'keywords': ['best solution', 'affordable option', 'easy to use'],
                'ad_copy_themes': ['value_focused', 'user_friendly'],
                'confidence_score': 0.3
            }]
        else:
            return [{
                'name': 'Business Decision Maker',
                'job_title': 'Business Manager',
                'company_size': 'SMB (10-100 employees)',
                'pain_points': ['Operational efficiency', 'Cost control', 'Growth challenges'],
                'goals': ['Improve operations', 'Reduce costs', 'Drive growth'],
                'motivations': ['Business results', 'Efficiency', 'ROI'],
                'search_behaviors': ['Business solutions', 'ROI information', 'Case studies'],
                'preferred_channels': ['Search', 'LinkedIn', 'Business publications'],
                'keywords': ['business solution', 'improve efficiency', 'ROI'],
                'ad_copy_themes': ['business_focused', 'roi_driven'],
                'confidence_score': 0.3
            }]
