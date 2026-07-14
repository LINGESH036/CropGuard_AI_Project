# 🌿 CropGuard AI — Crop Disease Detection System

A full-stack web application for intelligent crop disease detection using AI/ML simulation, built with **Python Flask**, **SQLite**, and **HTML/CSS/JS**.

---

## 🚀 Features

| Module | Features |
|--------|----------|
| **User Management** | Farmer/Expert/Admin roles, JWT-style sessions, profile management |
| **Crop Management** | Add/track crops, growth stages, field records |
| **AI Disease Detection** | CNN-based image analysis, confidence scores, severity ratings |
| **Disease Library** | 6+ diseases with causes, symptoms, treatments |
| **Treatment Recommendations** | Chemical + organic options with dosage |
| **Weather Monitoring** | Temperature/humidity tracking, disease risk prediction |
| **Analytics Dashboard** | Chart.js charts — disease trends, severity breakdown |
| **Alert System** | Auto-alerts for high-risk detections and weather |
| **Expert Consultation** | Farmer-to-expert query system with reply workflow |
| **AI Predictions** | Seasonal disease forecasts, early warning system |
| **Admin Panel** | User management, disease DB management, CSV export |

---

## 🛠 Tech Stack

- **Backend:** Python 3.10+, Flask 3.0, Flask-SQLAlchemy
- **Database:** SQLite (cropguard.db)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Charts:** Chart.js 4.4
- **Icons:** Font Awesome 6.5
- **Fonts:** Google Fonts (Outfit, Space Mono)
- **Security:** Werkzeug password hashing

---

## 📦 Installation & Setup

> ⚠️ **Important:** All commands below must be run from inside the `crop_disease_detection/` folder. If you get `No such file or directory: 'requirements.txt'`, it means you are in the wrong directory.

### Quick Start (Recommended)

**Windows** — double-click `run_windows.bat` or run it in Command Prompt.

**macOS/Linux** — open Terminal in the project folder and run:
```bash
bash run_unix.sh
```

### Manual Setup

```bash
# 1. Navigate INTO the project folder (this step is critical!)
cd crop_disease_detection

# Verify you are in the right place — requirements.txt must be listed:
ls          # macOS/Linux
dir         # Windows

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies (must be inside crop_disease_detection/)
pip install -r requirements.txt

# 5. Run the application
python app.py

# 6. Open browser
# http://localhost:5000
```

---

## 🔐 Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Expert | `expert1` | `expert123` |
| Farmer | Register yourself | — |

---

## 📁 Project Structure

```
crop_disease_detection/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── static/
│   └── uploads/              # Uploaded leaf images
└── templates/
    ├── base.html             # Base layout with sidebar
    ├── index.html            # Landing page
    ├── login.html            # Login page
    ├── register.html         # Registration page
    ├── dashboard.html        # Main dashboard
    ├── crops.html            # Crop listing
    ├── add_crop.html         # Add crop form
    ├── detect.html           # Disease detection upload
    ├── detection_result.html # AI result display
    ├── detections.html       # Detection history
    ├── diseases.html         # Disease library
    ├── disease_detail.html   # Disease detail view
    ├── weather.html          # Weather monitoring
    ├── analytics.html        # Charts & analytics
    ├── alerts.html           # Alert notifications
    ├── notifications.html    # System notifications
    ├── profile.html          # User profile
    ├── consult.html          # Expert consultation
    ├── expert_dashboard.html # Expert reply panel
    ├── predict.html          # AI predictions
    ├── admin.html            # Admin dashboard
    └── add_disease.html      # Add disease (admin)
```

---

## 🌟 Resume Highlights

- **AI/ML Integration:** Simulated CNN-based deep learning disease detection with confidence scoring
- **Full-Stack Development:** End-to-end Flask MVC architecture with SQLAlchemy ORM
- **Role-Based Access Control:** Three-tier user system (Farmer / Expert / Admin)
- **RESTful API Endpoints:** JSON API for notifications and weather simulation
- **Responsive Design:** Mobile-first CSS with CSS custom properties
- **Data Visualization:** Interactive Chart.js charts (doughnut, bar, line)
- **Security:** Password hashing, session management, route protection decorators
- **File Handling:** Secure image upload with validation and preprocessing
- **Database Design:** Normalized SQLite schema with 8 relational tables
- **Expert System:** Query-response workflow between farmers and agricultural experts

---

## 🔮 Future Enhancements (Mentioned in Resume)

- Real CNN model integration (TensorFlow/PyTorch)
- Real-time camera capture via WebRTC
- Actual weather API integration (OpenWeatherMap)
- Multilingual support (Tamil + English i18n)
- IoT sensor data ingestion
- Drone image analysis pipeline
- Flutter/React Native mobile app

---

## 📊 Database Schema

```
users → crops → disease_detections
             ↘ (linked optionally)
diseases (standalone reference library)
weather_data
notifications → users
alerts → users
expert_queries → users (farmer + expert)
```

---

*Built as a portfolio project demonstrating full-stack Python web development with AI/ML concepts.*
