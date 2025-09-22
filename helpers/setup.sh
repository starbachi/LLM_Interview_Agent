#!/bin/bash

# AI Interview Assistant Setup Script
echo "Setting up AI Interview Assistant..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "[OK] - Virtual environment detected: $VIRTUAL_ENV"
else
    echo "[WARNING] - No virtual environment detected. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[INFO] - Virtual environment created and activated"
fi

# Install system dependencies
echo "[INFO] - Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y ffmpeg

# Check if ffmpeg is installed
if command -v ffmpeg &> /dev/null; then
    echo "[OK] - ffmpeg installed successfully"
else
    echo "[ERROR] - ffmpeg installation failed"
fi

# Install Python packages
echo "[INFO] - Installing Python packages..."
pip install -r requirements.txt

# Check API configuration
echo "[INFO] - Checking API configuration..."
echo "/----------------------------------------/"

if [ -f "api/api.env" ]; then
    source api/api.env
    if [ -z "$NVIDIA_API_KEY" ]; then
        echo "[ERROR] - NVIDIA_API_KEY not set in api/api.env"
        echo "[INFO] - Please add your NVIDIA API key to api/api.env file"
    else
        echo "[OK] - NVIDIA API key found"
    fi
    
    if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "[ERROR] - GOOGLE_APPLICATION_CREDENTIALS not set in api/api.env"
        echo "[INFO] - Please add your Google Cloud credentials path to api/api.env file"
    else
        if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
            echo "[OK] - Google Cloud credentials file found"
        else
            echo "[ERROR] - Google Cloud credentials file not found at: $GOOGLE_APPLICATION_CREDENTIALS"
        fi
    fi
else
    echo "[ERROR] - api/api.env file not found"
    echo "[INFO] - Creating api directory and template api.env file..."
    mkdir -p api
    cat > api/api.env << EOF
EOF
    echo "[OK] - Template api/api.env created. Please update with your credentials."
fi
echo "[INFO] - If your API credentials are set. Please run: streamlit run streamlit_app.py"