from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import json
import os
import math
import uuid
import sqlite3
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from image_matcher import image_similarity, find_visually_similar, IMAGE_MATCH_AVAILABLE

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Data storage file
DATA_FILE = "data.json"
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Admin access required.", "danger")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Ensure data file exists
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as file:
        json.dump({"lost_items": [], "found_items": []}, file)

# Load existing data
def load_data():
    with open(DATA_FILE, "r") as file:
        return json.load(file)

data = load_data()
def save_data():
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)

if "notifications" not in data:
    data["notifications"] = []
    save_data()

def detect_matches(new_item, report_type):
    # Determine the opposite list to compare against
    target_list_name = "found_items" if report_type == "lost" else "lost_items"
    target_list = data.get(target_list_name, [])
    
    new_name = new_item.get("name", "").lower()
    new_cat = new_item.get("category", "")
    
    for existing in target_list:
        ext_cat = existing.get("category", "")
        # Require identical category to avoid noisy matching
        if new_cat != ext_cat:
            continue
            
        ext_name = existing.get("name", "").lower()
        
        # Checking substring intersection (e.g. 'wallet' in 'black wallet')
        # Splitting terms checks if any significant noun overlaps
        new_words = set(new_name.split())
        ext_words = set(ext_name.split())
        
        # Intersect checks if they share words directly, or string inclusion
        overlap = new_words.intersection(ext_words)
        
        if overlap or new_name in ext_name or ext_name in new_name:
            # We found a match! Create notification
            matched_noun = list(overlap)[0] if overlap else new_name
            msg = f"🔍 Match found for your {report_type} {matched_noun.title()}! Check the {target_list_name.replace('_', ' ').title()}."
            
            # Link back dynamically to opposite view
            link_target = "view_found" if report_type == "lost" else "view_lost"
            
            new_notif = {
                "id": str(uuid.uuid4()),
                "message": msg,
                "is_read": False,
                "timestamp": datetime.now().isoformat(),
                "link": f"/{'found' if report_type == 'lost' else 'lost'}?search={matched_noun}&category={new_cat}&sort=latest"
            }
            data["notifications"].append(new_notif)
            save_data()
            # Only trigger 1 notification map per new item to prevent spam
            break

@app.route("/api/notifications")
def api_notifications():
    unread = [n for n in data.get("notifications", []) if not n.get("is_read")]
    # sort by latest
    unread.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify(unread)

