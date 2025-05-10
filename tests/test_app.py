import pytest
from app import app, db
from werkzeug.security import generate_password_hash
import sys
import os
import urllib.parse  # Import for URL encoding

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['MONGO_URI'] = "mongodb://localhost:27017/test_db"
    with app.test_client() as client:
        yield client

@pytest.fixture
def init_db():
    # Clear collections before and after tests
    db.users.drop()
    db.students.drop()
    
    # Insert test users
    db.users.insert_one({
        "name": "Test User",
        "email": "testuser@example.com",
        "password": generate_password_hash("password123"),
        "role": "admin"
    })
    db.users.insert_one({
        "name": "Staff User",
        "email": "staffuser@example.com",
        "password": generate_password_hash("password123"),
        "role": "staff"
    })
    
    yield db
    
    # Cleanup after test
    db.users.drop()
    db.students.drop()

def test_home_redirect(client):
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_signup_page(client):
    response = client.get('/signup', follow_redirects=True)
    assert response.status_code == 200
    assert b"Signup" in response.data

def test_login_success(client, init_db):
    response = client.post('/login', data=dict(
        email="testuser@example.com",
        password="password123"
    ), follow_redirects=True)
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data  # Ensure proper page rendering

def test_login_failure(client):
    response = client.post('/login', data=dict(
        email="wrongemail@example.com",
        password="wrongpassword"
    ), follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

def test_admin_dashboard_redirect_if_not_logged_in(client):
    response = client.get('/admin', follow_redirects=True)
    assert response.status_code == 200
    assert b"You need to log in first." in response.data

def test_admin_dashboard(client, init_db):
    client.post('/login', data=dict(
        email="testuser@example.com",
        password="password123"
    ), follow_redirects=True)
    response = client.get('/admin', follow_redirects=True)
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data

def test_create_event(client, init_db):
    client.post('/login', data=dict(
        email="staffuser@example.com",
        password="password123"
    ), follow_redirects=True)
    response = client.post('/create_event', data=dict(
        title="Test Event",
        date="2025-05-20",
        event_type="Lecture"
    ), follow_redirects=True)
    assert response.status_code == 200
    assert b"Test Event" in response.data  # Check if event is correctly created

def test_view_users_as_admin(client, init_db):
    client.post('/login', data=dict(
        email="testuser@example.com",
        password="password123"
    ), follow_redirects=True)
    response = client.get('/view_users')
    assert response.status_code == 200
    assert b"Test User" in response.data  # Admin can view user

def test_view_student_profile(client, init_db):
    # Insert a student profile for testing
    test_student_email = "student1@example.com"
    db.students.insert_one({
        "name": "Student One",
        "email": test_student_email,
        "grades": {
            "Semester 1": {"Math": 85, "Science": 90},
            "Semester 2": {"Math": 80, "Science": 88}
        },
        "attendance": {
            "Semester 1": {"Math": 90, "Science": 92},
            "Semester 2": {"Math": 88, "Science": 91}
        }
    })

    # Ensure the student was inserted
    student = db.students.find_one({"email": test_student_email})
    assert student is not None, "Test student was not inserted into the database."

    # Login as admin
    login_response = client.post('/login', data=dict(
        email="testuser@example.com",
        password="password123"
    ), follow_redirects=True)
    assert b"Dashboard" in login_response.data or login_response.status_code == 200, "Login failed"

    # URL encode the email
    encoded_email = urllib.parse.quote_plus(test_student_email)

    # Visit the student's profile page
    response = client.get(f'/view_student/{encoded_email}', follow_redirects=True)
    html = response.data.decode('utf-8')  # Decode to inspect HTML response

    print("\n==== Student Profile Page HTML ====\n", html)

    # Assertions
    assert b"Student One" in response.data, "Student name not found in response"
    assert b"Semester 1" in response.data, "Semester 1 not displayed"
    assert b"Math" in response.data, "Math subject not displayed"
    assert b"Science" in response.data, "Science subject not displayed"

def test_logout(client, init_db):
    client.post('/login', data=dict(
        email="testuser@example.com",
        password="password123"
    ), follow_redirects=True)
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"Logged out successfully." in response.data
    assert b"Login" in response.data  # Check that Login button is visible after logout
