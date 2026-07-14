from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import sqlite3, os, random, json, csv
from io import StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cropguard_secret_2024'
app.config['DATABASE'] = 'cropguard.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ─────────────────────────── JINJA2 FILTERS ────────────────────────────────
def format_datetime(value, fmt='%d %b %Y, %H:%M'):
    """Convert string datetime from SQLite to formatted string."""
    if not value:
        return '—'
    if isinstance(value, str):
        for pattern in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(value[:len(pattern)+2], pattern).strftime(fmt)
            except ValueError:
                try:
                    return datetime.strptime(value[:19], pattern).strftime(fmt)
                except:
                    continue
        return value
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return str(value)

def format_date(value, fmt='%d %b %Y'):
    return format_datetime(value, fmt)

def format_short(value):
    return format_datetime(value, '%d %b')

def format_month_year(value):
    return format_datetime(value, '%b %Y')

app.jinja_env.filters['fdt'] = format_datetime
app.jinja_env.filters['fdate'] = format_date
app.jinja_env.filters['fshort'] = format_short
app.jinja_env.filters['fmonth'] = format_month_year

# ───────────────────────────── DB HELPERS ──────────────────────────────────
def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'farmer',
        full_name TEXT,
        phone TEXT,
        location TEXT,
        language TEXT DEFAULT 'en',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS crops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        crop_name TEXT,
        variety TEXT,
        growth_stage TEXT,
        planting_date TEXT,
        field_size REAL,
        location TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS disease_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        crop_id INTEGER,
        image_path TEXT,
        crop_type TEXT,
        disease_detected TEXT,
        confidence_score REAL,
        severity TEXT,
        status TEXT DEFAULT 'completed',
        detected_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS diseases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        crop_type TEXT,
        description TEXT,
        causes TEXT,
        symptoms TEXT,
        chemical_treatment TEXT,
        organic_treatment TEXT,
        prevention TEXT,
        severity_level TEXT
    );
    CREATE TABLE IF NOT EXISTS weather_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        temperature REAL,
        humidity REAL,
        rainfall REAL,
        wind_speed REAL,
        disease_risk TEXT,
        risk_details TEXT,
        recorded_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        message TEXT,
        notif_type TEXT DEFAULT 'system',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS expert_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER,
        expert_id INTEGER,
        subject TEXT,
        message TEXT,
        response TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT (datetime('now')),
        replied_at TEXT
    );
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        alert_type TEXT,
        title TEXT,
        message TEXT,
        severity TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    db.commit()

    # Seed admin
    existing = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        db.execute("INSERT INTO users (username,email,password,role,full_name,is_active) VALUES (?,?,?,?,?,?)",
                   ('admin','admin@cropguard.ai',generate_password_hash('admin123'),'admin','System Administrator',1))
        db.execute("INSERT INTO users (username,email,password,role,full_name,is_active) VALUES (?,?,?,?,?,?)",
                   ('expert1','expert@cropguard.ai',generate_password_hash('expert123'),'expert','Dr. Rajesh Kumar (Agriculture Expert)',1))
        db.commit()

    # Seed diseases
    count = db.execute("SELECT COUNT(*) FROM diseases").fetchone()[0]
    if count == 0:
        diseases = [
            ('Rice Blast','Rice',
             'Rice blast is the most important disease of rice worldwide, caused by the fungus Magnaporthe oryzae. It can infect all above-ground parts of the rice plant.',
             'Caused by the fungus Magnaporthe oryzae. Favored by high humidity (>90%), temperatures between 25-28°C, excessive nitrogen fertilization, and dense plant populations.',
             'Diamond-shaped lesions with grey centers and brown borders on leaves. Neck rot causing white/grey panicles. Node blast causing dark brown to black lesions on nodes.',
             'Apply Tricyclazole (0.6g/L), Carbendazim (1g/L), or Propiconazole (1ml/L) at boot stage. Repeat after 10-15 days if infection persists.',
             'Apply neem leaf extract (5%), Trichoderma viride @4g/kg seed treatment, spray Pseudomonas fluorescens 0.5% at boot stage.',
             'Use resistant varieties. Avoid excessive nitrogen. Maintain proper plant spacing. Remove infected plant debris. Apply silicon fertilizer.',
             'high'),
            ('Bacterial Leaf Blight','Rice',
             'A serious bacterial disease caused by Xanthomonas oryzae pv. oryzae, causing wilting of seedlings and leaf blight in mature plants.',
             'Caused by Xanthomonas oryzae bacteria. Enters through wounds, water pores (hydathodes). Favored by high temperature (25-34°C), high humidity and rain.',
             'Water-soaked to yellowish stripes on leaf blades. Leaves turning yellow to straw-colored from the tips. Bacterial ooze visible in early morning.',
             'Apply Copper Oxychloride 50WP (3g/L) or Streptocycline (0.5g/10L) + Copper Oxychloride. Bleaching powder at 10kg/ha in irrigation water.',
             'Remove infected tillers. Avoid flood irrigation. Apply garlic extract spray. Maintain proper drainage.',
             'Use disease-free certified seeds. Treat seeds with hot water (52°C for 30 min). Use resistant varieties. Avoid excess nitrogen.',
             'high'),
            ('Early Blight','Tomato',
             'Early blight is a common fungal disease of tomatoes caused by Alternaria solani. It can significantly reduce yield if not managed properly.',
             'Caused by Alternaria solani fungus. Favored by warm temperatures (24-29°C), high humidity, and wet weather. Spreads through infected plant debris and seed.',
             'Brown spots with concentric rings forming a target-board pattern on older leaves. Yellow halo around lesions. Lesions on stems and fruit near stem end.',
             'Apply Mancozeb 75WP (2g/L), Chlorothalonil (2g/L), or Copper Oxychloride every 7-10 days. Iprodione or azoxystrobin for severe cases.',
             'Spray compost tea, neem oil (3ml/L), or baking soda solution (5g/L). Remove infected lower leaves. Mulch to prevent soil splash.',
             'Use disease-free transplants. Practice crop rotation (3 years). Stake plants for air circulation. Avoid wetting foliage.',
             'medium'),
            ('Late Blight','Tomato',
             'Late blight, caused by Phytophthora infestans, is a devastating disease that can destroy an entire crop within days under favorable conditions.',
             'Caused by oomycete Phytophthora infestans. Thrives in cool, wet weather (10-25°C). Spreads rapidly through airborne spores. Highly contagious.',
             'Large dark green, water-soaked areas on leaves. White fuzzy growth on undersides in humid conditions. Dark brown lesions on stems. Brown, firm rot on fruits.',
             'Apply Metalaxyl+Mancozeb (2.5g/L), Cymoxanil+Mancozeb (2g/L) preventively. Ridomil Gold for severe infection. Spray every 5-7 days.',
             'Bordeaux mixture (1%) spray preventively. Copper-based fungicides. Remove and destroy infected plants immediately. Improve drainage.',
             'Plant resistant varieties. Avoid overhead irrigation. Ensure good air circulation. Monitor weather forecasts.',
             'high'),
            ('Cotton Leaf Curl Virus','Cotton',
             'Cotton Leaf Curl Disease (CLCuD) is a serious viral disease caused by Begomoviruses transmitted by whitefly Bemisia tabaci.',
             'Caused by Cotton leaf curl virus (CLCuV) transmitted by whitefly (Bemisia tabaci). Disease spreads from infected plants to healthy ones through whitefly feeding.',
             'Upward or downward curling of leaves. Thickening and darkening of leaf veins. Enations (leaf-like outgrowths) on underside of leaves. Stunted plant growth.',
             'Control whitefly with Imidacloprid (0.3ml/L), Acetamiprid (0.2g/L), or Thiamethoxam. No direct cure for virus; manage the vector.',
             'Spray neem oil (5ml/L) to control whitefly. Use yellow sticky traps. Reflective mulches deter whitefly.',
             'Use virus-resistant/tolerant varieties. Remove infected plants early. Avoid ratoon cotton. Control whitefly population.',
             'high'),
            ('Powdery Mildew','Multiple',
             'Powdery mildew is a fungal disease affecting many crops, characterized by white powdery coating on plant surfaces.',
             'Caused by various fungi in the order Erysiphales. Favored by warm days, cool nights, high humidity, and shaded conditions. Spreads through airborne spores.',
             'White or grey powdery patches on leaves, stems, and flowers. Yellowing and distortion of affected leaves. Premature leaf drop in severe cases.',
             'Apply Sulfur dust or wettable sulfur (3g/L), Trifloxystrobin, Myclobutanil, or Tebuconazole. Spray every 10-14 days.',
             'Baking soda spray (5g+2ml oil/L), potassium bicarbonate (5g/L), diluted milk spray (1:9 ratio), neem oil.',
             'Plant resistant varieties. Avoid excessive nitrogen. Maintain plant spacing for air circulation. Water in morning.',
             'medium'),
        ]
        db.executemany("""INSERT INTO diseases
            (name,crop_type,description,causes,symptoms,chemical_treatment,organic_treatment,prevention,severity_level)
            VALUES (?,?,?,?,?,?,?,?,?)""", diseases)
        db.commit()
    db.close()

