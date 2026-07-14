#!/bin/bash
echo "Setting up CropGuard AI..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Starting CropGuard AI..."
python3 app.py
