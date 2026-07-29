from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id       = db.Column(db.Integer, primary_key=True)
    nome     = db.Column(db.String(100), nullable=False)
    email    = db.Column(db.String(100), unique=True, nullable=False)
    senha    = db.Column(db.String(200), nullable=False)
    area     = db.Column(db.String(50))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


class OrdemCarregamento(db.Model):
    id                    = db.Column(db.Integer, primary_key=True)
    numero_oc             = db.Column(db.String(50))
    status                = db.Column(db.String(20), default='em_andamento')
    data_criacao          = db.Column(db.DateTime, default=datetime.utcnow)
    # Exclusão suave
    excluida              = db.Column(db.Boolean, default=False, nullable=False)
    data_exclusao         = db.Column(db.DateTime, nullable=True)
    motivo_cancelamento   = db.Column(db.String(30), nullable=True)
    justificativa_exclusao = db.Column(db.Text, nullable=True)
    excluida_por          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class EtapaOC(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    oc_id        = db.Column(db.Integer, db.ForeignKey('ordem_carregamento.id'))
    codigo_etapa = db.Column(db.String(10))
    inicio       = db.Column(db.DateTime, default=datetime.utcnow)
    fim          = db.Column(db.DateTime)
    duracao      = db.Column(db.Integer)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('user.id'))


class DadosEtapa(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    etapa_id = db.Column(db.Integer, db.ForeignKey('etapa_oc.id'))
    campo    = db.Column(db.String(100))
    valor    = db.Column(db.Text)
