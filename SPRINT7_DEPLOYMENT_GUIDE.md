# Sprint 7: Production Deployment Guide

## Overview
Sprint 7 focuses on production deployment and billing integration. This guide covers deployment to Railway with full Stripe integration.

## Pre-Deployment Checklist

### 1. Environment Variables Setup
Ensure the following environment variables are configured in Railway:

#### Backend (ppc-backend service)
```bash
# Core Configuration
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-production-secret-key

# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key  
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
MOCK_STRIPE=false

# API Keys
OPENAI_API_KEY=your_openai_api_key
SEMRUSH_API_KEY=your_semrush_api_key
SIMILARWEB_API_KEY=your_similarweb_api_key
BUILTWITH_API_KEY=your_builtwith_api_key

# Authentication
APP_BASIC_AUTH_USER=your_admin_username
APP_BASIC_AUTH_PASS=your_secure_password

# Google Ads (Optional)
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
GOOGLE_ADS_CLIENT_ID=your_oauth2_client_id
GOOGLE_ADS_CLIENT_SECRET=your_oauth2_client_secret
```

#### Frontend (web-frontend service)
```bash
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://api-synter.railway.app
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key
```

### 2. Stripe Configuration

#### Create Stripe Products
1. **Credit Packs**:
   - `credits_10` - 10 Credits ($10)
   - `credits_25` - 25 Credits ($20)  
   - `credits_50` - 50 Credits ($35)

2. **Subscriptions**:
   - `PRO` - Pro Plan ($49/month)
   - `ENTERPRISE` - Enterprise Plan ($199/month)

#### Configure Webhooks
Set up webhook endpoint in Stripe Dashboard:
- **Endpoint URL**: `https://api-synter.railway.app/api/v1/billing/stripe-webhook`
- **Events**: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

### 3. Database Setup
The application will automatically initialize the database on startup. For production, ensure PostgreSQL is configured with proper backups.

## Deployment Steps

### 1. Deploy to Railway
```bash
# Connect to Railway (if not already connected)
railway login

# Link to your Railway project
railway link

# Deploy both services
railway up
```

### 2. Configure Domains
- **Backend**: `api-synter.railway.app` 
- **Frontend**: Use Railway's generated domain or connect custom domain

### 3. Verify Deployment
Run the production test suite:
```bash
python test-sprint7-production.py
```

## Testing Production Deployment

### 1. Health Checks
- **Backend Health**: `GET https://api-synter.railway.app/health`
- **Frontend**: Verify site loads at your Railway URL

### 2. Billing Integration
- Test checkout session creation
- Verify Stripe webhook delivery
- Test report generation with credit consumption

### 3. Report Generation
Test all three report types:
- **Tracking Readiness** (1 credit)
- **Spend Baseline** (2 credits)  
- **Competitor Snapshot** (3 credits)

## Production Features

### ✅ Completed in Sprint 7
- [x] Production deployment configuration
- [x] Stripe integration for live payments
- [x] CORS configuration for production domains
- [x] Environment variable management
- [x] Frontend billing component integration
- [x] Production Docker setup
- [x] Health checks and monitoring endpoints
- [x] Comprehensive test suite

### 🔄 Billing Flow
1. User selects credit pack or subscription
2. Frontend creates Stripe checkout session via backend API
3. User redirected to Stripe Checkout
4. Payment processed by Stripe
5. Webhook updates user credits/subscription
6. User can generate reports with credits

### 📊 Report Types & Credits
- **Tracking Readiness**: 1 credit - Analyzes website tracking setup
- **Spend Baseline**: 2 credits - Aggregates spend data from ad platforms  
- **Competitor Snapshot**: 3 credits - Comprehensive SEMrush competitive intelligence

## Monitoring & Maintenance

### Health Endpoints
- **Backend**: `/health` - Service health status
- **Database**: Automatic connection testing
- **External APIs**: Service dependency checks

### Logging
- Production logs via Railway dashboard
- Error tracking and alerting
- API usage and performance monitoring

### Security
- HTTPS enforced on all endpoints
- Secure cookie handling
- API key encryption at rest
- Basic auth for admin endpoints

## Troubleshooting

### Common Issues
1. **Stripe Webhook Failures**: Verify webhook URL and secret
2. **CORS Errors**: Check allowed origins in backend CORS config
3. **Database Connection**: Verify PostgreSQL URL and credentials
4. **API Key Issues**: Ensure all required API keys are set

### Support Commands
```bash
# Check backend logs
railway logs --service ppc-backend

# Check frontend logs  
railway logs --service web-frontend

# Connect to production database
railway connect postgres

# Run production tests
python test-sprint7-production.py
```

## Next Steps (Sprint 8+)
- Advanced analytics dashboard
- User authentication and multi-tenancy
- Advanced reporting features
- Performance optimization
- Enhanced monitoring and alerting
