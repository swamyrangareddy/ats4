import streamlit as st
st.set_page_config(layout="wide")
import sqlite3
import hashlib
import time
import streamlit_cookies_manager

# Importing utility functions and pages
from utils.data_loader import load_data
from utils.recruiter_page import recruiter_page
from utils.jobs_page import jobs_page
from utils.submissions_page import submissions_page
from utils.dashboard import dashboard
from utils.Bulk_Upload import run_app
from utils.ATS_Score import resume_matching_system
from utils.search import search_fun

# Set page configuration (must be the first Streamlit command)


# Initialize cookie manager
cookies = streamlit_cookies_manager.CookieManager()

st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #0066cc;
            color: white;
        }
        .stButton>button:hover {
            background-color: #0052a3;
        }
        .success-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            color: #155724;
        }
        .text-area {
            border-radius: 0.5rem;
            border: 1px solid #ccc;
            padding: 0.5rem;
            font-size: 1rem;
            line-height: 1.5rem;
        }
        </style>
    """, unsafe_allow_html=True)


# Wait until the Cookie Manager is ready
if not cookies.ready():
    st.stop()

# Database setup
def init_db():
    conn = sqlite3.connect("mydb.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS USERS (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Utility function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Sign-Up Function
def sign_up():
    st.title("Sign Up")
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #0066cc;
            color: white;
        }
        .stButton>button:hover {
            background-color: #0052a3;
        }
        .success-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            color: #155724;
        }
        .text-area {
            border-radius: 0.5rem;
            border: 1px solid #ccc;
            padding: 0.5rem;
            font-size: 1rem;
            line-height: 1.5rem;
        }
        </style>
    """, unsafe_allow_html=True)
    with st.form("signup_form"):
        user_name = st.text_input("Username", key="signup_username")
        password = st.text_input("Password", type="password", key="signup_password")
        submit = st.form_submit_button("Sign Up")
    
    if submit:
        if not user_name or not password:
            st.error("Please fill in all fields.")
            return
        
        if len(user_name) < 5 or len(password) < 5:
            st.error("Username and password must be at least 5 characters long.")
            return
        
        conn = sqlite3.connect("mydb.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM USERS WHERE user_name = ?", (user_name,))
        if cursor.fetchone():
            st.error("Username already exists. Please choose a different one.")
        else:
            hashed_password = hash_password(password)
            cursor.execute("INSERT INTO USERS (user_name, password) VALUES (?, ?)", (user_name, hashed_password))
            conn.commit()
            st.success("Sign-Up successful! You can now log in.")
        conn.close()

# Login Function with Cookies
def login():
    st.title("Login")
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            background-color: #0066cc;
            color: white;
        }
        .stButton>button:hover {
            background-color: #0052a3;
        }
        .success-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            color: #155724;
        }
        .text-area {
            border-radius: 0.5rem;
            border: 1px solid #ccc;
            padding: 0.5rem;
            font-size: 1rem;
            line-height: 1.5rem;
        }
        .st.form-submit-button {
            width: 100%;
            background-color: #0066cc;
            color: white;
        }
        .st.form-submit-button:hover {
            background-color: #0052a3;
        }
        </style>
    """, unsafe_allow_html=True)

    # Auto-login if cookie exists
    user_cookie = cookies.get("logged_in_user")
    if user_cookie:
        st.session_state.logged_in = True
        st.session_state.user_name = user_cookie
        st.success(f"Welcome back, {user_cookie}!")
        time.sleep(1)
        st.rerun()
        return

    with st.form("login_form"):
        user_name = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submit = st.form_submit_button("Login")

    if submit:
        if not user_name or not password:
            st.error("Please fill in all fields.")
            return

        conn = sqlite3.connect("mydb.db")
        cursor = conn.cursor()
        hashed_password = hash_password(password)
        cursor.execute("SELECT * FROM USERS WHERE user_name = ? AND password = ?", (user_name, hashed_password))
        user = cursor.fetchone()
        conn.close()

        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user_name
            cookies["logged_in_user"] = user_name
            cookies.save()
            st.success("Welcome to ATS!")
            st.rerun()
        else:
            st.error("Username or password is incorrect.")

# Forgot Password Function
def forgot_password():
    st.title("Reset Password")
    st.markdown("Enter your username and your new password below.")

    with st.form("forgot_password_form"):
        user_name = st.text_input("Username", key="forgot_username")
        new_password = st.text_input("New Password", type="password", key="forgot_new_password")
        confirm_password = st.text_input("Confirm New Password", type="password", key="forgot_confirm_password")
        submit = st.form_submit_button("Reset Password")

    if submit:
        if not user_name or not new_password or not confirm_password:
            st.error("Please fill in all fields.")
            return

        if len(user_name) < 5 or len(new_password) < 5:
            st.error("Username and new password must be at least 5 characters long.")
            return

        if new_password != confirm_password:
            st.error("Passwords do not match. Please re-enter.")
            return

        conn = sqlite3.connect("mydb.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM USERS WHERE user_name = ?", (user_name,))
        if cursor.fetchone() is None:
            st.error("Username not found.")
        else:
            hashed_password = hash_password(new_password)
            cursor.execute("UPDATE USERS SET password = ? WHERE user_name = ?", (hashed_password, user_name))
            conn.commit()
            st.success("Password updated successfully! You can now log in.")
        conn.close()

# Logout Function
def logout():
    st.session_state.logged_in = False
    st.session_state.user_name = None
    cookies["logged_in_user"] = None
    cookies.save()
    st.rerun()

# Main Function
def main():
    init_db()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("Recruitment Management Dashboard")
        tabs = st.tabs(["Login", "Sign Up", "Forgot Password"])
        with tabs[0]:
            login()
        with tabs[1]:
            sign_up()
        with tabs[2]:
            forgot_password()
    else:
        # Header section with dashboard title and logout button on top-right
        col1, col2 = st.columns([9, 1])
        with col1:
            st.markdown(
                """
                <style>
                
                .dashboard-heading {
                    font-size: 3em;
                    font-weight: bold;
                    margin: 0;
                }
                @media (prefers-color-scheme: dark) {
                    .dashboard-heading {
                        color: white;
                    }
                }
                @media (prefers-color-scheme: light) {
                    .dashboard-heading {
                        color: black;
                    }
                }
                </style>
                <h1 class="dashboard-heading">Recruitment Management Dashboard</h1>
                """,
                unsafe_allow_html=True
            )
        with col2:
            if st.button("Logout", key="logout_button"):
                logout()

        # Load data for dashboard
        recruiter_detail, job_requirements, submission_table = load_data()

        # Tabs for navigation
        tabs = st.tabs([
            "Dashboard",
            "Recruiters",
            "Jobs",
            "Submissions",
            "Upload Resumes",
            "ATS Score",
            "Search"
        ])
        with tabs[0]:
            dashboard()
        with tabs[1]:
            recruiter_page()
        with tabs[2]:
            jobs_page()
        with tabs[3]:
            submissions_page()
        with tabs[4]:
            run_app()
        with tabs[5]:
            resume_matching_system()
        with tabs[6]:
            search_fun()

if __name__ == "__main__":
    main()
