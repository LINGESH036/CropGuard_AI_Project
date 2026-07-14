@echo off
echo Setting up CropGuard AI...
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
echo Starting CropGuard AI...
python app.py
