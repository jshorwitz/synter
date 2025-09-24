# Sourcegraph PPC Manager - Backend

A Google Ads management and optimization service built with FastAPI that integrates with the Synter platform.

## Features

- **Google Ads Integration**: OAuth2 authentication and GAQL queries
- **Data Ingestion**: Sync campaigns, ad groups, keywords, and search terms
- **ICP Scoring**: Rule-based relevance scoring for Sourcegraph's target audience
- **Smart Recommendations**: Automated suggestions for negative keywords, pauses, and budget shifts
- **Safe Operations**: All writes support dry-run validation with audit logging
- **Policy Gates**: Built-in guardrails for safe automated changes

## Quick Start

### Prerequisites

- Docker and docker-compose
- Google Ads API access (developer token, OAuth2 credentials)
- PostgreSQL database (provided in docker-compose)

### 1. Environment Setup

Copy and configure environment variables:

```bash
cp .env.example .env
# Edit .env with your Google Ads API credentials
```

Required credentials:
- `GOOGLE_ADS_DEVELOPER_TOKEN`: Your developer token
- `GOOGLE_ADS_CLIENT_ID`: OAuth2 client ID  
- `GOOGLE_ADS_CLIENT_SECRET`: OAuth2 client secret
- `GOOGLE_ADS_REFRESH_TOKEN`: OAuth2 refresh token
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`: MCC customer ID (digits only)
- `GOOGLE_ADS_CUSTOMER_ID`: Target account ID (digits only)

### 2. Start Services

```bash
make dev
# Or: docker-compose up --build
```

The API will be available at `http://localhost:8000`

### 3. Initial Data Sync

```bash
# Sync all data from Google Ads (last 90 days)
make sync

# Run ICP scoring on keywords and search terms
make score

# Generate recommendations
make recs

# Test recommendations with dry-run
make dryrun
```

## API Endpoints

### Core Operations

- `GET /healthz` - Health check
- `GET /auth/google_ads/status` - Check API connection

### Data Sync

- `GET /sync/keywords?days=90` - Sync keywords and metrics
- `GET /sync/search_terms?days=30` - Sync search terms
- `GET /sync/campaigns?days=30` - Sync campaign budgets
- `POST /sync/full_sync` - Sync all data

### ICP Scoring

- `POST /score/icp?level=keyword&limit=1000` - Score keywords
- `POST /score/icp?level=term&limit=1000` - Score search terms
- `GET /score/icp/stats` - Get scoring statistics
- `GET /score/icp/sample?level=keyword&score_range=low` - Get samples

### Recommendations

- `GET /recommendations/?types=neg,pause,budget&limit=50` - Get recommendations
- `POST /recommendations/generate?types=neg,pause,budget` - Generate new recommendations
- `PUT /recommendations/{id}/status?status=applied` - Update status

### Apply Operations (with dry-run support)

- `POST /apply/negative_keyword` - Add negative keyword
- `POST /apply/pause_keyword` - Pause keyword
- `POST /apply/adjust_budget` - Adjust campaign budget
- `POST /apply/dry_run_all` - Bulk dry-run recommendations

### Audit & Logging

- `GET /audit/?since=2025-01-01&limit=100` - Get audit logs
- `GET /audit/summary?days=30` - Get audit summary
- `GET /audit/{id}` - Get audit log details

## Data Model

### Core Entities

- **Campaigns**: Budget and status information
- **AdGroups**: Campaign subdivisions
- **Keywords**: Targetable keywords with ICP scores
- **SearchTerms**: Actual user queries with ICP scores
- **DailyMetrics**: Performance data (impressions, clicks, cost, conversions)

### ML/Scoring

- **Recommendations**: Generated optimization suggestions
- **AuditLog**: Complete history of all operations

## ICP Scoring System

The system scores keywords and search terms (0-100) based on fit for Sourcegraph's ICP:

### Scoring Rules