# ─────────────────────────────── HELPERS ───────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def simulate_ai_detection(crop_type):
    diseases = {
        'rice': [('Rice Blast',88.5,'high'),('Brown Spot',76.2,'medium'),
                 ('Bacterial Blight',91.3,'high'),('Sheath Blight',82.7,'medium'),('Healthy',95.1,'none')],
        'tomato': [('Early Blight',87.4,'medium'),('Late Blight',93.2,'high'),
                   ('Leaf Curl Virus',79.8,'high'),('Septoria Leaf Spot',84.1,'medium'),('Healthy',96.3,'none')],
        'cotton': [('Cotton Leaf Curl Virus',89.6,'high'),('Alternaria Blight',75.3,'medium'),
                   ('Cercospora Leaf Spot',81.2,'low'),('Healthy',94.7,'none')],
    }
    opts = diseases.get(crop_type.lower(), [('Powdery Mildew',85.0,'medium'),('Rust Disease',78.5,'low'),('Healthy',93.5,'none')])
    d, conf, sev = random.choice(opts)
    return {'disease': d, 'confidence': round(conf + random.uniform(-3,3), 2), 'severity': sev}

def get_weather_risk(temperature, humidity):
    if humidity > 80 and temperature > 25:
        return 'high', 'High humidity and warm temperature create ideal conditions for fungal diseases.'
    elif humidity > 65 or temperature > 30:
        return 'medium', 'Moderate risk — monitor crops closely for early signs of disease.'
    return 'low', 'Current weather conditions are not favorable for disease development.'

