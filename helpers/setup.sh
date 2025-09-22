#!/bin/bash

# AI Interview Assistant Setup Script
echo "Setting up AI Interview Assistant..."

# Ensure we're in project root
cd "$(dirname "$0")"

# Check for virtual environment
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "[OK] - Virtual environment detected: $VIRTUAL_ENV"
else
    if [[ ! -d "venv" ]]; then
        echo "[INFO] - No virtual environment found. Creating one..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    echo "[OK] - Virtual environment activated: $(pwd)/venv"
fi

# Upgrade pip
python -m pip install --upgrade pip

# Install system dependencies (Debian/Ubuntu only)
if command -v apt-get &> /dev/null; then
    echo "[INFO] - Installing system dependencies..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg
fi

# Check if ffmpeg is installed
if command -v ffmpeg &> /dev/null; then
    echo "[OK] - ffmpeg installed successfully"
else
    echo "[WARNING] - ffmpeg not found. Please install manually."
fi

# Install Python packages
echo "[INFO] - Installing Python packages..."
pip install -r ../requirements.txt

# Check API configuration
echo "[INFO] - Checking API configuration..."
echo "/----------------------------------------/"

if [[ -f "api/api.env" ]]; then
    source api/api.env

    [[ -z "$NVIDIA_API_KEY" ]] && \
      echo "[ERROR] - NVIDIA_API_KEY not set in api/api.env" || \
      echo "[OK] - NVIDIA_API_KEY found"

    if [[ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
        echo "[ERROR] - GOOGLE_APPLICATION_CREDENTIALS not set in api/api.env"
    elif [[ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
        echo "[OK] - Google Cloud credentials file found"
    else
        echo "[ERROR] - Google Cloud credentials file not found at: $GOOGLE_APPLICATION_CREDENTIALS"
    fi
else
    echo "[ERROR] - api/api.env file not found"
    echo "[INFO] - Creating api directory and template api.env file..."
    mkdir -p api
    cat > api/api.env << EOF
NVIDIA_API_KEY=
GOOGLE_APPLICATION_CREDENTIALS=
EOF
    echo "[OK] - Template api/api.env created. Please update with your credentials."
fi

echo "[INFO] - Setup complete. Run: streamlit run streamlit_app.py"