@app.route("/api/notifications/<notif_id>/read", methods=["POST"])
def api_notifications_read(notif_id):
    for n in data.get("notifications", []):
        if n.get("id") == notif_id:
            n["is_read"] = True
            save_data()
            return jsonify({"status": "success"})
    return jsonify({"status": "not_found"}), 404

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                         (name, email, hashed_password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email address already registered.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("my_items"))
        else:
            flash("Invalid email or password.", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

@app.route("/")
def home():
    return render_template("home.html")

def apply_filters(items, args):
    search_query = args.get("search", "").lower()
    category = args.get("category", "")
    location = args.get("location", "").lower()
    date_filter = args.get("date", "")
    sort_by = args.get("sort", "latest")
    
    filtered = []
    for item in items:
        # Search match
        if search_query and search_query not in item["name"].lower() and search_query not in item["description"].lower():
            continue
            
        # Category match
        if category and item.get("category") != category:
            continue
            
        # Location match
        if location and location not in item.get("location", "").lower():
            continue
            
        # Date match
        if date_filter and date_filter != "all":
            reported = item.get("date_reported")
            if not reported:
                continue 
            try:
                dt = datetime.fromisoformat(reported)
                now = datetime.now()
                delta = now - dt
                if date_filter == "today" and delta.days > 0:
                    continue
                if date_filter == "week" and delta.days > 7:
                    continue
            except:
                pass
                
        filtered.append(item)
        
    # Sorting
    if sort_by == "alphabetical":
        filtered.sort(key=lambda x: x["name"].lower())
    elif sort_by == "oldest":
        filtered.sort(key=lambda x: x.get("date_reported", "zzz"))
    else:
        filtered.sort(key=lambda x: x.get("date_reported", ""), reverse=True)
        
    return filtered

@app.route("/lost", methods=["GET", "POST"])
def view_lost():
    item_type = request.args.get("type", "lost")
    if item_type == "found":
        base_items = data["found_items"]
    elif item_type == "all":
        base_items = data["lost_items"] + data["found_items"]
    else:
        base_items = data["lost_items"]
    
    items = apply_filters(base_items, request.args)
    return render_template("view_lost.html", lost_items=items)

@app.route("/found", methods=["GET", "POST"])
def view_found():
    item_type = request.args.get("type", "found")
    if item_type == "lost":
        base_items = data["lost_items"]
    elif item_type == "all":
        base_items = data["lost_items"] + data["found_items"]
    else:
        base_items = data["found_items"]
        
    items = apply_filters(base_items, request.args)
    return render_template("view_found.html", found_items=items)

@app.route("/report-lost", methods=["GET", "POST"])
@login_required
def report_lost():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        description = request.form["description"]
        contact = request.form["contact"]
        location = request.form["location"]
        image = request.files.get("image")

        # Handle image upload
        image_filename = None  # No default image
        if image and image.filename:
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(image.filename)
            image.save(os.path.join(upload_folder, filename))
            image_filename = "/static/uploads/" + filename

        # Parse lat/lng
        lat_val = request.form.get("lat", "").strip()
        lng_val = request.form.get("lng", "").strip()
        
        # Save lost item
        data["lost_items"].append({
            "user_id":     session.get("user_id"),
            "name":        name.lower(),
            "category":    category,
            "description": description.lower(),
            "contact":     contact,
            "location":    location,
            "lat":         float(lat_val) if lat_val else None,
            "lng":         float(lng_val) if lng_val else None,
            "image":       image_filename,
            "date_reported": datetime.now().isoformat()
        })
        detect_matches(data["lost_items"][-1], "lost")
        save_data()
        flash("Lost item reported successfully!", "success")
        return redirect(url_for("view_lost"))

    return render_template("lost.html")

@app.route("/report-found", methods=["GET", "POST"])
@login_required
def report_found():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        description = request.form["description"]
        contact = request.form["contact"]
        location = request.form["location"]
        image = request.files.get("image")

        # Handle image upload
        image_filename = None  # No default image
        if image and image.filename:
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(image.filename)
            image.save(os.path.join(upload_folder, filename))
            image_filename = "/static/uploads/" + filename

        # Parse lat/lng
        lat_val = request.form.get("lat", "").strip()
        lng_val = request.form.get("lng", "").strip()
        
        # Save found item
        data["found_items"].append({
            "user_id":     session.get("user_id"),
            "name":        name.lower(),
            "category":    category,
            "description": description.lower(),
            "contact":     contact,
            "location":    location,
            "lat":         float(lat_val) if lat_val else None,
            "lng":         float(lng_val) if lng_val else None,
            "image":       image_filename,
            "date_reported": datetime.now().isoformat()
        })
        detect_matches(data["found_items"][-1], "found")
        save_data()
        flash("Found item reported successfully!", "success")
        return redirect(url_for("view_found"))

    return render_template("found.html")


@app.route("/map")
def map_view():
    import json as json_lib
    fresh = load_data()
    # Tag each item with its type + index for popup links
    lost_tagged  = [{**item, "_type": "lost",  "_idx": idx} for idx, item in enumerate(fresh.get("lost_items",  []))]
    found_tagged = [{**item, "_type": "found", "_idx": idx} for idx, item in enumerate(fresh.get("found_items", []))]
    all_items = lost_tagged + found_tagged
    # Filter to only items that have coordinates
    geo_items = [i for i in all_items if i.get("lat") and i.get("lng")]
    return render_template("map.html",
                           items_json=json_lib.dumps(geo_items),
                           total=len(all_items),
                           geo_count=len(geo_items))

# ── Geographic helpers ───────────────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2):
    """Return distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_coord(val):
    """Safely parse a coordinate string/number to float, or return None."""
    try:
        v = float(val)
        return v if v != 0.0 else None
    except (TypeError, ValueError):
        return None


@app.route("/api/items")
def api_items():
    """JSON endpoint — returns all items with coordinates tagged by type."""
    fresh = load_data()
    result = []
    for idx, item in enumerate(fresh.get("lost_items", [])):
        result.append({**item, "_type": "lost", "_idx": idx})
    for idx, item in enumerate(fresh.get("found_items", [])):
        result.append({**item, "_type": "found", "_idx": idx})
    return jsonify(result)


import difflib

# ── Matching Helpers ──────────────────────────────────────────────
def normalize_text(text):
    """Lowercase, strip, collapse whitespace."""
    return " ".join(str(text).lower().split())

def similarity_score(a, b):
    """Return 0–100 similarity score using SequenceMatcher."""
    a, b = normalize_text(a), normalize_text(b)
    if not a or not b:
        return 0
    return round(difflib.SequenceMatcher(None, a, b).ratio() * 100, 1)

def contains_bonus(a, b):
    """Extra points if one name is a substring of the other."""
    a, b = normalize_text(a), normalize_text(b)
    return 15 if (a in b or b in a) else 0

def geo_distance_bonus(lost, found):
    """Distance proximity bonus (0–15 pts). Returns (bonus, distance_km or None)."""
    lat1 = _parse_coord(lost.get("lat"))
    lng1 = _parse_coord(lost.get("lng"))
    lat2 = _parse_coord(found.get("lat"))
    lng2 = _parse_coord(found.get("lng"))
    if None in (lat1, lng1, lat2, lng2):
        return 0, None
    dist = haversine_km(lat1, lng1, lat2, lng2)
    if dist < 1:    return 15, dist
    if dist < 5:    return 10, dist
    if dist < 15:   return 5,  dist
    return 0, dist

def compute_overall_match_score(lost, found):
    """Weighted multi-signal score (0–100)."""
    if normalize_text(lost.get("category", "")) != normalize_text(found.get("category", "")):
        return 0

    name_score = similarity_score(lost.get("name", ""),        found.get("name", ""))
    desc_score = similarity_score(lost.get("description", ""), found.get("description", ""))
    loc_score  = similarity_score(lost.get("location", ""),    found.get("location", ""))
    bonus      = contains_bonus(lost.get("name", ""),    found.get("name", ""))
    geo_bonus, dist_km = geo_distance_bonus(lost, found)

    text_score = (name_score * 0.45) + (desc_score * 0.25) + (loc_score * 0.15) + bonus + geo_bonus

    # --- Image signal (optional) ---
    img_score = -1.0
    if IMAGE_MATCH_AVAILABLE and lost.get("image") and found.get("image"):
        img_score = image_similarity(lost["image"], found["image"])

    if img_score >= 0:
        combined = (text_score * 0.70) + (img_score * 0.30)
    else:
        combined = text_score

    return min(round(combined, 1), 100), img_score, dist_km

def get_all_matches(fresh_data, threshold=45):
    candidates = []
    seen = set()

    for lost in fresh_data.get("lost_items", []):
        for found in fresh_data.get("found_items", []):
            pair_key = (normalize_text(lost["name"]), normalize_text(found["name"]))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            result = compute_overall_match_score(lost, found)
            if isinstance(result, tuple) and len(result) == 3:
                score, img_score, dist_km = result
            elif isinstance(result, tuple) and len(result) == 2:
                score, img_score = result
                dist_km = None
            else:
                score, img_score, dist_km = result, -1.0, None

            if score >= threshold:
                candidates.append({
                    "lost_item":  lost,
                    "found_item": found,
                    "score":      score,
                    "img_score":  round(img_score, 1) if img_score >= 0 else None,
                    "dist_km":    round(dist_km, 2) if dist_km is not None else None,
                    "label":      _score_label(score),
                })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

@app.route("/match")
def match_results():
    fresh_data = load_data()
    candidates = get_all_matches(fresh_data)
    return render_template("match_results.html", matches=candidates)

@app.route("/my-items")
@login_required
def my_items():
    user_id = session.get("user_id")
    fresh_data = load_data()
    my_lost = [item for item in fresh_data.get("lost_items", []) if item.get("user_id") == user_id]
    my_found = [item for item in fresh_data.get("found_items", []) if item.get("user_id") == user_id]
    
    # Get all matches, but filter to only show matches relevant to this user
    all_candidates = get_all_matches(fresh_data)
    my_matches = []
    for cand in all_candidates:
        if cand["lost_item"].get("user_id") == user_id or cand["found_item"].get("user_id") == user_id:
            my_matches.append(cand)
            
    return render_template("dashboard.html", my_lost=my_lost, my_found=my_found, my_matches=my_matches)

def _score_label(score):
    """Human-readable confidence label for a given score."""
    if score >= 85:
        return ("Excellent Match", "label-excellent")
    elif score >= 70:
        return ("Strong Match",    "label-strong")
    elif score >= 55:
        return ("Possible Match",  "label-possible")
    else:
        return ("Weak Match",      "label-weak")


@app.route("/search-image", methods=["GET", "POST"])
def search_image():
    results = []
    query_img_url = None

    if request.method == "POST":
        file = request.files.get("query_image")
        if file and file.filename:
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = "query_" + secure_filename(file.filename)
            query_path = os.path.join(upload_folder, filename)
            file.save(query_path)
            query_img_url = "/static/uploads/" + filename

            fresh_data = load_data()
            all_items = fresh_data.get("lost_items", []) + fresh_data.get("found_items", [])
            raw = find_visually_similar(query_path, all_items, threshold=40.0)
            results = [{"item": item, "score": score, "label": _score_label(score)}
                       for item, score in raw]

    return render_template("search_image.html",
                           results=results,
                           query_img_url=query_img_url,
                           image_match_available=IMAGE_MATCH_AVAILABLE)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            session["is_admin"] = True
            flash("Logged in as Admin.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    fresh_data = load_data()
    total_lost = len(fresh_data.get("lost_items", []))
    total_found = len(fresh_data.get("found_items", []))
    all_matches = get_all_matches(fresh_data)
    total_matches = len(all_matches)
    
    conn = get_db_connection()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    
    recent_lost = sorted(fresh_data.get("lost_items", []), key=lambda x: x.get("date_reported", ""), reverse=True)[:5]
    recent_found = sorted(fresh_data.get("found_items", []), key=lambda x: x.get("date_reported", ""), reverse=True)[:5]
    recent_matches = all_matches[:5]
    
    from collections import defaultdict
    date_counts = defaultdict(int)
    for item in fresh_data.get("lost_items", []) + fresh_data.get("found_items", []):
        d_str = item.get("date_reported", "")
        if d_str:
            date_only = d_str[:10]
            date_counts[date_only] += 1
            
    sorted_dates = sorted(date_counts.keys())
    chart_dates = sorted_dates[-14:] 
    chart_counts = [date_counts[d] for d in chart_dates]

    return render_template("admin_dashboard.html",
                           total_lost=total_lost, total_found=total_found, 
                           total_matches=total_matches, total_users=total_users,
                           recent_lost=recent_lost, recent_found=recent_found, recent_matches=recent_matches,
                           chart_dates=chart_dates, chart_counts=chart_counts)

@app.route("/admin/clear")
@admin_required
def admin_clear():
    fresh_data = {"lost_items": [], "found_items": [], "notifications": []}
    global data
    data = fresh_data 
    save_data()
    flash("All lost/found/notification data cleared.", "success")
    return redirect(url_for("admin_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)

