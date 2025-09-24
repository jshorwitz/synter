import os
import logging
import stripe
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import json
import uuid

logger = logging.getLogger(__name__)

class BillingService:
    """Stripe billing integration for subscriptions and credit packs."""
    
    def __init__(self):
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY') 
        self.stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.mock_mode = os.getenv('MOCK_STRIPE', 'false').lower() == 'true'
        
        # Plan configuration
        self.plans = {
            "PRO": {
                "name": "Pro Plan",
                "price_cents": 4900,  # $49/month
                "monthly_credits": 20,
                "can_publish": True,
                "max_users": 5,
                "features": ["Unlimited reports", "Campaign publishing", "Priority support"]
            },
            "ENTERPRISE": {
                "name": "Enterprise Plan", 
                "price_cents": 14900,  # $149/month
                "monthly_credits": 100,
                "can_publish": True,
                "max_users": 25,
                "features": ["Unlimited reports", "Campaign publishing", "API access", "Custom integrations"]
            }
        }
        
        # Credit pack configuration
        self.credit_packs = [
            {
                "id": "pack_10",
                "name": "Starter Pack",
                "credits": 10,
                "price_cents": 1900,  # $19
                "description": "Perfect for small businesses getting started",
                "is_popular": False
            },
            {
                "id": "pack_25", 
                "name": "Growth Pack",
                "credits": 25,
                "price_cents": 3900,  # $39 (save $8.5)
                "description": "Great for growing businesses",
                "is_popular": True,
                "discount_percent": 18
            },
            {
                "id": "pack_50",
                "name": "Scale Pack", 
                "credits": 50,
                "price_cents": 6900,  # $69 (save $25.5)
                "description": "For businesses at scale",
                "is_popular": False,
                "discount_percent": 27
            }
        ]
        
        if not self.mock_mode and self.stripe_secret_key:
            stripe.api_key = self.stripe_secret_key
            logger.info("Stripe billing integration enabled")
        else:
            logger.info("Using Stripe mock mode")
            self.mock_mode = True
    
    async def create_checkout_session(
        self, 
        workspace_id: str,
        product_type: str,  # "subscription" or "credit_pack"
        product_id: str,    # Plan name or credit pack ID
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None
    ) -> Dict:
        """Create Stripe checkout session."""
        
        try:
            if self.mock_mode:
                return self._mock_checkout_session(product_type, product_id, workspace_id)
            
            # Get product details
            if product_type == "subscription":
                if product_id not in self.plans:
                    raise ValueError(f"Invalid plan: {product_id}")
                
                plan = self.plans[product_id]
                session_data = {
                    'mode': 'subscription',
                    'line_items': [{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': plan['name'],
                                'description': f"Monthly subscription with {plan['monthly_credits']} credits"
                            },
                            'unit_amount': plan['price_cents'],
                            'recurring': {'interval': 'month'}
                        },
                        'quantity': 1
                    }],
                    'metadata': {
                        'workspace_id': workspace_id,
                        'product_type': product_type,
                        'plan_name': product_id
                    }
                }
                
            elif product_type == "credit_pack":
                credit_pack = next((pack for pack in self.credit_packs if pack['id'] == product_id), None)
                if not credit_pack:
                    raise ValueError(f"Invalid credit pack: {product_id}")
                
                session_data = {
                    'mode': 'payment',
                    'line_items': [{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': credit_pack['name'],
                                'description': f"{credit_pack['credits']} report credits"
                            },
                            'unit_amount': credit_pack['price_cents']
                        },
                        'quantity': 1
                    }],
                    'metadata': {
                        'workspace_id': workspace_id,
                        'product_type': product_type,
                        'credit_pack_id': product_id,
                        'credits': str(credit_pack['credits'])
                    }
                }
            else:
                raise ValueError(f"Invalid product type: {product_type}")
            
            # Common session configuration
            session_data.update({
                'success_url': success_url,
                'cancel_url': cancel_url,
                'billing_address_collection': 'required'
            })
            
            if customer_email:
                session_data['customer_email'] = customer_email
            
            # Create session
            session = stripe.checkout.Session.create(**session_data)
            
            logger.info(f"Created Stripe checkout session: {session.id}")
            
            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
                "session": session
            }
            
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """Handle Stripe webhook events."""
        
        try:
            if self.mock_mode:
                return {"success": True, "mock": True}
            
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            
            logger.info(f"Processing Stripe webhook: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'checkout.session.completed':
                return await self._handle_checkout_completed(event)
            elif event['type'] == 'customer.subscription.created':
                return await self._handle_subscription_created(event)
            elif event['type'] == 'customer.subscription.updated':
                return await self._handle_subscription_updated(event)
            elif event['type'] == 'customer.subscription.deleted':
                return await self._handle_subscription_canceled(event)
            elif event['type'] == 'invoice.payment_succeeded':
                return await self._handle_payment_succeeded(event)
            else:
                logger.info(f"Unhandled webhook event: {event['type']}")
                return {"success": True, "handled": False}
            
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_checkout_completed(self, event: Dict) -> Dict:
        """Handle completed checkout session."""
        session = event['data']['object']
        metadata = session.get('metadata', {})
        
        workspace_id = metadata.get('workspace_id')
        product_type = metadata.get('product_type')
        
        if not workspace_id:
            logger.error("No workspace_id in checkout session metadata")
            return {"success": False, "error": "Missing workspace_id"}
        
        from simple_database import SessionLocal, Workspace, BillingEvent
        
        db = SessionLocal()
        try:
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                logger.error(f"Workspace not found: {workspace_id}")
                return {"success": False, "error": "Workspace not found"}
            
            if product_type == "credit_pack":
                # Handle credit pack purchase
                credits = int(metadata.get('credits', 0))
                credit_pack_id = metadata.get('credit_pack_id')
                
                # Add credits to workspace
                workspace.report_credits += credits
                
                # Record billing event
                billing_event = BillingEvent(
                    id=str(uuid.uuid4()),
                    workspace_id=workspace_id,
                    event_type="credits_purchased",
                    stripe_event_id=event['id'],
                    amount=session['amount_total'],
                    credits_added=credits,
                    product_name=f"Credit Pack - {credits} credits",
                    metadata_json=json.dumps(metadata),
                    processed=True
                )
                
                db.add(billing_event)
                db.commit()
                
                logger.info(f"Added {credits} credits to workspace {workspace_id}")
                
            elif product_type == "subscription":
                # Handle subscription creation
                plan_name = metadata.get('plan_name')
                
                if plan_name in self.plans:
                    plan = self.plans[plan_name]
                    
                    # Update workspace with Pro features
                    workspace.plan = plan_name
                    workspace.can_publish = plan['can_publish']
                    workspace.stripe_customer_id = session.get('customer')
                    workspace.stripe_subscription_id = session.get('subscription')
                    
                    # Record billing event
                    billing_event = BillingEvent(
                        id=str(uuid.uuid4()),
                        workspace_id=workspace_id,
                        event_type="subscription_created",
                        stripe_event_id=event['id'],
                        amount=session['amount_total'],
                        product_name=plan['name'],
                        plan_changed_to=plan_name,
                        metadata_json=json.dumps(metadata),
                        processed=True
                    )
                    
                    db.add(billing_event)
                    db.commit()
                    
                    logger.info(f"Activated {plan_name} plan for workspace {workspace_id}")
            
            return {"success": True, "workspace_id": workspace_id}
            
        finally:
            db.close()
    
    async def get_workspace_entitlements(self, workspace_id: str) -> Dict:
        """Get current entitlements for a workspace."""
        
        from simple_database import SessionLocal, Workspace, Subscription
        
        db = SessionLocal()
        try:
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            
            if not workspace:
                # Create default free workspace
                workspace = Workspace(
                    id=workspace_id,
                    name="Default Workspace",
                    plan="FREE",
                    report_credits=3,
                    can_publish=False
                )
                db.add(workspace)
                db.commit()
                db.refresh(workspace)
            
            # Check if credits need to be reset (monthly)
            if workspace.credits_reset_date and workspace.credits_reset_date < date.today():
                await self._reset_monthly_credits(workspace_id, db)
                db.refresh(workspace)
            
            # Get active subscription if any
            subscription = db.query(Subscription).filter(
                Subscription.workspace_id == workspace_id,
                Subscription.is_active == True
            ).first()
            
            return {
                "workspace_id": workspace_id,
                "plan": workspace.plan,
                "report_credits": workspace.report_credits,
                "can_publish": workspace.can_publish,
                "reports_generated_this_month": workspace.reports_generated_this_month,
                "subscription": {
                    "active": subscription is not None,
                    "plan_name": subscription.plan_name if subscription else None,
                    "status": subscription.status if subscription else None,
                    "next_billing": subscription.current_period_end if subscription else None
                } if subscription else None
            }
            
        finally:
            db.close()
    
    async def check_report_access(self, workspace_id: str, report_type: str) -> Dict:
        """Check if workspace can generate a report."""
        
        entitlements = await self.get_workspace_entitlements(workspace_id)
        
        # Get report cost
        from services.credit_manager import credit_manager
        cost = credit_manager.get_report_cost(report_type)
        
        # Check credits
        has_credits = entitlements['report_credits'] >= cost
        
        # Check plan limits
        plan = entitlements['plan']
        can_generate = True
        limit_reason = None
        
        if plan == "FREE":
            # Free plan limits
            if entitlements['reports_generated_this_month'] >= 3:
                can_generate = False
                limit_reason = "Free plan monthly limit reached (3 reports)"
        
        return {
            "can_generate": has_credits and can_generate,
            "has_credits": has_credits,
            "credits_available": entitlements['report_credits'],
            "credits_needed": cost,
            "plan": plan,
            "limit_reason": limit_reason,
            "upgrade_required": not has_credits or not can_generate
        }
    
    async def consume_report_credits(self, workspace_id: str, report_type: str, report_id: str) -> Dict:
        """Consume credits for report generation and update workspace."""
        
        from simple_database import SessionLocal, Workspace, BillingEvent
        from services.credit_manager import credit_manager
        
        # Check access first
        access_check = await self.check_report_access(workspace_id, report_type)
        if not access_check['can_generate']:
            return {
                "success": False,
                "error": "insufficient_access",
                "reason": access_check.get('limit_reason', 'Insufficient credits or plan limits'),
                "upgrade_required": access_check['upgrade_required']
            }
        
        cost = credit_manager.get_report_cost(report_type)
        
        db = SessionLocal()
        try:
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                return {"success": False, "error": "workspace_not_found"}
            
            # Deduct credits
            workspace.report_credits -= cost
            workspace.reports_generated_this_month += 1
            workspace.last_report_generated = datetime.utcnow()
            
            # Record billing event
            billing_event = BillingEvent(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                event_type="report_generated",
                credits_consumed=cost,
                product_name=f"{report_type} Report",
                metadata_json=json.dumps({
                    "report_id": report_id,
                    "report_type": report_type
                }),
                processed=True
            )
            
            db.add(billing_event)
            db.commit()
            
            logger.info(f"Consumed {cost} credits for {report_type} report in workspace {workspace_id}")
            
            return {
                "success": True,
                "credits_consumed": cost,
                "credits_remaining": workspace.report_credits
            }
            
        finally:
            db.close()
    
    async def _reset_monthly_credits(self, workspace_id: str, db: Any) -> None:
        """Reset monthly credits for a workspace."""
        
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            return
        
        # Get plan credits
        if workspace.plan == "PRO":
            monthly_credits = self.plans["PRO"]["monthly_credits"]
        elif workspace.plan == "ENTERPRISE":
            monthly_credits = self.plans["ENTERPRISE"]["monthly_credits"]
        else:
            monthly_credits = 3  # Free plan
        
        # Reset credits and counters
        workspace.report_credits = monthly_credits
        workspace.reports_generated_this_month = 0
        workspace.credits_reset_date = date.today() + timedelta(days=30)  # Next reset
        
        db.commit()
        
        logger.info(f"Reset monthly credits for workspace {workspace_id}: {monthly_credits} credits")
    
    def get_pricing_info(self) -> Dict:
        """Get pricing information for frontend."""
        
        return {
            "plans": self.plans,
            "credit_packs": self.credit_packs,
            "report_costs": {
                "TRACKING_READINESS": 1,
                "SPEND_BASELINE": 2, 
                "COMPETITOR_SNAPSHOT": 3
            },
            "free_plan": {
                "monthly_credits": 3,
                "monthly_reports": 3,
                "can_publish": False
            }
        }
    
    # Mock methods for development
    def _mock_checkout_session(self, product_type: str, product_id: str, workspace_id: str) -> Dict:
        """Mock checkout session for development."""
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        
        return {
            "success": True,
            "session_id": session_id,
            "checkout_url": f"https://checkout.stripe.com/pay/{session_id}",
            "mock": True,
            "product_type": product_type,
            "product_id": product_id,
            "workspace_id": workspace_id
        }
    
    async def _handle_subscription_created(self, event: Dict) -> Dict:
        """Handle subscription creation webhook."""
        # Implementation would mirror checkout completed for subscriptions
        return {"success": True, "event": "subscription_created"}
    
    async def _handle_subscription_updated(self, event: Dict) -> Dict:
        """Handle subscription update webhook."""
        return {"success": True, "event": "subscription_updated"}
    
    async def _handle_subscription_canceled(self, event: Dict) -> Dict:
        """Handle subscription cancellation webhook."""
        return {"success": True, "event": "subscription_canceled"}
    
    async def _handle_payment_succeeded(self, event: Dict) -> Dict:
        """Handle successful payment webhook."""
        return {"success": True, "event": "payment_succeeded"}