# ─────────────────────────────── AUTH ──────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute("""INSERT INTO users (username,email,password,full_name,phone,location,role)
                          VALUES (?,?,?,?,?,?,?)""",
                       (request.form['username'], request.form['email'],
                        generate_password_hash(request.form['password']),
                        request.form.get('full_name',''), request.form.get('phone',''),
                        request.form.get('location',''), request.form.get('role','farmer')))
            db.commit()
            user = db.execute("SELECT id FROM users WHERE username=?", (request.form['username'],)).fetchone()
            db.execute("INSERT INTO notifications (user_id,title,message,notif_type) VALUES (?,?,?,?)",
                       (user['id'], 'Welcome to CropGuard AI!',
                        f"Hello {request.form.get('full_name', request.form['username'])}! Your account is active.", 'system'))
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
        finally:
            db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (request.form['username'],)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], request.form['password']) and user['is_active']:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name'] or user['username']
            flash(f"Welcome back, {session['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials or account disabled.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─────────────────────────────── DASHBOARD ─────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    db = get_db()
    total_crops = db.execute("SELECT COUNT(*) FROM crops WHERE user_id=?", (uid,)).fetchone()[0]
    total_detections = db.execute("SELECT COUNT(*) FROM disease_detections WHERE user_id=?", (uid,)).fetchone()[0]
    high_risk = db.execute("SELECT COUNT(*) FROM disease_detections WHERE user_id=? AND severity='high'", (uid,)).fetchone()[0]
    open_queries = db.execute("SELECT COUNT(*) FROM expert_queries WHERE farmer_id=? AND status='open'", (uid,)).fetchone()[0]
    detections = db.execute("SELECT * FROM disease_detections WHERE user_id=? ORDER BY detected_at DESC LIMIT 5", (uid,)).fetchall()
    weather = db.execute("SELECT * FROM weather_data ORDER BY recorded_at DESC LIMIT 1").fetchone()
    db.close()
    return render_template('dashboard.html', total_crops=total_crops, total_detections=total_detections,
                           high_risk=high_risk, open_queries=open_queries, detections=detections, weather=weather)

# ─────────────────────────────── PROFILE ───────────────────────────────────
@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    if request.method == 'POST':
        if request.form.get('new_password'):
            if not check_password_hash(user['password'], request.form.get('current_password','')):
                flash('Current password is incorrect.', 'error')
                db.close()
                return render_template('profile.html', user=user)
            db.execute("UPDATE users SET full_name=?,phone=?,location=?,language=?,password=? WHERE id=?",
                       (request.form['full_name'], request.form['phone'], request.form['location'],
                        request.form['language'], generate_password_hash(request.form['new_password']),
                        session['user_id']))
        else:
            db.execute("UPDATE users SET full_name=?,phone=?,location=?,language=? WHERE id=?",
                       (request.form['full_name'], request.form['phone'], request.form['location'],
                        request.form['language'], session['user_id']))
        db.commit()
        session['full_name'] = request.form['full_name']
        flash('Profile updated!', 'success')
        user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    db.close()
    return render_template('profile.html', user=user)

# ─────────────────────────────── CROPS ─────────────────────────────────────
@app.route('/crops')
@login_required
def crops():
    db = get_db()
    user_crops = db.execute("SELECT * FROM crops WHERE user_id=? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    db.close()
    return render_template('crops.html', crops=user_crops)

@app.route('/crops/add', methods=['GET','POST'])
@login_required
def add_crop():
    if request.method == 'POST':
        db = get_db()
        db.execute("""INSERT INTO crops (user_id,crop_name,variety,growth_stage,planting_date,field_size,location,notes)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (session['user_id'], request.form['crop_name'], request.form.get('variety',''),
                    request.form.get('growth_stage',''), request.form.get('planting_date',''),
                    float(request.form.get('field_size',0) or 0), request.form.get('location',''),
                    request.form.get('notes','')))
        db.commit(); db.close()
        flash('Crop added successfully!', 'success')
        return redirect(url_for('crops'))
    return render_template('add_crop.html')

