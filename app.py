

from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, session
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange
import bcrypt
import MySQLdb.cursors
import subprocess
import os
import uuid


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# MySQL configurations
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mydatabase'

# Initialize MySQL
mysql = MySQL(app)

# ------------------------
# Forms Section
# ------------------------

class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")

class ReviewForm(FlaskForm):
    comment = StringField("Comment", validators=[DataRequired()])
    rating = IntegerField("Rating", validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField("Submit Review")

# ------------------------
# User Registration Section
# ------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        name = form.name.data
        password = form.password.data

        # Check if the email already exists
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            form.email.errors.append('An account with this email already exists. Please use a different email.')
            return render_template('register.html', form=form)

        # Hash the password and insert the new user into the database
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("INSERT INTO user (name, email, password) VALUES (%s, %s, %s)", 
                       (name, email, hashed_password))
        mysql.connection.commit()
        cursor.close()

        # Flash a success message and redirect to the login page
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)




# ------------------------
# User Login Section
# ------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Get form data
        email = form.email.data
        password = form.password.data

        # Fetch the user from the database
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        # Validate the user's password
        if user:
            stored_password = user['password']
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                session['user_id'] = user['id']
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password', 'danger')
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html', form=form)

# ------------------------
# Review Submission Section
# ------------------------

@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    form = ReviewForm()
    if form.validate_on_submit():
        # Get form data
        comment = form.comment.data
        rating = form.rating.data

        # Check if the user is logged in
        user_id = session.get('user_id')
        if not user_id:
            flash('You need to be logged in to leave a review', 'danger')
            return redirect(url_for('login'))

        # Insert the review into the database
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO review (user_id, comment, rating) VALUES (%s, %s, %s)", (user_id, comment, rating))
        mysql.connection.commit()
        cursor.close()

        flash('Review submitted successfully!', 'success')
        return redirect(url_for('reviews'))

    # Fetch and display all reviews
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT r.comment, r.rating, u.name FROM review r JOIN user u ON r.user_id = u.id")
    reviews = cursor.fetchall()
    cursor.close()

    return render_template('reviews.html', form=form, reviews=reviews)

# ------------------------
# Compiler Section
# ------------------------

@app.route('/compiler')
def index():
    return render_template('compiler.html')

@app.route('/run', methods=['POST'])
def run_code():
    data = request.json
    code = data['code']
    input_data = data['input']
    language = data['language']

    # Generate a unique identifier for temporary files
    unique_id = str(uuid.uuid4())

    try:
        # Run the code based on the selected language
        if language in ['python', 'python3']:
            filename = f'{unique_id}.py'
            with open(filename, 'w') as f:
                f.write(code)

            result = subprocess.run(
                ['python3', filename], input=input_data, text=True,
                capture_output=True, check=True
            )
            output = result.stdout + result.stderr

        elif language == 'c':
            filename = f'{unique_id}.c'
            exe_filename = f'{unique_id}'
            with open(filename, 'w') as f:
                f.write(code)

            subprocess.run(['gcc', filename, '-o', exe_filename], check=True)
            result = subprocess.run([f'./{exe_filename}'], input=input_data, text=True, capture_output=True, check=True)
            output = result.stdout + result.stderr

        elif language == 'cpp':
            filename = f'{unique_id}.cpp'
            exe_filename = f'{unique_id}'
            with open(filename, 'w') as f:
                f.write(code)

            subprocess.run(['g++', filename, '-o', exe_filename], check=True)
            result = subprocess.run([f'./{exe_filename}'], input=input_data, text=True, capture_output=True, check=True)
            output = result.stdout + result.stderr

        elif language == 'java':
            filename = f'{unique_id}.java'
            classname = 'Program'
            with open(filename, 'w') as f:
                f.write(code)

            subprocess.run(['javac', filename], check=True)
            result = subprocess.run(['java', classname], input=input_data, text=True, capture_output=True, check=True)
            output = result.stdout + result.stderr

        else:
            output = "Unsupported language"

        return jsonify({'output': output})

    except subprocess.CalledProcessError as e:
        return jsonify({'output': e.output + e.stderr}), 400

    finally:
        # Clean up temporary files
      
        if language in ['c', 'cpp'] and os.path.exists(exe_filename):
            os.remove(exe_filename)
        if language == 'java' and os.path.exists(f'{classname}.class'):
            os.remove(f'{classname}.class')

# ------------------------
# Home Route
# ------------------------

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
