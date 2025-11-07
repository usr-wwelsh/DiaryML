#!/bin/bash

echo "===================================="
echo "DiaryML - Your Private Creative Companion"
echo "===================================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        echo "Make sure Python 3.10+ is installed"
        exit 1
    fi

    echo "Virtual environment created successfully!"
    echo ""
fi

# Activate virtual environment
echo "[2/3] Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[3/3] Installing dependencies (this may take 5-10 minutes)..."
    echo ""
    cd backend
    pip install -r requirements.txt

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi

    cd ..
    echo ""
    echo "Dependencies installed successfully!"
    echo ""
else
    echo "[3/3] Dependencies already installed"
    echo ""
fi

# Start the server
echo "===================================="
echo "Starting DiaryML Server..."
echo "===================================="
echo ""
echo "Open your browser to: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

cd backend
python main.py