@app.route('/crops/<int:crop_id>/delete', methods=['POST'])
@login_required
def delete_crop(crop_id):
    db = get_db()
    db.execute("DELETE FROM crops WHERE id=? AND user_id=?", (crop_id, session['user_id']))
    db.commit(); db.close()
    flash('Crop removed.', 'success')
    return redirect(url_for('crops'))

# ─────────────────────────────── DETECTION ─────────────────────────────────
@app.route('/detect', methods=['GET','POST'])
@login_required
def detect():
    db = get_db()
    user_crops = db.execute("SELECT * FROM crops WHERE user_id=?", (session['user_id'],)).fetchall()
    if request.method == 'POST':
        if 'image' not in request.files or request.files['image'].filename == '':
            flash('Please select an image.', 'error')
            db.close()
            return render_template('detect.html', crops=user_crops)
        file = request.files['image']
        crop_type = request.form.get('crop_type','default')
        crop_id = request.form.get('crop_id') or None
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            result = simulate_ai_detection(crop_type)
            db.execute("""INSERT INTO disease_detections
                (user_id,crop_id,image_path,crop_type,disease_detected,confidence_score,severity,status)
                VALUES (?,?,?,?,?,?,?,?)""",
                (session['user_id'], crop_id, f"uploads/{filename}", crop_type,
                 result['disease'], result['confidence'], result['severity'], 'completed'))
            if result['severity'] in ('high','medium'):
                db.execute("""INSERT INTO alerts (user_id,alert_type,title,message,severity)
                    VALUES (?,?,?,?,?)""",
                    (session['user_id'], 'disease', f"Disease Detected: {result['disease']}",
                     f"A {result['severity']} severity disease was detected in your {crop_type} crop with {result['confidence']:.1f}% confidence.",
                     result['severity']))
            db.commit()
            disease_info = db.execute("SELECT * FROM diseases WHERE name LIKE ? AND crop_type LIKE ?",
                                       (f"%{result['disease'].split()[0]}%", f"%{crop_type}%")).fetchone()
            if not disease_info:
                disease_info = db.execute("SELECT * FROM diseases WHERE name LIKE ?",
                                           (f"%{result['disease'].split()[0]}%",)).fetchone()
            detected_at = datetime.now().strftime('%d %b %Y, %H:%M')
            db.close()
            return render_template('detection_result.html', result=result,
                                   disease_info=disease_info, crop_type=crop_type,
                                   image_path=f"uploads/{filename}",
                                   detected_at=detected_at)
        flash('Invalid file type.', 'error')
    db.close()
    return render_template('detect.html', crops=user_crops)

