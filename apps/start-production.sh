#!/bin/bash

# Production startup script for Synter PPC Backend

echo "Starting Synter PPC Backend in production mode..."

# Set production environment
export ENVIRONMENT=production

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing/updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python -c "from database import init_db; init_db()"

# Start the application
echo "Starting FastAPI server..."
exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
