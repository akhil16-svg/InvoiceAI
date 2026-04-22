"""
User Authentication System for Invoice OCR Platform
Save this as: utils/auth.py
"""

import json
import os
import hashlib
import secrets
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class AuthSystem:
    """
    Simple authentication system with user accounts
    Supports JSON and PostgreSQL
    """
    
    def __init__(self, users_file: str = 'data/users.json', db_type: str = 'postgres'):
        """
        Initialize authentication system
        
        Args:
            users_file: Path to users database file (for json)
            db_type: 'json' or 'postgres'
        """
        self.users_file = users_file
        self.db_type = db_type
        
        if self.db_type == 'json':
            self._ensure_users_file()
        elif self.db_type == 'postgres':
            self.pg_url = os.environ.get('DATABASE_URL')
            if not self.pg_url:
                raise ValueError("DATABASE_URL environment variable is missing for PostgreSQL.")
            self._init_postgres()
    
    def _ensure_users_file(self):
        """Create users file if it doesn't exist"""
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump({}, f)
                
    def _init_postgres(self):
        """Create users table in Postgres"""
        import psycopg2
        conn = psycopg2.connect(self.pg_url)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                password_hash TEXT,
                salt TEXT,
                created_at TIMESTAMP,
                data_folder TEXT,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                verification_code TEXT,
                verification_code_expires TIMESTAMP
            )
        ''')
        # Add columns if migrating from earlier schema
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
        except:
            conn.rollback()
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP")
        except:
            conn.rollback()
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN verification_code TEXT")
        except:
            conn.rollback()
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN verification_code_expires TIMESTAMP")
        except:
            conn.rollback()

        conn.commit()
        cursor.close()
        conn.close()
    
    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """Hash password with salt for security"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return pwd_hash.hex(), salt
    
    def _get_user(self, email: str) -> Optional[Dict]:
        """Fetch a single user by email"""
        if self.db_type == 'json':
            try:
                with open(self.users_file, 'r') as f:
                    users = json.load(f)
                    return users.get(email)
            except:
                return None
        elif self.db_type == 'postgres':
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(self.pg_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
                user = cursor.fetchone()
                if user:
                    return dict(user)
                return None
            finally:
                cursor.close()
                conn.close()
        return None
    
    def _save_user(self, email: str, user_data: Dict):
        """Save a user record"""
        # Ensure new fields exist
        user_data.setdefault('failed_login_attempts', 0)
        user_data.setdefault('locked_until', None)
        user_data.setdefault('verification_code', None)
        user_data.setdefault('verification_code_expires', None)
        
        if self.db_type == 'json':
            try:
                with open(self.users_file, 'r') as f:
                    users = json.load(f)
            except:
                users = {}
            # Handle datetime objects for JSON serialization
            user_data_json = dict(user_data)
            for k, v in user_data_json.items():
                if isinstance(v, datetime):
                    user_data_json[k] = v.isoformat()
            users[email] = user_data_json
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2)
                
        elif self.db_type == 'postgres':
            import psycopg2
            conn = psycopg2.connect(self.pg_url)
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (email, name, password_hash, salt, created_at, data_folder, 
                                     failed_login_attempts, locked_until, verification_code, verification_code_expires)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                        name = EXCLUDED.name,
                        password_hash = EXCLUDED.password_hash,
                        salt = EXCLUDED.salt,
                        data_folder = EXCLUDED.data_folder,
                        failed_login_attempts = EXCLUDED.failed_login_attempts,
                        locked_until = EXCLUDED.locked_until,
                        verification_code = EXCLUDED.verification_code,
                        verification_code_expires = EXCLUDED.verification_code_expires
                ''', (
                    email,
                    user_data['name'],
                    user_data['password_hash'],
                    user_data['salt'],
                    user_data['created_at'],
                    user_data['data_folder'],
                    user_data.get('failed_login_attempts', 0),
                    user_data.get('locked_until'),
                    user_data.get('verification_code'),
                    user_data.get('verification_code_expires')
                ))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
                
    def _delete_user_record(self, email: str):
        """Delete user record from DB"""
        if self.db_type == 'json':
            try:
                with open(self.users_file, 'r') as f:
                    users = json.load(f)
                if email in users:
                    del users[email]
                    with open(self.users_file, 'w') as f:
                        json.dump(users, f, indent=2)
            except:
                pass
        elif self.db_type == 'postgres':
            import psycopg2
            conn = psycopg2.connect(self.pg_url)
            cursor = conn.cursor()
            try:
                cursor.execute('DELETE FROM users WHERE email = %s', (email,))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
                
    def _send_email(self, to_email: str, subject: str, body: str):
        """Send an email using SMTP (e.g. MailHog for testing)"""
        smtp_server = os.environ.get('SMTP_SERVER', 'localhost')
        smtp_port = int(os.environ.get('SMTP_PORT', 1025))
        
        msg = MIMEMultipart()
        msg['From'] = 'noreply@invoice-ocr.local'
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def register_user(self, email: str, password: str, name: str) -> Dict[str, Any]:
        """Register a new user"""
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
            return {'success': False, 'error': 'Invalid email address format'}
            
        if self._get_user(email):
            return {'success': False, 'error': 'Email already registered'}
        
        if len(password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
        
        pwd_hash, salt = self._hash_password(password)
        
        user_data = {
            'name': name,
            'password_hash': pwd_hash,
            'salt': salt,
            'created_at': datetime.now().isoformat() if self.db_type == 'json' else datetime.now(),
            'data_folder': f'data/users/{email.replace("@", "_at_").replace(".", "_")}'
        }
        
        os.makedirs(user_data['data_folder'], exist_ok=True)
        self._save_user(email, user_data)
        
        return {'success': True, 'message': 'Account created successfully!'}
    
    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Login user with brute force protection"""
        user = self._get_user(email)
        
        if not user:
            return {'success': False, 'error': 'Invalid email or password'}
            
        # Parse dates if JSON
        locked_until = user.get('locked_until')
        if isinstance(locked_until, str):
            try:
                locked_until = datetime.fromisoformat(locked_until)
            except:
                locked_until = None
        
        # Check if account is locked
        if locked_until and datetime.now() < locked_until:
            return {'success': False, 'error': 'Account is temporarily locked due to too many failed attempts. Try again later.'}
        
        # Verify password
        pwd_hash, _ = self._hash_password(password, user['salt'])
        
        if pwd_hash != user['password_hash']:
            # Handle failed attempt
            attempts = user.get('failed_login_attempts', 0) + 1
            user['failed_login_attempts'] = attempts
            
            if attempts >= 5:
                user['locked_until'] = datetime.now() + timedelta(minutes=15)
                self._save_user(email, user)
                return {'success': False, 'error': 'Account locked due to 5 failed attempts. Please wait 15 minutes or reset your password.'}
            
            self._save_user(email, user)
            return {'success': False, 'error': 'Invalid email or password'}
        
        # Login successful - reset counters
        user['failed_login_attempts'] = 0
        user['locked_until'] = None
        self._save_user(email, user)
        
        created_at_str = user['created_at'].isoformat() if isinstance(user['created_at'], datetime) else user['created_at']
        
        return {
            'success': True,
            'user': {
                'email': email,
                'name': user['name'],
                'data_folder': user['data_folder'],
                'created_at': created_at_str
            }
        }
        
    def request_password_reset(self, email: str) -> Dict[str, Any]:
        """Generate and email a 6-digit reset code"""
        user = self._get_user(email)
        if not user:
            # Return true anyway to prevent email enumeration attacks
            return {'success': True, 'message': 'If the email exists, a reset code was sent.'}
            
        code = str(secrets.randbelow(1000000)).zfill(6)
        
        user['verification_code'] = code
        user['verification_code_expires'] = datetime.now() + timedelta(minutes=10)
        
        self._save_user(email, user)
        
        # Send Email
        body = f"Hello {user['name']},\n\nYour password reset code is: {code}\n\nThis code will expire in 10 minutes.\nIf you did not request this, please ignore this email."
        self._send_email(email, "Invoice OCR - Password Reset Code", body)
        
        return {'success': True, 'message': 'If the email exists, a reset code was sent.'}
        
    def verify_and_reset_password(self, email: str, code: str, new_password: str) -> Dict[str, Any]:
        """Verify the 2FA code and set new password"""
        user = self._get_user(email)
        if not user:
            return {'success': False, 'error': 'Invalid request'}
            
        if not user.get('verification_code') or user['verification_code'] != code:
            return {'success': False, 'error': 'Invalid or expired code'}
            
        expires = user.get('verification_code_expires')
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires)
            except:
                expires = None
                
        if not expires or datetime.now() > expires:
            return {'success': False, 'error': 'Code has expired. Please request a new one.'}
            
        if len(new_password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
            
        # Reset password
        new_hash, new_salt = self._hash_password(new_password)
        user['password_hash'] = new_hash
        user['salt'] = new_salt
        
        # Clear reset code and unlock account
        user['verification_code'] = None
        user['verification_code_expires'] = None
        user['failed_login_attempts'] = 0
        user['locked_until'] = None
        
        self._save_user(email, user)
        return {'success': True, 'message': 'Password has been reset successfully!'}
    
    def change_password(self, email: str, old_password: str, new_password: str) -> Dict[str, Any]:
        """Change user password"""
        user = self._get_user(email)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        pwd_hash, _ = self._hash_password(old_password, user['salt'])
        if pwd_hash != user['password_hash']:
            return {'success': False, 'error': 'Current password is incorrect'}
        
        if len(new_password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters'}
        
        new_hash, new_salt = self._hash_password(new_password)
        user['password_hash'] = new_hash
        user['salt'] = new_salt
        
        self._save_user(email, user)
        return {'success': True, 'message': 'Password changed successfully'}
    
    def delete_account(self, email: str, password: str) -> Dict[str, Any]:
        """Delete user account"""
        user = self._get_user(email)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        pwd_hash, _ = self._hash_password(password, user['salt'])
        if pwd_hash != user['password_hash']:
            return {'success': False, 'error': 'Incorrect password'}
        
        import shutil
        if os.path.exists(user['data_folder']):
            shutil.rmtree(user['data_folder'])
        
        self._delete_user_record(email)
        return {'success': True, 'message': 'Account deleted successfully'}


# Streamlit integration functions
def show_login_page():
    """Display login/register/reset page in Streamlit"""
    import streamlit as st
    
    st.markdown("""
        <div style="text-align: center; padding: 50px 0;">
            <h1 style="color: #00DC83; font-size: 3rem;">Invoice Intelligence</h1>
            <p style="color: #999; font-size: 1.2rem;">Sign in to access your invoices</p>
        </div>
    """, unsafe_allow_html=True)
    
    auth = AuthSystem()
    
    tab1, tab2, tab3 = st.tabs(["🔐 Login", "📝 Register", "🔑 Forgot Password"])
    
    with tab1:
        st.markdown("### Login to Your Account")
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    result = auth.login_user(email, password)
                    if result['success']:
                        st.session_state.user = result['user']
                        st.session_state.logged_in = True
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
    
    with tab2:
        st.markdown("### Create New Account")
        with st.form("register_form"):
            name = st.text_input("Full Name", placeholder="John Doe")
            email_reg = st.text_input("Email", placeholder="your@email.com", key="reg_email")
            password_reg = st.text_input("Password", type="password", key="reg_pwd", help="Minimum 6 characters")
            password_confirm = st.text_input("Confirm Password", type="password")
            submit_reg = st.form_submit_button("Create Account", use_container_width=True)
            
            if submit_reg:
                if not name or not email_reg or not password_reg:
                    st.error("Please fill in all fields")
                elif password_reg != password_confirm:
                    st.error("Passwords don't match")
                else:
                    result = auth.register_user(email_reg, password_reg, name)
                    if result['success']:
                        st.success("✅ Account created! Please login.")
                    else:
                        st.error(f"❌ {result['error']}")
                        
    with tab3:
        st.markdown("### Reset Password")
        if 'reset_email_sent' not in st.session_state:
            st.session_state.reset_email_sent = False
            
        if not st.session_state.reset_email_sent:
            with st.form("forgot_password_form"):
                reset_email = st.text_input("Email Address", placeholder="your@email.com")
                if st.form_submit_button("Send Reset Code", use_container_width=True):
                    if not reset_email:
                        st.error("Please enter your email")
                    else:
                        auth.request_password_reset(reset_email)
                        st.session_state.reset_email = reset_email
                        st.session_state.reset_email_sent = True
                        st.success("If an account exists, a 6-digit code has been sent to your email.")
                        st.rerun()
        else:
            with st.form("reset_password_form"):
                st.info(f"Enter the 6-digit code sent to {st.session_state.reset_email}")
                code = st.text_input("6-Digit Code")
                new_pwd = st.text_input("New Password", type="password")
                new_pwd_confirm = st.text_input("Confirm New Password", type="password")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_reset = st.form_submit_button("Reset Password", use_container_width=True)
                with col2:
                    if st.form_submit_button("Start Over", use_container_width=True):
                        st.session_state.reset_email_sent = False
                        st.rerun()
                
                if submit_reset:
                    if not code or not new_pwd:
                        st.error("Please fill in all fields")
                    elif new_pwd != new_pwd_confirm:
                        st.error("Passwords don't match")
                    else:
                        result = auth.verify_and_reset_password(st.session_state.reset_email, code, new_pwd)
                        if result['success']:
                            st.success("✅ Password reset! You can now log in.")
                            st.session_state.reset_email_sent = False
                        else:
                            st.error(f"❌ {result['error']}")

def show_user_profile():
    """Display user profile in sidebar"""
    import streamlit as st
    
    if not st.session_state.get('user'):
        return
    
    user = st.session_state.user
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Account")
    st.sidebar.markdown(f"**{user['name']}**")
    st.sidebar.markdown(f"📧 {user['email']}")
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()
    
    with st.sidebar.expander("⚙️ Account Settings"):
        auth = AuthSystem()
        
        st.markdown("**Change Password**")
        with st.form("change_password"):
            old_pwd = st.text_input("Current Password", type="password", key="old")
            new_pwd = st.text_input("New Password", type="password", key="new")
            new_pwd_confirm = st.text_input("Confirm New Password", type="password", key="confirm")
            
            if st.form_submit_button("Change Password"):
                if new_pwd != new_pwd_confirm:
                    st.error("Passwords don't match")
                else:
                    result = auth.change_password(user['email'], old_pwd, new_pwd)
                    if result['success']:
                        st.success("Password changed!")
                    else:
                        st.error(result['error'])
        
        st.markdown("---")
        st.markdown("**Delete Account**")
        if st.button("❌ Delete My Account", type="secondary"):
            st.session_state.show_delete_confirm = True
        
        if st.session_state.get('show_delete_confirm', False):
            st.warning("⚠️ This cannot be undone!")
            delete_pwd = st.text_input("Enter password to confirm", type="password", key="del_pwd")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Cancel"):
                    st.session_state.show_delete_confirm = False
                    st.rerun()
            
            with col2:
                if st.button("Delete", type="primary"):
                    result = auth.delete_account(user['email'], delete_pwd)
                    if result['success']:
                        st.session_state.logged_in = False
                        st.session_state.user = None
                        st.success("Account deleted")
                        st.rerun()
                    else:
                        st.error(result['error'])

def require_auth(func):
    """Decorator to require authentication for pages"""
    def wrapper(*args, **kwargs):
        import streamlit as st
        if not st.session_state.get('logged_in', False):
            show_login_page()
            st.stop()
        return func(*args, **kwargs)
    return wrapper

def init_auth_state():
    """Initialize authentication session state"""
    import streamlit as st
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None