@app.route('/detections')
@login_required
def detections():
    db = get_db()
    all_d = db.execute("SELECT * FROM disease_detections WHERE user_id=? ORDER BY detected_at DESC",
                        (session['user_id'],)).fetchall()
    db.close()
    return render_template('detections.html', detections=all_d)

# ─────────────────────────────── DISEASE LIBRARY ───────────────────────────
@app.route('/diseases')
@login_required
def diseases():
    search = request.args.get('search','')
    crop_filter = request.args.get('crop','')
    db = get_db()
    if search and crop_filter:
        rows = db.execute("SELECT * FROM diseases WHERE name LIKE ? AND crop_type LIKE ?",
                           (f'%{search}%', f'%{crop_filter}%')).fetchall()
    elif search:
        rows = db.execute("SELECT * FROM diseases WHERE name LIKE ?", (f'%{search}%',)).fetchall()
    elif crop_filter:
        rows = db.execute("SELECT * FROM diseases WHERE crop_type LIKE ?", (f'%{crop_filter}%',)).fetchall()
    else:
        rows = db.execute("SELECT * FROM diseases").fetchall()
    db.close()
    return render_template('diseases.html', diseases=rows, search=search, crop_filter=crop_filter)

@app.route('/diseases/<int:disease_id>')
@login_required
def disease_detail(disease_id):
    db = get_db()
    disease = db.execute("SELECT * FROM diseases WHERE id=?", (disease_id,)).fetchone()
    db.close()
    if not disease:
        flash('Disease not found.', 'error')
        return redirect(url_for('diseases'))
    return render_template('disease_detail.html', disease=disease)

# ─────────────────────────────── WEATHER ───────────────────────────────────
@app.route('/weather', methods=['GET','POST'])
@login_required
def weather():
    db = get_db()
    if request.method == 'POST':
        temp = float(request.form.get('temperature', 25) or 25)
        hum = float(request.form.get('humidity', 60) or 60)
        rain = float(request.form.get('rainfall', 0) or 0)
        wind = float(request.form.get('wind_speed', 10) or 10)
        loc = request.form.get('location','Farm')
        risk, details = get_weather_risk(temp, hum)
        db.execute("""INSERT INTO weather_data (location,temperature,humidity,rainfall,wind_speed,disease_risk,risk_details)
                      VALUES (?,?,?,?,?,?,?)""", (loc,temp,hum,rain,wind,risk,details))
        if risk == 'high':
            db.execute("""INSERT INTO alerts (user_id,alert_type,title,message,severity)
                          VALUES (?,?,?,?,?)""",
                       (session['user_id'],'weather','High Disease Risk Weather Alert',details,'high'))
        db.commit()
        flash('Weather data recorded!', 'success')
    history = db.execute("SELECT * FROM weather_data ORDER BY recorded_at DESC LIMIT 10").fetchall()
    db.close()
    return render_template('weather.html', history=history)

