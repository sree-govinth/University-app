from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
from functools import wraps
from datetime import timedelta
import pytz

# Load environment variables
load_dotenv()

app = Flask(__name__)  # Fix: Use __name, not _name
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')
app.permanent_session_lifetime = timedelta(minutes=30)

# MongoDB Setup
try:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client['campusApp']
    # Required collections
    collections = ['users', 'students', 'activities', 'events', 'notifications', 'resources', 'announcements']
    for collection_name in collections:
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)

    # Initialize collection references
    users = db['users']
    students = db['students']
    activities = db['activities']
    events = db['events']
    resources_collection = db['resources']
    announcements_collection = db['announcements']

    # Optional: Insert admin user if not exists
    admin_email = "sree123@gmail.com"
    if not users.find_one({"email": admin_email}):
        admin_user = {
            "name": "Sree",
            "email": admin_email,
            "password": generate_password_hash("1234"),
            "role": "admin"
        }
        users.insert_one(admin_user)
        print("✅ Admin user inserted.")

except Exception as e:
    print(f"MongoDB Connection Error: {e}")
    @app.route("/error")
    def error():
        return render_template('error.html', message="Database connection failed.")
    exit(1)

# Auth Decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            flash("You need to log in first.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Activity Logger
def log_activity(action, user_name, role):
    activities.insert_one({
        'user_name': user_name,
        'role': role,
        'action': action,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/')
def home():
    return redirect(url_for('login'))

# Admin-only Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']

        if users.find_one({'email': email}):
            flash('User already exists.')
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        users.insert_one({'name': name, 'email': email, 'password': hashed_password, 'role': role})

        if role == 'student':
            students.insert_one({
                'name': name,
                'email': email,
                'grades': {},
                'attendance': {}
            })

        log_activity('Registered a new user', name, role)
        flash('User registered successfully.')
        return redirect(url_for('admin_dashboard'))

    return render_template('signup.html')

# Login for all roles
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            session['user'] = {
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }

            print("Login successful:", session['user'])  # ✅ Add this

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user['role'] == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            elif user['role'] == 'staff':
                return redirect(url_for('staff_dashboard'))
        else:
            flash("Invalid email or password", "danger")
            print("Login failed for:", email)  # ✅ Add this too

    return render_template("login.html")  # ⚠️ Only if GET or failed login

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

# Admin Dashboard
@app.route('/admin')
@login_required
def admin_dashboard():
    if session['user']['role'] != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    recent_activities = activities.find().sort('timestamp', -1).limit(5)
    return render_template('admin_dashboard.html', activities=recent_activities)


from datetime import datetime

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    user = session.get('user', {})

    # Fetch the student's data from the database
    student = db['students'].find_one({'email': user.get('email')})

    # Ensure event dates are correct
    for event in events.find():
        if isinstance(event.get("date"), str):
            try:
                parsed_date = datetime.strptime(event["date"], "%Y-%m-%d")
                events.update_one(
                    {"_id": event["_id"]},
                    {"$set": {"date": parsed_date}}
                )
            except Exception as e:
                print(f"❌ Skipped: {event['title']} due to error: {e}")

    if not student:
        flash("Student record not found.")
        return redirect(url_for('login'))

    # Student specific data
    grades = student.get('grades', {})
    attendance_dict = student.get('attendance', {})
    subjects = list(grades.keys())
    grades_values = list(grades.values())
    attendance = [attendance_dict.get(sub, 0) for sub in subjects]

    # Fetch events created by staff for the student dashboard
    upcoming_events = list(events.find({"date": {"$gte": datetime.utcnow()}}).sort('date', 1))

    upcoming_events_data = [{
        "title": event["title"],
        "date": event["date"],
        "event_type": event["event_type"]
    } for event in upcoming_events]

    # Fetch announcements and ensure the date is in datetime format
    announcements_data = list(db['announcements'].find())  # Fetch announcements
    for announcement in announcements_data:
        for field in ['date', 'created_at', 'timestamp']:
            if isinstance(announcement.get(field), str):
                try:
                    # Convert string to datetime
                    announcement[field] = datetime.strptime(announcement[field], '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    print(f"❌ Skipped: {announcement.get('title')} due to error: {e}")

    # Sample semester comparison data
    semester_comparison = {
        "Semester 1": 7.5,
        "Semester 2": 6.5,
        "Semester 3": 8.1,
        "Semester 4": 9.7,
        "Semester 5": 8.5,
        "Semester 6": 9.8,
    }

    return render_template('student_dashboard.html',
                       student=student,  # Pass the student object to the template
                       grades=grades,
                       subjects=subjects,
                       grades_values=grades_values,
                       attendance=attendance,
                       upcoming_events=upcoming_events_data,
                       semester_comparison=semester_comparison,
                       announcements=announcements_data)

# Faculty Dashboard
@app.route('/faculty_dashboard')
@login_required
def faculty_dashboard():
    if session['user']['role'] not in ['faculty', 'admin']:
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    all_students = list(students.find())
    return render_template('faculty_dashboard.html', students=all_students)

# Update Student Record
@app.route('/update_student_record', methods=['POST'])
@login_required
def update_student_record():
    if session['user']['role'] not in ['faculty', 'admin']:
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    student_email = request.form['student_email'].strip().lower()
    subject = request.form['subject'].strip()
    attendance_value = int(request.form['attendance'].strip())

    try:
        grade = int(request.form['grade'])
    except ValueError:
        flash("Invalid grade entered.")
        return redirect(url_for('faculty_dashboard'))

    student = students.find_one({'email': student_email})
    if not student:
        flash("Student not found.")
        return redirect(url_for('faculty_dashboard'))

    update_fields = {
        f"grades.{subject}": grade,
        f"attendance.{subject}": attendance_value
    }

    students.update_one({'email': student_email}, {'$set': update_fields})
    log_activity(f"Updated {subject} for {student_email}", session['user']['name'], session['user']['role'])
    flash("Student record updated.")
    return redirect(url_for('faculty_dashboard'))

# Staff Dashboard
@app.route('/staff_dashboard')
@login_required
def staff_dashboard():
    if session['user']['role'] not in ['staff', 'admin']:
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    # Fetch events and notifications for staff dashboard
    event_list = events.find().sort("timestamp", -1)
    notification_list = activities.find().sort("timestamp", -1)
    
    return render_template('staff_dashboard.html', events=event_list, notifications=notification_list)

# Create Event
@app.route('/create_event', methods=['POST'])
@login_required
def create_event():
    if session['user']['role'] != 'staff':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    title = request.form['title'].strip()
    date = datetime.strptime(request.form['date'], '%Y-%m-%d')  # Ensure date is in datetime format
    event_type = request.form['event_type']

    if title and date:
        events.insert_one({
            'title': title,
            'date': date,
            'event_type': event_type,
            'created_by': session['user']['name'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        log_activity('Created a new event', session['user']['name'], session['user']['role'])

    return redirect(url_for('staff_dashboard'))

# Send Notification
@app.route('/send_notification', methods=['POST'])
@login_required
def send_notification():
    if session['user']['role'] != 'staff':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    notification_text = request.form['notification_text'].strip()
    if notification_text:
        # Store notification in announcements collection
        announcements_collection.insert_one({
            'message': notification_text,
            'sender': session['user']['name'],
            'role': session['user']['role'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        # Log staff activity
        log_activity('Sent a notification', session['user']['name'], session['user']['role'])

    return redirect(url_for('staff_dashboard'))

# View All Users - Admin Only
@app.route('/view_users')
@login_required
def view_users():
    if session['user']['role'] != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    query = request.args.get('search', '').strip()
    if query:
        found_users = users.find({
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'email': {'$regex': query, '$options': 'i'}}
            ]
        })
    else:
        found_users = users.find()

    return render_template('view_users.html', users=found_users)

# API Routes
@app.route('/get_events')
@login_required
def get_events():
    return jsonify(list(events.find().sort('timestamp', -1).limit(20)))

@app.route('/get_notifications')
@login_required
def get_notifications():
    return jsonify(list(activities.find().sort('timestamp', -1).limit(1)))

# View Student Profile
from urllib.parse import unquote_plus
from flask import session, flash, redirect, url_for, render_template

@app.route('/view_student/<encoded_email>')
@login_required
def view_student(encoded_email):
    user = session.get('user')
    if not user or user.get('role') not in ['admin', 'faculty', 'staff']:
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    # Decode the URL-encoded email
    email = unquote_plus(encoded_email)

    student = students.find_one({'email': email})
    if not student:
        flash("Student not found.")
        return redirect(url_for(f"{user['role']}_dashboard"))

    grades = student.get('grades', {})
    attendance_dict = student.get('attendance', {})
    subjects = list(grades.keys())
    grades_values = [grades[sub] for sub in subjects]
    attendance = [attendance_dict.get(sub, 0) for sub in subjects]

    return render_template('student_dashboard.html',
                           student=student,  # Pass the whole student object
                           grades=grades,
                           subjects=subjects,
                           grades_values=grades_values,
                           attendance=attendance,
                           is_viewing=True)

# Search Student
@app.route('/search_student')
@login_required
def search_student():
    if session['user']['role'] not in ['admin', 'faculty', 'staff']:
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    query = request.args.get('query', '').strip()
    if not query:
        flash("Please enter a search term.")
        return redirect(url_for(f"{session['user']['role']}_dashboard"))

    students_found = list(students.find({
        '$or': [
            {'name': {'$regex': query, '$options': 'i'}},
            {'email': {'$regex': query, '$options': 'i'}}
        ]
    }))

    return render_template('search_results.html', students=students_found)

# POST route to update/send announcements
@app.route('/update_announcement', methods=['POST'])
def update_announcement():
    try:
        announcement_data = request.get_json()

        if not announcement_data or 'announcement' not in announcement_data:
            return jsonify({"status": "error", "message": "Announcement data missing."}), 400

        announcement_text = announcement_data['announcement']
        staff_id = announcement_data.get('staff_id', 'Unknown Staff')  # Optional: Replace with real ID after auth

        if not announcement_text.strip():
            return jsonify({"status": "error", "message": "Announcement cannot be empty."}), 400

        # Create document to store
        announcement_doc = {
            "announcement": announcement_text,
            "staff_id": staff_id,
            "timestamp": datetime.utcnow()
        }

        announcements_collection.db.announcements.insert_one(announcement_doc)

        return jsonify({"status": "success", "message": "Announcement stored successfully."}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/update_resource', methods=['POST'])
@login_required
def update_resource():
    if session['user']['role'] != 'staff':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    resource_id = request.form.get('resource_id')
    title = request.form.get('title')
    description = request.form.get('description')

    if not resource_id or not title:
        flash("Missing resource ID or title.")
        return redirect(url_for('staff_dashboard'))

    from bson.objectid import ObjectId
    try:
        resources_collection.update_one(
            {'_id': ObjectId(resource_id)},
            {'$set': {
                'title': title,
                'description': description,
                'updated_at': datetime.utcnow()
            }}
        )
        log_activity(f"Staff updated resource: {title}", session['user']['name'], session['user']['role'])
        flash("Resource updated successfully.")
    except Exception as e:
        flash(f"Failed to update resource: {e}")

    return redirect(url_for('staff_dashboard'))

faq_data = [
    {"question": "How can I reset my password?", "answer": "To reset your password, go to the 'Account Settings' page and click on 'Reset Password.'"},
    {"question": "How can I check my marks?", "answer": "You can view your marks on the 'Student Portal' under the 'Marks' section."},
    {"question": "How do I view my attendance?", "answer": "You can check your attendance in the 'Attendance' section of the Student Portal."},
    {"question": "How do I update my profile?", "answer": "To update your profile, go to the 'Profile' page and click on 'Edit Profile.'"},
    {"question": "How do I contact support?", "answer": "You can contact support through the 'Contact Us' section or email support@campus.com."},
    # Add more relevant FAQs here
]

from sentence_transformers import SentenceTransformer, util

# Load the Sentence-Transformer model once
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

# Create embeddings for the FAQ data
faq_questions = [faq["question"] for faq in faq_data]
faq_answers = [faq["answer"] for faq in faq_data]
faq_embeddings = model.encode(faq_questions, convert_to_tensor=True)

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "GET":
        return render_template("chatbot.html")  # Show the chatbot interface

    # Handle chatbot message (POST)
    data = request.get_json()
    user_input = f"{data['role']} - {data['message']}"  # Combine role and message
    user_embedding = model.encode(user_input, convert_to_tensor=True)

    # Find the best match between the user query and the FAQ data
    scores = util.pytorch_cos_sim(user_embedding, faq_embeddings)[0]
    best_score_idx = int(scores.argmax())
    best_score = float(scores[best_score_idx])

    # Increase the similarity threshold to filter out irrelevant answers
    if best_score >= 0.7:  # Increased threshold for better matches
        answer = faq_answers[best_score_idx]
    else:
        answer = "❓ I'm not sure how to help with that. Please contact your department for support."

    return jsonify({"response": answer})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
