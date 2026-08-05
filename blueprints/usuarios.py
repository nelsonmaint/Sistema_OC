from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

from models import db, User
from constants import AREAS_CADASTRO
from helpers import admin_required

bp = Blueprint('usuarios', __name__)


@bp.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    usuarios = User.query.order_by(User.nome).all()
    erro = None
    if request.args.get('erro') == 'vinculos':
        erro = ('Usuário possui registros vinculados (etapas ou OCs) e não pode '
                'ser excluído.')
    return render_template('admin_usuarios.html', usuarios=usuarios, erro=erro)


@bp.route('/admin/usuarios/novo', methods=['GET','POST'])
@login_required
@admin_required
def cadastrar_usuario():
    erro = sucesso = None
    if request.method == 'POST':
        nome     = request.form.get('nome','').strip()
        email    = request.form.get('email','').strip()
        senha    = request.form.get('senha','')
        area     = request.form.get('area','')
        is_admin = request.form.get('is_admin') == 'on'
        if not all([nome, email, senha, area]):
            erro = 'Todos os campos são obrigatórios.'
        elif User.query.filter_by(email=email).first():
            erro = 'E-mail já cadastrado.'
        else:
            db.session.add(User(nome=nome, email=email,
                                senha=generate_password_hash(senha),
                                area=area, is_admin=is_admin))
            db.session.commit()
            sucesso = f'Usuário "{nome}" cadastrado!'
    return render_template('cadastro_usuario.html',
                           areas=AREAS_CADASTRO, erro=erro, sucesso=sucesso)


@bp.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_usuario(id):
    u = User.query.get_or_404(id)
    if u.id != current_user.id:
        # O Postgres aplica as FKs (o SQLite não aplicava): se o usuário já
        # registrou etapas ou excluiu OCs, o delete estoura IntegrityError.
        try:
            db.session.delete(u)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return redirect(url_for('usuarios.listar_usuarios', erro='vinculos'))
    return redirect(url_for('usuarios.listar_usuarios'))