# ─────────────────────────────── ANALYTICS ─────────────────────────────────
@app.route('/analytics')
@login_required
def analytics():
    uid = session['user_id']
    db = get_db()
    all_d = db.execute("SELECT * FROM disease_detections WHERE user_id=?", (uid,)).fetchall()
    total_crops = db.execute("SELECT COUNT(*) FROM crops WHERE user_id=?", (uid,)).fetchone()[0]
    db.close()
    disease_counts, severity_counts, monthly = {}, {'high':0,'medium':0,'low':0,'none':0}, {}
    for d in all_d:
        disease_counts[d['disease_detected']] = disease_counts.get(d['disease_detected'],0)+1
        sev = d['severity'] or 'none'
        severity_counts[sev] = severity_counts.get(sev,0)+1
        try:
            month_key = datetime.strptime(d['detected_at'][:10],'%Y-%m-%d').strftime('%b %Y')
        except:
            month_key = 'Unknown'
        monthly[month_key] = monthly.get(month_key,0)+1
    return render_template('analytics.html', all_detections=all_d, total_crops=total_crops,
                           disease_counts=json.dumps(disease_counts),
                           severity_counts=json.dumps(severity_counts),
                           monthly=json.dumps(monthly))

# ─────────────────────────────── ALERTS ────────────────────────────────────
@app.route('/alerts')
@login_required
def alerts():
    db = get_db()
    all_alerts = db.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC",
                             (session['user_id'],)).fetchall()
    db.execute("UPDATE alerts SET is_read=1 WHERE user_id=?", (session['user_id'],))
    db.commit(); db.close()
    return render_template('alerts.html', alerts=all_alerts)

@app.route('/notifications')
@login_required
def notifications():
    db = get_db()
    all_n = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC",
                        (session['user_id'],)).fetchall()
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (session['user_id'],))
    db.commit(); db.close()
    return render_template('notifications.html', notifications=all_n)

# ─────────────────────────────── CONSULT ───────────────────────────────────
@app.route('/consult', methods=['GET','POST'])
@login_required
def consult():
    db = get_db()
    if request.method == 'POST':
        db.execute("INSERT INTO expert_queries (farmer_id,subject,message) VALUES (?,?,?)",
                   (session['user_id'], request.form['subject'], request.form['message']))
        db.commit()
        flash('Query submitted to experts!', 'success')
        return redirect(url_for('consult'))
    queries = db.execute("SELECT * FROM expert_queries WHERE farmer_id=? ORDER BY created_at DESC",
                          (session['user_id'],)).fetchall()
    experts = db.execute("SELECT * FROM users WHERE role='expert' AND is_active=1").fetchall()
    db.close()
    return render_template('consult.html', queries=queries, experts=experts)

@app.route('/consult/reply/<int:query_id>', methods=['POST'])
@login_required
def reply_query(query_id):
    if session.get('role') not in ('expert','admin'):
        return jsonify({'error':'Unauthorized'}), 403
    db = get_db()
    query = db.execute("SELECT * FROM expert_queries WHERE id=?", (query_id,)).fetchone()
    db.execute("""UPDATE expert_queries SET response=?,expert_id=?,status='answered',replied_at=datetime('now')
                  WHERE id=?""", (request.form['response'], session['user_id'], query_id))
    db.execute("INSERT INTO notifications (user_id,title,message,notif_type) VALUES (?,?,?,?)",
               (query['farmer_id'], 'Expert Response Received',
                f"Your query \"{query['subject']}\" has been answered.", 'expert'))
    db.commit(); db.close()
    flash('Response sent!', 'success')
    return redirect(url_for('expert_dashboard'))

# ─────────────────────────────── EXPERT ────────────────────────────────────
@app.route('/expert')
@login_required
def expert_dashboard():
    if session.get('role') not in ('expert','admin'):
        return redirect(url_for('dashboard'))
    db = get_db()
    open_queries = db.execute("SELECT * FROM expert_queries WHERE status='open' ORDER BY created_at DESC").fetchall()
    answered = db.execute("SELECT COUNT(*) FROM expert_queries WHERE expert_id=?", (session['user_id'],)).fetchone()[0]
    db.close()
    return render_template('expert_dashboard.html', queries=open_queries, answered=answered)

