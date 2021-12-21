import functools, re

from datetime import datetime, date

from flask import(
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from flaskr.db import auto_keys, get_db, insert_or_update, request_fetchall, request_fetchone

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        db = get_db()
        error = None
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        elif not email:
            error = 'Email is required'
        elif not re.fullmatch(regex, email):
            error = 'Invalid email address'
        
        if error is None:
            try:
                insert_or_update("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(password)),)
            except:
                usernames = request_fetchall("SELECT username FROM user", ['username'])
                emails = request_fetchall("SELECT email FROM user", ['email'])
                if username in usernames:
                    error = f"User {username} is already registered."
                elif email in emails:
                    error = f"Email {email} is already used."
                else:
                    error = "An error occured in the database."

            else:
                return redirect(url_for("auth.login"))
        
        flash(error)

    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = request_fetchone('SELECT * FROM users WHERE username = ?', auto_keys('users'), (username,))

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password'
        
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        
        flash(error)
    
    return render_template('auth/login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = request_fetchone('SELECT * FROM users WHERE id = ?', auto_keys('users'), (user_id,))
        last_post = request_fetchone('SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC', auto_keys('preds'), (user_id,))
        if last_post is not None:
            date_post = last_post['created']
            today = date.today()
            post_day = date(date_post.year, date_post.month, date_post.day)
            if today == post_day:
                g.edit = True
            else:
                g.edit = None
        else:
            g.edit = None
        if datetime.today().weekday() == 0:
            g.monday = True
        elif datetime.today().strftime('%Y-%m-%d') == '2021-12-15':
            g.monday = None
        else:
            g.monday = True

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        
        return view(**kwargs)
    
    return wrapped_view
