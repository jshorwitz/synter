import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from contextlib import asynccontextmanager
from routers import sync, score, recommend, apply, audit, auth, website, reports, billing
from database import engine, init_db


security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials."""
    correct_username = secrets.compare_digest(
        credentials.username, os.getenv("APP_BASIC_AUTH_USER", "admin")
    )
    correct_password = secrets.compare_digest(
        credentials.password, os.getenv("APP_BASIC_AUTH_PASS", "change-me")
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Synter - Digital Marketing Intelligence Platform",
    description="Website analysis, competitor research, and multi-platform campaign management",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://synter.dev",
        "https://synter.railway.app",
        "https://*.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with auth dependency (except healthz and auth routes)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(billing.router, prefix="/billing", tags=["billing"], dependencies=[Depends(verify_credentials)])
app.include_router(website.router, prefix="/website", tags=["website"], dependencies=[Depends(verify_credentials)])
app.include_router(reports.router, prefix="/v1/reports", tags=["reports"], dependencies=[Depends(verify_credentials)])
app.include_router(sync.router, prefix="/sync", tags=["sync"], dependencies=[Depends(verify_credentials)])
app.include_router(score.router, prefix="/score", tags=["icp"], dependencies=[Depends(verify_credentials)])
app.include_router(recommend.router, prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(verify_credentials)])
app.include_router(apply.router, prefix="/apply", tags=["apply"], dependencies=[Depends(verify_credentials)])
app.include_router(audit.router, prefix="/audit", tags=["audit"], dependencies=[Depends(verify_credentials)])


@app.get("/healthz", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ppc-manager"}


@app.get("/", tags=["info"])
def root():
    """Root endpoint with service information."""
    return {
        "service": "Synter - Digital Marketing Intelligence Platform",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "Website Analysis",
            "Competitor Research", 
            "Persona Generation",
            "Multi-Platform Campaign Management"
        ]
    }
