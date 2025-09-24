import logging
from typing import Dict, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class CreditManager:
    """Manage credit usage and billing for reports."""
    
    # Report type costs
    REPORT_COSTS = {
        "TRACKING_READINESS": 1,
        "SPEND_BASELINE": 2,
        "COMPETITOR_SNAPSHOT": 3
    }
    
    def __init__(self):
        # In production, this would connect to your billing database
        # For now, we'll use a simple in-memory tracker
        self.workspace_credits = {}
        self.usage_log = []
    
    def get_report_cost(self, report_type: str) -> int:
        """Get credit cost for a report type."""
        return self.REPORT_COSTS.get(report_type, 1)
    
    def check_credits_available(self, workspace_id: str, report_type: str) -> Dict:
        """Check if workspace has enough credits for a report."""
        cost = self.get_report_cost(report_type)
        available = self.get_workspace_credits(workspace_id)
        
        return {
            "has_credits": available >= cost,
            "credits_available": available,
            "credits_needed": cost,
            "credits_remaining": max(0, available - cost)
        }
    
    def get_workspace_credits(self, workspace_id: str) -> int:
        """Get available credits for a workspace."""
        # Default: Free tier gets 3 credits
        if workspace_id not in self.workspace_credits:
            self.workspace_credits[workspace_id] = 3
        
        return self.workspace_credits[workspace_id]
    
    def consume_credits(self, workspace_id: str, report_type: str, report_id: str, user_id: str) -> Dict:
        """Consume credits for a report generation."""
        cost = self.get_report_cost(report_type)
        available = self.get_workspace_credits(workspace_id)
        
        if available < cost:
            logger.warning(f"Insufficient credits for {workspace_id}: needed {cost}, have {available}")
            return {
                "success": False,
                "error": "insufficient_credits",
                "credits_available": available,
                "credits_needed": cost
            }
        
        # Deduct credits
        self.workspace_credits[workspace_id] = available - cost
        
        # Log usage
        usage_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "report_id": report_id,
            "report_type": report_type,
            "credits_consumed": cost,
            "credits_remaining": self.workspace_credits[workspace_id]
        }
        
        self.usage_log.append(usage_entry)
        
        logger.info(f"Credits consumed: {workspace_id} used {cost} credits for {report_type}")
        
        return {
            "success": True,
            "credits_consumed": cost,
            "credits_remaining": self.workspace_credits[workspace_id]
        }
    
    def add_credits(self, workspace_id: str, credits: int, source: str = "purchase") -> Dict:
        """Add credits to a workspace."""
        current = self.get_workspace_credits(workspace_id)
        new_total = current + credits
        self.workspace_credits[workspace_id] = new_total
        
        # Log credit addition
        credit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "workspace_id": workspace_id,
            "credits_added": credits,
            "source": source,
            "new_total": new_total
        }
        
        self.usage_log.append(credit_entry)
        
        logger.info(f"Credits added: {workspace_id} gained {credits} credits from {source}")
        
        return {
            "success": True,
            "credits_added": credits,
            "new_total": new_total
        }
    
    def get_usage_stats(self, workspace_id: str) -> Dict:
        """Get usage statistics for a workspace."""
        workspace_usage = [
            entry for entry in self.usage_log 
            if entry.get("workspace_id") == workspace_id
        ]
        
        total_reports = len([
            entry for entry in workspace_usage 
            if "report_type" in entry
        ])
        
        credits_consumed = sum([
            entry.get("credits_consumed", 0) 
            for entry in workspace_usage 
            if "credits_consumed" in entry
        ])
        
        report_types = {}
        for entry in workspace_usage:
            if "report_type" in entry:
                report_type = entry["report_type"]
                report_types[report_type] = report_types.get(report_type, 0) + 1
        
        return {
            "workspace_id": workspace_id,
            "credits_available": self.get_workspace_credits(workspace_id),
            "total_reports_generated": total_reports,
            "total_credits_consumed": credits_consumed,
            "report_breakdown": report_types,
            "recent_usage": workspace_usage[-10:]  # Last 10 entries
        }
    
    def get_all_workspaces_stats(self) -> Dict:
        """Get stats for all workspaces."""
        all_stats = {}
        for workspace_id in self.workspace_credits:
            all_stats[workspace_id] = self.get_usage_stats(workspace_id)
        
        return {
            "total_workspaces": len(self.workspace_credits),
            "workspace_stats": all_stats,
            "system_totals": {
                "total_credits_distributed": sum(self.workspace_credits.values()),
                "total_usage_events": len(self.usage_log)
            }
        }

# Global credit manager instance
credit_manager = CreditManager()
