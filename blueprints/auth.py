from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, login_required, logout_user
from werkzeug.security import check_password_hash

from models import User

bp = Blueprint('auth', __name__)


@bp.route('/')
def home():
    return redirect(url_for('dashboard.acompanhamento'))


@bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        senha = request.form.get('senha','')
        user  = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for('auth.dashboard'))
        return render_template('login.html', erro='E-mail ou senha inválidos.')
    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('dashboard.acompanhamento'))