# ─────────────────────────────── PREDICT ───────────────────────────────────
@app.route('/predict')
@login_required
def predict():
    uid = session['user_id']
    db = get_db()
    recent_d = db.execute("SELECT * FROM disease_detections WHERE user_id=? ORDER BY detected_at DESC LIMIT 10", (uid,)).fetchall()
    recent_w = db.execute("SELECT * FROM weather_data ORDER BY recorded_at DESC LIMIT 5").fetchall()
    db.close()
    predictions = []
    if recent_w:
        w = recent_w[0]
        if w['humidity'] > 75:
            predictions.append({'disease':'Fungal Blight','probability':78,'timeframe':'Next 7 days','risk':'high'})
        if w['temperature'] > 28:
            predictions.append({'disease':'Bacterial Leaf Spot','probability':55,'timeframe':'Next 14 days','risk':'medium'})
    predictions.append({'disease':'Rust Disease','probability':30,'timeframe':'Next 30 days','risk':'low'})
    return render_template('predict.html', predictions=predictions,
                           recent_detections=recent_d, weather=recent_w)

# ─────────────────────────────── ADMIN ─────────────────────────────────────
@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    stats = {
        'total_users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_crops': db.execute("SELECT COUNT(*) FROM crops").fetchone()[0],
        'total_detections': db.execute("SELECT COUNT(*) FROM disease_detections").fetchone()[0],
        'total_diseases': db.execute("SELECT COUNT(*) FROM diseases").fetchone()[0],
    }
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    recent_d = db.execute("SELECT * FROM disease_detections ORDER BY detected_at DESC LIMIT 10").fetchall()
    db.close()
    return render_template('admin.html', users=users, recent_detections=recent_d, **stats)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    new_status = 0 if user['is_active'] else 1
    db.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
    db.commit(); db.close()
    return jsonify({'status': 'active' if new_status else 'inactive'})

@app.route('/admin/disease/add', methods=['GET','POST'])
@admin_required
def add_disease():
    if request.method == 'POST':
        db = get_db()
        db.execute("""INSERT INTO diseases
            (name,crop_type,description,causes,symptoms,chemical_treatment,organic_treatment,prevention,severity_level)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (request.form['name'], request.form['crop_type'], request.form['description'],
             request.form['causes'], request.form['symptoms'], request.form['chemical_treatment'],
             request.form['organic_treatment'], request.form['prevention'], request.form['severity_level']))
        db.commit(); db.close()
        flash('Disease added to database!', 'success')
        return redirect(url_for('admin'))
    return render_template('add_disease.html')

@app.route('/admin/report')
@admin_required
def report():
    db = get_db()
    rows = db.execute("SELECT * FROM disease_detections").fetchall()
    db.close()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID','User ID','Crop Type','Disease','Confidence','Severity','Date'])
    for r in rows:
        cw.writerow([r['id'],r['user_id'],r['crop_type'],r['disease_detected'],r['confidence_score'],r['severity'],r['detected_at']])
    return Response(si.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment; filename=detections_report.csv'})

# ─────────────────────────────── API ───────────────────────────────────────
@app.route('/api/notifications/count')
@login_required
def notif_count():
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (session['user_id'],)).fetchone()[0]
    a = db.execute("SELECT COUNT(*) FROM alerts WHERE user_id=? AND is_read=0", (session['user_id'],)).fetchone()[0]
    db.close()
    return jsonify({'notifications':n,'alerts':a,'total':n+a})

@app.route('/api/weather/simulate')
@login_required
def simulate_weather():
    t = round(random.uniform(18,38),1)
    h = round(random.uniform(40,95),1)
    risk, details = get_weather_risk(t,h)
    return jsonify({'temperature':t,'humidity':h,'rainfall':round(random.uniform(0,15),1),
                    'wind_speed':round(random.uniform(5,30),1),'disease_risk':risk,'risk_details':details})

# ───────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)