- **Start**: 50 (neutral)
- **Brand match**: +40 (sourcegraph, sourcegraph enterprise, etc.)
- **Include terms**: +25 (semantic code search, code discovery, etc.)
- **Exclude terms**: -30 (homework, tutorial, student, etc.)
- **Free/open source** (without enterprise): -15

### Categories

- **High fit (70-100)**: Strong ICP match, increase investment
- **Medium fit (40-69)**: Moderate relevance, monitor closely  
- **Low fit (0-39)**: Poor match, consider negative keywords or pausing

## Recommendation Engine

### 1. Negative Keywords
**Trigger**: ICP score < 40 + spend ≥ $300 (7 days) + 0 conversions  
**Action**: Add campaign-level negative keyword (exact match)

### 2. Pause Keywords  
**Trigger**: ICP score < 50 + spend ≥ $500 (14 days) + conversion rate < account 25th percentile  
**Action**: Pause ad group criterion

### 3. Budget Shifts
**Trigger**: High-fit campaigns (≥80 ICP) budget-constrained OR low-fit campaigns (<40 ICP) overspending  
**Action**: Suggest ±10-20% budget reallocation

### Policy Gates

- Minimum 20 conversions in last 30 days (data sufficiency)
- No budget below $100/day
- Changes >20% require manual approval
- All operations support `validate_only=true` dry-run

## Development

### Local Development

```bash
# Set up Python environment
make setup
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
make test

# Code quality
make lint
make typecheck
```

### Testing

```bash
# Unit tests
make test

# Integration tests (requires Google Ads credentials)
make test-integration

# API testing
make test-api
```

## Configuration

### Authentication

Basic auth is used for MVP (username/password in headers):
- Username: `APP_BASIC_AUTH_USER` (default: admin)
- Password: `APP_BASIC_AUTH_PASS` (default: change-me)

### Database

Supports PostgreSQL (production) and SQLite (development):
- PostgreSQL: `postgresql://user:pass@host:port/db`
- SQLite: `sqlite:///./ppc.db`

## Deployment

### Production Checklist

1. Set strong `APP_BASIC_AUTH_PASS`
2. Use PostgreSQL for `DATABASE_URL`
3. Store Google Ads credentials securely
4. Enable HTTPS/TLS
5. Configure log retention
6. Set up monitoring and alerting

### Docker Deployment

```bash
# Build and run
docker build -t ppc-manager .
docker run -p 8000:8000 --env-file .env ppc-manager
```

## Troubleshooting

### Common Issues

**Authentication Error**
- Check developer token status and whitelist
- Verify OAuth client credentials
- Ensure refresh token is valid
- Confirm login_customer_id format (digits only)

**Empty Data**
- Check customer ID access permissions  
- Verify date ranges in queries
- Ensure search term reporting is enabled

**Policy Blocks**
- Budget changes >20% require approval flag
- Minimum $100/day budget enforced
- Need ≥20 conversions for budget recommendations

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check Google Ads connection
curl -u admin:change-me http://localhost:8000/auth/google_ads/status

# View recent audit logs
curl -u admin:change-me http://localhost:8000/audit/summary
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Next.js UI    │    │   Google Ads    │
│   (Synter Web)  │    │      API        │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          │ HTTP/REST            │ GAQL/Mutate
          │                      │
    ┌─────┴─────────────────────┴─────┐
    │         FastAPI Service          │
    │  ┌─────────┬─────────┬─────────┐│
    │  │  Sync   │  Score  │ Recommend││
    │  └─────────┴─────────┴─────────┘│
    │  ┌─────────┬─────────┬─────────┐│
    │  │  Apply  │  Audit  │  Auth   ││
    │  └─────────┴─────────┴─────────┘│
    └─────────────────┬───────────────┘
                      │
              ┌───────┴───────┐
              │   PostgreSQL   │
              │   Database     │
              └───────────────┘
```

## Contributing

1. Follow existing code style (Black, isort, flake8)
2. Add tests for new features
3. Update documentation
4. Test with `validate_only=true` first
5. Include audit logging for all mutations

## License

Part of the Synter platform. See main project license.
