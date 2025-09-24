import os
from typing import Optional
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class GoogleAdsClientFactory:
    """Factory for creating Google Ads API clients."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self) -> GoogleAdsClient:
        """Get or create a Google Ads client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> GoogleAdsClient:
        """Create a Google Ads client from environment variables."""
        credentials = {
            "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
            "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        }
        
        # Validate required credentials
        missing = [k for k, v in credentials.items() if not v]
        if missing:
            raise ValueError(f"Missing Google Ads credentials: {missing}")
        
        try:
            client = GoogleAdsClient.load_from_dict(credentials)
            logger.info("Google Ads client created successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to create Google Ads client: {e}")
            raise
    
    @property
    def customer_id(self) -> str:
        """Get the customer ID from environment."""
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
        if not customer_id:
            raise ValueError("GOOGLE_ADS_CUSTOMER_ID not set")
        return customer_id.replace("-", "")  # Remove dashes
    
    def execute_query(self, query: str, customer_id: Optional[str] = None) -> list:
        """Execute a GAQL query and return results."""
        if not customer_id:
            customer_id = self.customer_id
            
        client = self.get_client()
        ga_service = client.get_service("GoogleAdsService")
        
        try:
            response = ga_service.search_stream(
                customer_id=customer_id,
                query=query
            )
            
            results = []
            for batch in response:
                for row in batch.results:
                    results.append(row)
            
            logger.info(f"Query executed successfully. Returned {len(results)} rows")
            return results
            
        except GoogleAdsException as ex:
            logger.error(f"Request failed with status {ex.error.code().name}")
            for error in ex.failure.errors:
                logger.error(f"Error: {error.message}")
            raise
    
    def execute_mutate(self, operations: list, service_name: str, 
                      customer_id: Optional[str] = None, validate_only: bool = True) -> dict:
        """Execute a mutate operation with optional validation."""
        if not customer_id:
            customer_id = self.customer_id
            
        client = self.get_client()
        service = client.get_service(service_name)
        
        try:
            with client.configure().operation_settings(validate_only=validate_only):
                if service_name == "CampaignCriterionService":
                    response = service.mutate_campaign_criteria(
                        customer_id=customer_id, operations=operations
                    )
                elif service_name == "AdGroupCriterionService":
                    response = service.mutate_ad_group_criteria(
                        customer_id=customer_id, operations=operations
                    )
                elif service_name == "CampaignBudgetService":
                    response = service.mutate_campaign_budgets(
                        customer_id=customer_id, operations=operations
                    )
                else:
                    raise ValueError(f"Unsupported service: {service_name}")
            
            result = {
                "status": "success" if not validate_only else "validation_success",
                "resource_names": [r.resource_name for r in response.results] if hasattr(response, 'results') else [],
                "partial_failure_error": response.partial_failure_error if hasattr(response, 'partial_failure_error') else None
            }
            
            logger.info(f"Mutate operation {'validated' if validate_only else 'executed'} successfully")
            return result
            
        except GoogleAdsException as ex:
            logger.error(f"Mutate operation failed: {ex.error.code().name}")
            error_details = []
            for error in ex.failure.errors:
                error_details.append(error.message)
                logger.error(f"Error: {error.message}")
            
            return {
                "status": "error",
                "error_code": ex.error.code().name,
                "errors": error_details
            }


# Global instance
ads_client = GoogleAdsClientFactory()
