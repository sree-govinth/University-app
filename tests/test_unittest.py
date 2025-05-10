import unittest
from werkzeug.security import generate_password_hash
import sys
import os
from urllib.parse import quote_plus

# Ensure that the parent directory is included in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the app and db modules
from app import app, db


class AppTestCase(unittest.TestCase):

    def setUp(self):
        # Configure test environment
        app.config['TESTING'] = True
        app.config['MONGO_URI'] = "mongodb://localhost:27017/test_db"
        self.client = app.test_client()

        # Reset DB
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

    def tearDown(self):
        # Clean up the database after each test
        db.users.drop()
        db.students.drop()

    def test_home_redirect(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_signup_page(self):
        response = self.client.get('/signup', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Signup", response.data)

    def test_login_success(self):
        response = self.client.post('/login', data=dict(
            email="testuser@example.com",
            password="password123"
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Dashboard", response.data)

    def test_login_failure(self):
        response = self.client.post('/login', data=dict(
            email="wrong@example.com",
            password="wrongpass"
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email or password", response.data)

    def test_admin_dashboard_redirect_if_not_logged_in(self):
        response = self.client.get('/admin', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You need to log in first.", response.data)

    def test_admin_dashboard(self):
        self.client.post('/login', data=dict(
            email="testuser@example.com",
            password="password123"
        ), follow_redirects=True)
        response = self.client.get('/admin', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Dashboard", response.data)

    def test_create_event(self):
        self.client.post('/login', data=dict(
            email="staffuser@example.com",
            password="password123"
        ), follow_redirects=True)
        response = self.client.post('/create_event', data=dict(
            title="Test Event",
            date="2025-05-20",
            event_type="Lecture"
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Event", response.data)

    def test_view_users_as_admin(self):
        self.client.post('/login', data=dict(
            email="testuser@example.com",
            password="password123"
        ), follow_redirects=True)
        response = self.client.get('/view_users')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test User", response.data)

    def test_view_student_profile(self):
        test_email = "student1@example.com"
        db.students.insert_one({
            "name": "Student One",
            "email": test_email,
            "grades": {
                "Semester 1": {"Math": 85, "Science": 90},
                "Semester 2": {"Math": 80, "Science": 88}
            },
            "attendance": {
                "Semester 1": {"Math": 90, "Science": 92},
                "Semester 2": {"Math": 88, "Science": 91}
            }
        })

        self.client.post('/login', data=dict(
            email="testuser@example.com",
            password="password123"
        ), follow_redirects=True)

        encoded_email = quote_plus(test_email)
        response = self.client.get(f'/view_student/{encoded_email}', follow_redirects=True)

        self.assertIn(b"Student One", response.data)
        self.assertIn(b"Semester 1", response.data)
        self.assertIn(b"Math", response.data)
        self.assertIn(b"Science", response.data)

    def test_logout(self):
        self.client.post('/login', data=dict(
            email="testuser@example.com",
            password="password123"
        ), follow_redirects=True)
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Logged out successfully.", response.data)
        self.assertIn(b"Login", response.data)


if __name__ == '__main__':
    unittest.main()
