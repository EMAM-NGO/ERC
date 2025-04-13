from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, LoginManager, login_user, login_required, current_user, logout_user
from supabase import create_client, Client
import os

# Initialize Flask app
app = Flask(__name__)  
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Initialize Supabase client using environment variables
url = os.getenv("SUPABASE_URL")  # Get Supabase URL from environment variable
key = os.getenv("SUPABASE_KEY")  # Get Supabase Key from environment variable

if not url or not key:
    raise ValueError("Supabase URL or Key is not set in environment variables")

supabase: Client = create_client(url, key)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# User class representing a single user
class User(UserMixin):
    def __init__(self, id, username, password, is_admin=False):
        self.id = str(id)
        self.username = username
        self.password = password
        self.is_admin = is_admin

    def __repr__(self):
        return f"<User {self.username}>"

    @classmethod
    def get(cls, user_id):
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        if result.data:
            user = result.data[0]
            return cls(user['id'], user['username'], user['password'], user.get('is_admin', False))
        return None

    @classmethod
    def get_by_username(cls, username):
        result = supabase.table('users').select('*').eq('username', username).execute()
        if result.data:
            user = result.data[0]
            return cls(user['id'], user['username'], user['password'], user.get('is_admin', False))
        return None

# Grade class representing a single quiz result
class Grade:
    def __init__(self, id, user_id, quiz_name, grade, bonus, final_grade, paper_url):
        self.id = id
        self.user_id = user_id
        self.quiz_name = quiz_name
        self.grade = grade
        self.bonus = bonus
        self.final_grade = final_grade
        self.status = "Passed" if score >= 16 else "Failed"
        self.paper_url = paper_url

    def __repr__(self):
        return f"<Grade {self.quiz_name} - {self.score} for user {self.user_id}, Status: {self.status}>"

    @classmethod
    def get_by_user(cls, user_id):
        # Fetch all grades for the user
        results = supabase.table('grades').select('*').eq('user_id', user_id).execute()
        return [cls(g['id'], g['user_id'], g['quiz_name'], g['score'], g['bonus'], g['final_score'], g['paper_url']) for g in results.data]


    @classmethod
    def add_grade(cls, user_id, quiz_name, score):
        data = {
            'user_id': user_id,
            'quiz_name': quiz_name,
            'score': score,
        }
        supabase.table('grades').insert(data).execute()

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        if current_user.is_admin and request.args.get('force_home') != '1':
            return redirect(url_for('manage_users'))
        return render_template('home.html', user=current_user)

    if request.method == 'POST':
        user_id = request.form.get("user_id")
        password = request.form.get("password")

        if not user_id or not password:
            flash("⚠ Both user ID and password are required.", "danger")
            return redirect(url_for('home'))

        user = User.get(user_id)  # Fetch user by ID
        if user and password:
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash("⚠ Invalid user ID or password.", "danger")
            return redirect(url_for('home'))

    return render_template('home.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        flash("⚠ You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        user_id = request.form['id']
        username = request.form["username"]
        password = request.form["password"]

        if User.get_by_username(username):
            flash("⚠ Username already exists, please choose a different one.", "warning")
            return redirect(url_for('add_user'))

        user_data = {
            'id': user_id,
            'username': username,
            'password': password,
            'is_admin': False
        }
        supabase.table('users').insert(user_data).execute()
        flash("✅ User added successfully.", "success")
        return redirect(url_for('manage_users'))

    return render_template('add_user.html')

@app.route('/manage_users')
@login_required
def manage_users():
    if not current_user.is_admin:
        flash("⚠ You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))

    users = supabase.table('users').select('*').execute().data
    return render_template('manage_users.html', users=users)

@app.route('/remove_user/<string:id>', methods=['POST'])
@login_required
def remove_user(id):
    if not current_user.is_admin:
        flash("⚠ You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))

    user_to_remove = User.get(id)
    if user_to_remove and user_to_remove.id == current_user.id:
        flash("⚠ You cannot remove your own account.", "danger")
        return redirect(url_for('manage_users'))

    supabase.table('users').delete().eq('id', id).execute()
    flash("✅ User removed successfully.", "success")
    return redirect(url_for('manage_users'))

@app.route('/toggle_admin/<string:id>', methods=['POST'])
@login_required
def toggle_admin(id):
    if not current_user.is_admin:
        flash("⚠ You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))

    user = User.get(id)
    if user:
        new_status = not user.is_admin
        supabase.table('users').update({'is_admin': new_status}).eq('id', user.id).execute()
        flash(f"✅ User {user.username} admin status updated.", "success")

    return redirect(url_for('manage_users'))

@app.route('/add_grade/<string:user_id>', methods=['GET', 'POST'])
@login_required
def add_grade(user_id):
    if not current_user.is_admin:
        flash("⚠ You do not have permission to access this page.", "danger")
        return redirect(url_for('home'))

    user = User.get(user_id)

    if request.method == 'POST':
        quiz_name = request.form['quiz_name']
        score = float(request.form['score'])

        Grade.add_grade(user_id, quiz_name, score)
        flash("✅ Grade added successfully.", "success")
        return redirect(url_for('view_grades', user_id=user_id))

    return render_template('add_grade.html', user=user)

@app.route('/view_grades/<string:user_id>')
@login_required
def view_grades(user_id):
    if not current_user.is_admin and current_user.id != user_id:
        flash("⚠ You do not have permission to view these grades.", "danger")
        return redirect(url_for('home'))

    user = User.get(user_id)
    grades = Grade.get_by_user(user_id)
    return render_template('view_grades.html', user=user, grades=grades)
