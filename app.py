import os
import io
import csv
import json
import calendar
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, abort, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

ETAPAS = {
    "010": "Solicitação de Carregamento",
    "020": "PCP",
    "030": "LCQ Inicial",
    "040": "Check-in Portaria",
    "050": "Liberação de Entrada",
    "060": "Checklist de Entrada",
    "070": "Balança Inicial",
    "080": "Checklist de Carregamento",
    "090": "Balança Final",
    "100": "Check-out",
    "110": "LCQ Final",
    "120": "Faturamento"
}

ORDEM_ETAPAS = [
    "010","020","030","050","060",
    "070","080","090","100","110","120"
]

AREAS = {
    "010": "Faturamento",
    "020": "PCP",
    "030": "Laboratório",
    "040": "Portaria",
    "050": "Produção",
    "060": "Portaria",
    "070": "Faturamento",
    "080": "Produção",
    "090": "Faturamento",
    "100": "Portaria",
    "110": "Laboratório",
    "120": "Faturamento"
}

TEMPO_META = {
    "020": 10, "030": 20, "040": 15, "050": 15,
    "060": 10, "070": 8,  "080": 30, "090": 8,
    "100": 10, "110": 20, "120": 15
}

PERMISSOES = {
    "Administrativo": ["010","020","030","040","050","060","070","080","090","100","110","120"],
    "Faturamento":    ["010","070","090","120"],
    "Portaria":       ["040","060","100"],
    "Produção":       ["050","080"],
    "Laboratório":    ["030","110"],
    "PCP":            ["020"]
}

CLIENTE_LCQ_FINAL = 'DA FONTE'   # substring em upper() → "Raymundo da Fonte"

AREAS_CADASTRO = [
    "Administrativo","Faturamento","Portaria",
    "Produção","Laboratório","PCP"
]

CAMPOS_ASSINATURAS = [
    'assinatura_motorista','assinatura_faturamento',
    'assinatura_vigilante','assinatura_operador',
    'assinatura_supervisor_antes','assinatura_supervisor_depois'
]

CAMPOS_FOTOS = [
    'imagem','img_parte_superior','img_nivel',
    'img_domo','img_lacres','img_mangueira_reservatorio','img_valvula'
]

LABELS_CAMPOS = {
    'numero_lote':'Número do Lote','tanque':'Número do Tanque',
    'aprovacao':'Aprovação','motorista_nome':'Nome do Motorista',
    'cliente':'Cliente','transportadora':'Transportadora','produto':'Produto',
    'placa_carreta':'Placa Carreta','placa_cavalo':'Placa Cavalo',
    'aspecto_fisico':'Aspecto Físico','epis_ok':'EPIs Adequados',
    'mope':'Curso MOPE','civ_carreta':'CIV Carreta','civ_cavalo':'CIV Cavalo',
    'cipp':'CIPP','checkin_doc':'Check-in Documental',
    'entrada_liberada':'Entrada Liberada',
    'rotulos_risco':'Rótulos de Risco','painel_seguranca':'Painel de Segurança',
    'pneus':'Pneus','luzes':'Luzes','fios':'Fios','cabine':'Cabine',
    'tanque_combustivel':'Tanque Combustível','motor_arranque':'Motor de Arranque',
    'parachoque':'Para-choque','tanque_carga':'Tanque de Carga',
    'valvulas':'Válvulas','cabo_terra':'Cabo Terra','lacracao':'Lacração',
    'junta':'Junta','fumaca':'Emissão de Fumaça',
    'extintor':'Extintor','cinto':'Cinto','tacografo':'Tacógrafo',
    'kit_seguranca':'Kit de Segurança','aprovado':'Veículo Aprovado',
    'observacoes':'Observações','pesagem_inicial':'Pesagem Inicial (kg)',
    'pesagem_final':'Pesagem Final (kg)','numero_ticket':'Número do Ticket',
    'tanque_adequado':'Tanque Adequado','tanque_limpo':'Tanque Limpo',
    'parafusos_valvulas':'Parafusos/Válvulas','junta_vedacao':'Junta de Vedação',
    'valvula_suspiro':'Válvula do Suspiro','nivel_alinhado':'Nível Alinhado',
    'regua_utilizada':'Régua Utilizada','fechamento_domo':'Fechamento Domo',
    'domo_limpo':'Domo Limpo','lacres_ok':'Lacres OK',
    'mangueira_conectada':'Mangueira Conectada',
    'reservatorio_vazio':'Reservatório Vazio',
    'numero_amostra':'Número da Amostra','numero_lacre':'Número do Lacre',
    'valvula_fechada':'Válvula Fechada','numero_nf':'Número da NF',
    'pedido_de_venda':'Pedido de Venda','tipo_de_frete':'Tipo de Frete',
    'codigo_produto':'Código do Produto','lote':'Nº Lote',
}

LABELS_ASS = {
    'assinatura_motorista':'Motorista','assinatura_faturamento':'Faturamento',
    'assinatura_vigilante':'Vigilante','assinatura_operador':'Operador',
    'assinatura_supervisor_antes':'Supervisor (antes)',
    'assinatura_supervisor_depois':'Supervisor (depois)',
}

# ─────────────────────────────────────────────
# INICIALIZAÇÃO
# ─────────────────────────────────────────────

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'))
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────────────
# DECORADORES
# ─────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def checar_permissao(codigo):
    if not current_user.is_authenticated: return False
    if current_user.is_admin: return True
    return codigo in PERMISSOES.get(current_user.area, [])


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _ordem_efetiva(cliente):
    """Ordem sequencial real: 040 é paralelo (sempre excluído); 110 só para DA FONTE."""
    ordem = list(ORDEM_ETAPAS)
    if CLIENTE_LCQ_FINAL not in (cliente or '').upper():
        ordem = [c for c in ordem if c != '110']
    return ordem


def _buscar_dados_oc(oc_id):
    from models import EtapaOC, DadosEtapa
    etapas = EtapaOC.query.filter_by(oc_id=oc_id).all()
    return {e.codigo_etapa: DadosEtapa.query.filter_by(etapa_id=e.id).all()
            for e in etapas}


def _campo_valor(lista, campo):
    for r in lista:
        if r.campo == campo:
            return r.valor or '—'
    return '—'


def _finalizar(etapa):
    etapa.fim     = datetime.utcnow()
    etapa.duracao = int((etapa.fim - etapa.inicio).total_seconds() / 60)


def _contexto_oc(oc_id):
    from models import EtapaOC, DadosEtapa
    ctx = {k: '—' for k in ['cliente','produto','transportadora',
                              'tipo_de_frete','codigo_produto',
                              'motorista','placa_carreta','placa_cavalo']}
    e010 = EtapaOC.query.filter_by(oc_id=oc_id, codigo_etapa='010').first()
    if e010:
        d = DadosEtapa.query.filter_by(etapa_id=e010.id).all()
        for campo in ['cliente','produto','transportadora','tipo_de_frete','codigo_produto']:
            ctx[campo] = _campo_valor(d, campo)
    e040 = EtapaOC.query.filter_by(oc_id=oc_id, codigo_etapa='040').first()
    if e040:
        d = DadosEtapa.query.filter_by(etapa_id=e040.id).all()
        ctx['motorista']     = _campo_valor(d, 'motorista_nome')
        ctx['placa_carreta'] = _campo_valor(d, 'placa_carreta')
        ctx['placa_cavalo']  = _campo_valor(d, 'placa_cavalo')
    return ctx


def _pendencias_usuario():
    from models import OrdemCarregamento, EtapaOC, DadosEtapa
    if current_user.is_admin: return []
    etapas_da_area = PERMISSOES.get(current_user.area, [])
    if not etapas_da_area: return []
    pendentes = []
    adicionadas = set()
    for oc in OrdemCarregamento.query.filter_by(
            status='em_andamento', excluida=False).all():
        etapas_dict = {e.codigo_etapa: e
                       for e in EtapaOC.query.filter_by(oc_id=oc.id).all()}

        cliente = '—'
        e010 = etapas_dict.get('010')
        if e010:
            d = DadosEtapa.query.filter_by(etapa_id=e010.id, campo='cliente').first()
            if d: cliente = d.valor or '—'

        proxima = next(
            (c for c in _ordem_efetiva(cliente)
             if (c in etapas_dict and etapas_dict[c].fim is None)
             or c not in etapas_dict),
            None
        )
        if proxima and proxima in etapas_da_area and oc.id not in adicionadas:
            pendentes.append(oc)
            adicionadas.add(oc.id)
            continue

        # 040 check-in é paralelo: Portaria vê pendente enquanto não realizado
        if '040' in etapas_da_area and '040' not in etapas_dict and oc.id not in adicionadas:
            pendentes.append(oc)
            adicionadas.add(oc.id)
    return pendentes


def _montar_item_oc(oc):
    """Monta o dict de exibição para um card de OC na listagem."""
    from models import EtapaOC, DadosEtapa
    etapas      = EtapaOC.query.filter_by(oc_id=oc.id).order_by(EtapaOC.id).all()
    etapas_dict = {e.codigo_etapa: e for e in etapas}
    e010        = etapas_dict.get('010')

    criador = '—'
    if e010 and e010.usuario_id:
        u = User.query.get(e010.usuario_id)
        if u: criador = u.nome

    cliente = produto = '—'
    if e010:
        for d in DadosEtapa.query.filter_by(etapa_id=e010.id):
            if d.campo == 'cliente': cliente = d.valor or '—'
            if d.campo == 'produto': produto  = d.valor or '—'

    ordem = _ordem_efetiva(cliente)

    etapa_codigo = etapa_nome = etapa_area = '—'
    for codigo in ordem:
        if codigo in etapas_dict:
            if etapas_dict[codigo].fim is None:
                etapa_codigo = codigo
                etapa_nome   = ETAPAS.get(codigo,'—')
                etapa_area   = AREAS.get(codigo,'—')
                break
        else:
            etapa_codigo = codigo
            etapa_nome   = ETAPAS.get(codigo,'—')
            etapa_area   = AREAS.get(codigo,'—')
            break

    etapas_da_area = PERMISSOES.get(current_user.area, []) \
                     if not current_user.is_admin else list(ORDEM_ETAPAS) + ['040']
    aguardando = (etapa_codigo in etapas_da_area
                  and oc.status == 'em_andamento'
                  and not oc.excluida)

    e040 = etapas_dict.get('040')
    checkin = 'concluido' if (e040 and e040.fim) else ('em_andamento' if e040 else None)

    return {
        'oc': oc, 'criador': criador,
        'cliente': cliente, 'produto': produto,
        'etapa_codigo': etapa_codigo,
        'etapa_nome':   etapa_nome,
        'etapa_area':   etapa_area,
        'aguardando_minha_area': aguardando,
        'checkin': checkin,
    }


# ─────────────────────────────────────────────
# AUTENTICAÇÃO
# ─────────────────────────────────────────────

@app.route('/')
def home():
    return redirect(url_for('acompanhamento'))


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        senha = request.form.get('senha','')
        user  = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha, senha):
            login_user(user)
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro='E-mail ou senha inválidos.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('acompanhamento'))


# ─────────────────────────────────────────────
# USUÁRIOS (admin)
# ─────────────────────────────────────────────

@app.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    usuarios = User.query.order_by(User.nome).all()
    return render_template('admin_usuarios.html', usuarios=usuarios)


@app.route('/admin/usuarios/novo', methods=['GET','POST'])
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


@app.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_usuario(id):
    u = User.query.get_or_404(id)
    if u.id != current_user.id:
        db.session.delete(u)
        db.session.commit()
    return redirect(url_for('listar_usuarios'))


# ─────────────────────────────────────────────
# OCs — LISTAGEM
# ─────────────────────────────────────────────

@app.route('/oc/nova', methods=['GET','POST'])
@login_required
def nova_oc():
    if request.method == 'POST':
        from models import OrdemCarregamento, EtapaOC, DadosEtapa
        total     = OrdemCarregamento.query.count() + 1
        numero_oc = f"OC{total:05d}"
        nova      = OrdemCarregamento(numero_oc=numero_oc, status='em_andamento')
        db.session.add(nova)
        db.session.commit()

        agora = datetime.utcnow()
        etapa = EtapaOC(oc_id=nova.id, codigo_etapa='010',
                        usuario_id=current_user.id,
                        inicio=agora, fim=agora, duracao=0)
        db.session.add(etapa)
        db.session.commit()

        for campo, chave in [
            ('pedido_de_venda','pedido'), ('tipo_de_frete','frete'),
            ('cliente','cliente'),       ('produto','produto'),
            ('codigo_produto','codigo'), ('transportadora','transportadora')
        ]:
            db.session.add(DadosEtapa(etapa_id=etapa.id,
                                       campo=campo,
                                       valor=request.form.get(chave)))
        db.session.commit()
        return redirect(url_for('listar_ocs'))
    return render_template('nova_oc.html')


@app.route('/ocs')
@login_required
def listar_ocs():
    from models import OrdemCarregamento

    # Admin vê tudo (incluindo excluídas)
    # Usuário comum só vê não-excluídas
    if current_user.is_admin:
        ocs = OrdemCarregamento.query.order_by(
                OrdemCarregamento.id.desc()).all()
    else:
        ocs = OrdemCarregamento.query.filter_by(excluida=False)\
                .order_by(OrdemCarregamento.id.desc()).all()

    lista = [_montar_item_oc(oc) for oc in ocs]

    return render_template('ocs.html',
                           lista=lista,
                           is_admin=current_user.is_admin)


# ─────────────────────────────────────────────
# OCs — VER / EDITAR / EXCLUIR
# ─────────────────────────────────────────────

@app.route('/oc/<int:id>')
@login_required
def ver_oc(id):
    from models import OrdemCarregamento, EtapaOC

    oc          = OrdemCarregamento.query.get_or_404(id)
    etapas      = EtapaOC.query.filter_by(oc_id=id).order_by(EtapaOC.id).all()
    etapas_dict = {e.codigo_etapa: e for e in etapas}

    ctx   = _contexto_oc(id)
    ordem = _ordem_efetiva(ctx.get('cliente', '—'))

    proxima = em_andamento = None
    for codigo in ordem:
        if codigo in etapas_dict:
            if etapas_dict[codigo].fim is None:
                em_andamento = etapas_dict[codigo]; break
        else:
            proxima = codigo; break

    # 040 check-in é paralelo
    e040 = etapas_dict.get('040')
    checkin_status       = 'concluido' if (e040 and e040.fim) else ('em_andamento' if e040 else None)
    pode_iniciar_checkin = checar_permissao('040') and not oc.excluida and not e040

    dados      = _buscar_dados_oc(id)
    permitidas = list(ORDEM_ETAPAS) + ['040'] if current_user.is_admin \
                 else PERMISSOES.get(current_user.area, [])

    return render_template('ver_oc.html',
        oc=oc, etapas=etapas, dados=dados,
        proxima=proxima, em_andamento=em_andamento,
        ETAPAS=ETAPAS, TEMPO_META=TEMPO_META,
        AREAS=AREAS, permitidas=permitidas,
        ORDEM_ETAPAS=ordem,
        checkin_status=checkin_status,
        pode_iniciar_checkin=pode_iniciar_checkin,
        checkin_aguarda_050=checkin_status == 'concluido' and proxima == '050')


@app.route('/oc/<int:id>/editar', methods=['GET','POST'])
@login_required
@admin_required
def editar_oc(id):
    from models import OrdemCarregamento, EtapaOC, DadosEtapa

    oc        = OrdemCarregamento.query.get_or_404(id)
    etapa_010 = EtapaOC.query.filter_by(oc_id=id, codigo_etapa='010').first()

    dados_dict = {}
    if etapa_010:
        for d in DadosEtapa.query.filter_by(etapa_id=etapa_010.id):
            dados_dict[d.campo] = d

    if request.method == 'POST':
        for campo in ['pedido_de_venda','tipo_de_frete','cliente',
                      'produto','codigo_produto','transportadora']:
            valor = request.form.get(campo,'').strip()
            if campo in dados_dict:
                dados_dict[campo].valor = valor
            elif etapa_010:
                db.session.add(DadosEtapa(etapa_id=etapa_010.id,
                                           campo=campo, valor=valor))
        db.session.commit()
        return redirect(url_for('ver_oc', id=id))

    vals = {c: (dados_dict[c].valor if c in dados_dict else '')
            for c in ['pedido_de_venda','tipo_de_frete','cliente',
                      'produto','codigo_produto','transportadora']}
    return render_template('editar_oc.html', oc=oc, vals=vals)


@app.route('/oc/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_oc(id):
    from models import OrdemCarregamento
    motivo        = request.form.get('motivo_cancelamento','').strip()
    justificativa = request.form.get('justificativa','').strip()
    if not motivo:
        return redirect(url_for('ver_oc', id=id))
    oc = OrdemCarregamento.query.get_or_404(id)
    oc.excluida               = True
    oc.data_exclusao          = datetime.utcnow()
    oc.motivo_cancelamento    = motivo
    oc.justificativa_exclusao = justificativa or None
    oc.excluida_por           = current_user.id
    db.session.commit()
    return redirect(url_for('listar_ocs'))


# ─────────────────────────────────────────────
# FLUXO DE ETAPAS
# ─────────────────────────────────────────────

@app.route('/oc/<int:id>/iniciar/<codigo>')
@login_required
def iniciar_etapa(id, codigo):
    from models import EtapaOC
    if not checar_permissao(codigo): abort(403)

    # 050 só pode iniciar depois do check-in (040) concluído
    if codigo == '050':
        e040 = EtapaOC.query.filter_by(oc_id=id, codigo_etapa='040').first()
        if not e040 or not e040.fim:
            return redirect(url_for('ver_oc', id=id))

    # 110 somente para cliente DA FONTE
    if codigo == '110':
        ctx = _contexto_oc(id)
        if CLIENTE_LCQ_FINAL not in (ctx.get('cliente', '') or '').upper():
            abort(403)

    etapa = EtapaOC(oc_id=id, codigo_etapa=codigo, usuario_id=current_user.id)
    db.session.add(etapa)
    db.session.commit()
    rotas = {
        '020':'etapa_020','030':'etapa_030','040':'etapa_040',
        '050':'etapa_050','060':'etapa_060','070':'etapa_070',
        '080':'etapa_080','090':'etapa_090','100':'etapa_100',
        '110':'etapa_110','120':'etapa_120',
    }
    if codigo in rotas:
        return redirect(url_for(rotas[codigo], id=id))
    return redirect(url_for('ver_oc', id=id))


def _etapa_base(id, codigo):
    from models import OrdemCarregamento, EtapaOC
    if not checar_permissao(codigo): abort(403)
    oc    = OrdemCarregamento.query.get_or_404(id)
    etapa = EtapaOC.query.filter_by(oc_id=id, codigo_etapa=codigo, fim=None).first()
    ctx   = _contexto_oc(id)
    return oc, etapa, ctx


# ─────────────────────────────────────────────
# FORMULÁRIOS DAS ETAPAS
# ─────────────────────────────────────────────

@app.route('/oc/<int:id>/formulario/020', methods=['GET','POST'])
@login_required
def etapa_020(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '020')
    if not etapa: return "Erro: etapa 020 não encontrada."
    if request.method == 'POST':
        lote = request.form.get('lote','').strip()
        if not lote:
            return render_template('etapa_020.html', oc=oc, ctx=ctx,
                                   mensagem='Lote obrigatório.')
        db.session.add(DadosEtapa(etapa_id=etapa.id, campo='numero_lote', valor=lote))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_020.html', oc=oc, ctx=ctx)


@app.route('/oc/<int:id>/formulario/030', methods=['GET','POST'])
@login_required
def etapa_030(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '030')
    if not etapa: return "Erro: etapa 030 não encontrada."
    mensagem = None
    if request.method == 'POST':
        tanque    = request.form.get('tanque','').strip()
        aprovacao = request.form.get('aprovacao','')
        if not tanque or not aprovacao:
            mensagem = 'Preencha todos os campos.'
            return render_template('etapa_030.html', oc=oc, ctx=ctx, mensagem=mensagem)
        db.session.add(DadosEtapa(etapa_id=etapa.id, campo='tanque',    valor=tanque))
        db.session.add(DadosEtapa(etapa_id=etapa.id, campo='aprovacao', valor=aprovacao))
        if aprovacao == 'SIM':
            _finalizar(etapa); db.session.commit()
            return redirect(url_for('ver_oc', id=id))
        db.session.commit()
        mensagem = 'Carga bloqueada.' if aprovacao == 'NAO' else 'Etapa em análise.'
    return render_template('etapa_030.html', oc=oc, ctx=ctx, mensagem=mensagem)


@app.route('/oc/<int:id>/formulario/040', methods=['GET','POST'])
@login_required
def etapa_040(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '040')
    if not etapa: return "Erro: etapa 040 não encontrada."
    if request.method == 'POST':
        for campo in ['motorista_nome','cliente','transportadora','produto',
                      'placa_carreta','placa_cavalo','aspecto_fisico','epis_ok',
                      'mope','civ_carreta','civ_cavalo','cipp','checkin_doc',
                      'assinatura_motorista','assinatura_faturamento']:
            db.session.add(DadosEtapa(etapa_id=etapa.id, campo=campo,
                                       valor=request.form.get(campo,'')))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_040.html', oc=oc, ctx=ctx)


@app.route('/oc/<int:id>/formulario/050', methods=['GET','POST'])
@login_required
def etapa_050(id):
    from models import EtapaOC, DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '050')
    if not etapa: return "Erro: etapa 050 não encontrada."
    if request.method == 'POST':
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='entrada_liberada', valor='SIM'))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    dados = {}
    for e in EtapaOC.query.filter_by(oc_id=id).all():
        for r in DadosEtapa.query.filter_by(etapa_id=e.id).all():
            dados[r.campo] = r.valor
    return render_template('etapa_050.html', oc=oc, ctx=ctx, dados=dados)


@app.route('/oc/<int:id>/formulario/060', methods=['GET','POST'])
@login_required
def etapa_060(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '060')
    if not etapa: return "Erro: etapa 060 não encontrada."
    if request.method == 'POST':
        tem_nao = any(v == 'NÃO' for v in request.form.values())
        if tem_nao and not request.form.get('observacoes','').strip():
            return render_template('etapa_060.html', oc=oc, ctx=ctx,
                                   mensagem='Preencha observações quando houver NÃO.')
        for campo, valor in request.form.to_dict().items():
            db.session.add(DadosEtapa(etapa_id=etapa.id, campo=campo, valor=valor))
        upload_dir = os.path.join(base_dir,'static','uploads')
        os.makedirs(upload_dir, exist_ok=True)
        for arq in request.files.getlist('imagens'):
            if arq.filename:
                nome = f"060_{etapa.id}_{arq.filename}"
                arq.save(os.path.join(upload_dir, nome))
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo='imagem',
                                           valor=f'static/uploads/{nome}'))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_060.html', oc=oc, ctx=ctx, mensagem=None)


@app.route('/oc/<int:id>/formulario/070', methods=['GET','POST'])
@login_required
def etapa_070(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '070')
    if not etapa: return "Erro: etapa 070 não encontrada."
    if request.method == 'POST':
        pesagem = request.form.get('pesagem','').strip()
        if not pesagem:
            return render_template('etapa_070.html', oc=oc, ctx=ctx,
                                   mensagem='Pesagem obrigatória.')
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='pesagem_inicial', valor=pesagem))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_070.html', oc=oc, ctx=ctx, mensagem=None)


@app.route('/oc/<int:id>/formulario/080', methods=['GET','POST'])
@login_required
def etapa_080(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '080')
    if not etapa: return "Erro: etapa 080 não encontrada."
    if request.method == 'POST':
        upload_dir = os.path.join(base_dir,'static','uploads')
        os.makedirs(upload_dir, exist_ok=True)
        for campo in ['tanque_adequado','tanque_limpo','parafusos_valvulas',
                      'junta_vedacao','valvula_suspiro','nivel_alinhado',
                      'regua_utilizada','fechamento_domo','domo_limpo','lacres_ok',
                      'mangueira_conectada','reservatorio_vazio',
                      'numero_amostra','numero_lacre','assinatura_operador',
                      'assinatura_supervisor_antes','assinatura_supervisor_depois']:
            valor = request.form.get(campo)
            if valor:
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo=campo, valor=valor))
        for campo in ['img_parte_superior','img_nivel','img_domo',
                      'img_mangueira_reservatorio']:
            arq = request.files.get(campo)
            if arq and arq.filename:
                nome = f"{campo}_{etapa.id}_{arq.filename}"
                arq.save(os.path.join(upload_dir, nome))
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo=campo,
                                           valor=f'static/uploads/{nome}'))
        for arq in request.files.getlist('img_lacres'):
            if arq and arq.filename:
                nome = f"img_lacres_{etapa.id}_{arq.filename}"
                arq.save(os.path.join(upload_dir, nome))
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo='img_lacres',
                                           valor=f'static/uploads/{nome}'))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_080.html', oc=oc, ctx=ctx)


@app.route('/oc/<int:id>/formulario/090', methods=['GET','POST'])
@login_required
def etapa_090(id):
    from models import EtapaOC, DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '090')
    if not etapa: return "Erro: etapa 090 não encontrada."
    pesagem_inicial = None
    e070 = EtapaOC.query.filter_by(oc_id=id, codigo_etapa='070').first()
    if e070:
        d = DadosEtapa.query.filter_by(etapa_id=e070.id,
                                        campo='pesagem_inicial').first()
        if d: pesagem_inicial = d.valor
    if request.method == 'POST':
        pesagem = request.form.get('pesagem','').strip()
        ticket  = request.form.get('numero_ticket','').strip()
        if not pesagem or not ticket:
            return render_template('etapa_090.html', oc=oc, ctx=ctx,
                                   mensagem='Preencha todos os campos.',
                                   pesagem_inicial=pesagem_inicial)
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='pesagem_final', valor=pesagem))
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='numero_ticket', valor=ticket))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_090.html', oc=oc, ctx=ctx,
                           mensagem=None, pesagem_inicial=pesagem_inicial)


@app.route('/oc/<int:id>/formulario/100', methods=['GET','POST'])
@login_required
def etapa_100(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '100')
    if not etapa: return "Erro: etapa 100 não encontrada."
    if request.method == 'POST':
        valvula    = request.form.get('valvula_fechada','')
        assinatura = request.form.get('assinatura_vigilante','')
        if not valvula or not assinatura:
            return render_template('etapa_100.html', oc=oc, ctx=ctx,
                                   mensagem='Preencha todos os campos e assine.')
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='valvula_fechada', valor=valvula))
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='assinatura_vigilante', valor=assinatura))
        upload_dir = os.path.join(base_dir,'static','uploads')
        os.makedirs(upload_dir, exist_ok=True)
        arq = request.files.get('img_valvula')
        if arq and arq.filename:
            nome = f"valvula_{etapa.id}_{arq.filename}"
            arq.save(os.path.join(upload_dir, nome))
            db.session.add(DadosEtapa(etapa_id=etapa.id, campo='img_valvula',
                                       valor=f'static/uploads/{nome}'))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_100.html', oc=oc, ctx=ctx, mensagem=None)


@app.route('/oc/<int:id>/formulario/110', methods=['GET','POST'])
@login_required
def etapa_110(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '110')
    if not etapa: return "Erro: etapa 110 não encontrada."
    if CLIENTE_LCQ_FINAL not in (ctx.get('cliente', '') or '').upper():
        abort(403)
    if request.method == 'POST':
        lote      = request.form.get('lote','').strip()
        aprovacao = request.form.get('aprovacao','')
        if not lote or not aprovacao:
            return render_template('etapa_110.html', oc=oc, ctx=ctx,
                                   mensagem='Preencha todos os campos.')
        db.session.add(DadosEtapa(etapa_id=etapa.id, campo='lote',      valor=lote))
        db.session.add(DadosEtapa(etapa_id=etapa.id, campo='aprovacao', valor=aprovacao))
        if aprovacao == 'NAO':
            db.session.commit()
            return render_template('etapa_110.html', oc=oc, ctx=ctx,
                mensagem='Aprovação NÃO — etapa bloqueada.')
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_110.html', oc=oc, ctx=ctx, mensagem=None)


@app.route('/oc/<int:id>/formulario/120', methods=['GET','POST'])
@login_required
def etapa_120(id):
    from models import OrdemCarregamento, DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '120')
    if not etapa: return "Erro: etapa 120 não encontrada."
    if request.method == 'POST':
        numero_nf = request.form.get('numero_nf','').strip()
        if not numero_nf:
            return render_template('etapa_120.html', oc=oc, ctx=ctx,
                                   mensagem='NF obrigatória.')
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='numero_nf', valor=numero_nf))
        _finalizar(etapa)
        oc.status = 'concluida'
        db.session.commit()
        return redirect(url_for('ver_oc', id=id))
    return render_template('etapa_120.html', oc=oc, ctx=ctx, mensagem=None)


# ─────────────────────────────────────────────
# ACOMPANHAMENTO EM TEMPO REAL
# ─────────────────────────────────────────────

@app.route('/acompanhamento')
@login_required
def acompanhamento():
    from models import OrdemCarregamento, EtapaOC, DadosEtapa

    ocs_abertas = OrdemCarregamento.query\
                    .filter_by(status='em_andamento', excluida=False)\
                    .order_by(OrdemCarregamento.id).all()
    ocs_data = []

    for oc in ocs_abertas:
        etapas      = EtapaOC.query.filter_by(oc_id=oc.id).order_by(EtapaOC.id).all()
        etapas_dict = {e.codigo_etapa: e for e in etapas}
        e010 = etapas_dict.get('010')

        cliente = transportadora = produto = '—'
        if e010:
            for d in DadosEtapa.query.filter_by(etapa_id=e010.id):
                if d.campo == 'cliente':        cliente        = d.valor or '—'
                if d.campo == 'produto':        produto        = d.valor or '—'
                if d.campo == 'transportadora': transportadora = d.valor or '—'

        # 040 check-in paralelo
        e040 = etapas_dict.get('040')
        placa_carreta = '—'
        if e040:
            d = DadosEtapa.query.filter_by(etapa_id=e040.id,
                                            campo='placa_carreta').first()
            if d: placa_carreta = d.valor or '—'

        checkin_ts = None
        checkin_espera_fixa = None
        if e040 and e040.fim:
            checkin_ts = calendar.timegm(e040.fim.timetuple())
            e050 = etapas_dict.get('050')
            if e050 and e050.inicio:
                checkin_espera_fixa = int(
                    max(0, (e050.inicio - e040.fim).total_seconds() / 60))

        # Timer 1: Check-in (040.fim) → Checklist de Entrada (060.fim)
        e060 = etapas_dict.get('060')
        w1_from = calendar.timegm(e040.fim.timetuple()) if (e040 and e040.fim) else None
        w1_to   = calendar.timegm(e060.fim.timetuple()) if (e060 and e060.fim) else None

        # Timer 2: Checklist de Entrada (060.fim) → início do Carregamento (080.inicio)
        e080 = etapas_dict.get('080')
        w2_from = calendar.timegm(e060.fim.timetuple()) if (e060 and e060.fim) else None
        w2_to   = calendar.timegm(e080.inicio.timetuple()) if (e080 and e080.inicio) else None

        # Fluxo sequencial (sem 040)
        ordem = _ordem_efetiva(cliente)
        etapa_codigo = etapa_nome = etapa_area = '—'
        etapa_inicio_ts = calendar.timegm(oc.data_criacao.timetuple())
        ultimo_fim_ts   = etapa_inicio_ts

        for codigo in ordem:
            if codigo in etapas_dict:
                e = etapas_dict[codigo]
                if e.fim is None:
                    etapa_codigo    = codigo
                    etapa_nome      = ETAPAS.get(codigo,'—')
                    etapa_area      = AREAS.get(codigo,'—')
                    etapa_inicio_ts = calendar.timegm(e.inicio.timetuple())
                    break
                if e.fim:
                    ultimo_fim_ts = calendar.timegm(e.fim.timetuple())
            else:
                etapa_codigo    = codigo
                etapa_nome      = ETAPAS.get(codigo,'—')
                etapa_area      = AREAS.get(codigo,'—')
                etapa_inicio_ts = ultimo_fim_ts
                break

        ocs_data.append({
            'id': oc.id, 'numero_oc': oc.numero_oc,
            'cliente': cliente, 'produto': produto,
            'transportadora': transportadora, 'placa_carreta': placa_carreta,
            'etapa_codigo': etapa_codigo, 'etapa_nome': etapa_nome,
            'etapa_area': etapa_area,
            'criacao_ts':           calendar.timegm(oc.data_criacao.timetuple()),
            'etapa_inicio_ts':      etapa_inicio_ts,
            'checkin_ts':           checkin_ts,
            'checkin_espera_fixa':  checkin_espera_fixa,
            'w1_from_ts':           w1_from,
            'w1_to_ts':             w1_to,
            'w2_from_ts':           w2_from,
            'w2_to_ts':             w2_to,
        })

    return render_template('acompanhamento.html',
                           ocs_json=json.dumps(ocs_data),
                           meta_json=json.dumps(TEMPO_META))


# ─────────────────────────────────────────────
# DASHBOARD GERENCIAL
# ─────────────────────────────────────────────

@app.route('/dashboard/gerencial')
@login_required
def dashboard_gerencial():
    from models import OrdemCarregamento, EtapaOC, DadosEtapa

    data_ini_str = request.args.get('data_ini','')
    data_fim_str = request.args.get('data_fim','')

    # Inclui TODAS as OCs (inclusive excluídas) para visão completa da programação
    query = OrdemCarregamento.query
    if data_ini_str:
        try:
            query = query.filter(OrdemCarregamento.data_criacao >=
                                 datetime.strptime(data_ini_str,'%Y-%m-%d'))
        except ValueError: pass
    if data_fim_str:
        try:
            df = datetime.strptime(data_fim_str,'%Y-%m-%d').replace(hour=23,minute=59,second=59)
            query = query.filter(OrdemCarregamento.data_criacao <= df)
        except ValueError: pass

    ocs = query.order_by(OrdemCarregamento.id.desc()).all()

    MOTIVOS = {
        'NAO_COMPARECEU': 'Não Compareceu',
        'ALTERACAO_PROG': 'Alteração de Programação',
        'CANCELAMENTO':   'Cancelamento Operacional',
        'OUTRO':          'Outro',
    }

    def dur_e(etapas_dict, codigo):
        e = etapas_dict.get(codigo)
        return e.duracao if e and e.duracao else 0

    def avg_hm(lst):
        if not lst: return '—'
        avg = sum(lst) / len(lst)
        return f"{int(avg//60)}:{int(avg%60):02d}"

    tabela = []; detalhes = {}
    por_produto = {}
    tempo_por_etapa = {c: [] for c in ORDEM_ETAPAS}
    tempos_fase = {'criacao_lote':[], 'entrada':[], 'carregamento':[], 'laboratorio':[], 'faturamento':[]}
    kpis_count  = {'faturada':0, 'em_andamento':0, 'nao_compareceu':0, 'alteracao_prog':0, 'cancelamento':0}
    tempo_max_ref = sum(TEMPO_META.values())

    for oc in ocs:
        etapas      = EtapaOC.query.filter_by(oc_id=oc.id).order_by(EtapaOC.id).all()
        etapas_dict = {e.codigo_etapa: e for e in etapas}
        e010 = etapas_dict.get('010')

        cliente = produto = transportadora = '—'
        if e010:
            for d in DadosEtapa.query.filter_by(etapa_id=e010.id):
                if d.campo == 'cliente':        cliente        = d.valor or '—'
                if d.campo == 'produto':        produto        = d.valor or '—'
                if d.campo == 'transportadora': transportadora = d.valor or '—'

        # Volume (t) = (pesagem_final - pesagem_inicial) / 1000
        volume = None
        e070 = etapas_dict.get('070')
        e090 = etapas_dict.get('090')
        if e070 and e090:
            d070 = DadosEtapa.query.filter_by(etapa_id=e070.id, campo='pesagem_inicial').first()
            d090 = DadosEtapa.query.filter_by(etapa_id=e090.id, campo='pesagem_final').first()
            if d070 and d090:
                try:
                    vol_kg = float(d090.valor) - float(d070.valor)
                    if vol_kg > 0: volume = round(vol_kg / 1000, 1)
                except (ValueError, TypeError): pass

        # Status
        if oc.excluida:
            motivo_k = (oc.motivo_cancelamento or 'OUTRO').upper()
            status_display = MOTIVOS.get(motivo_k, 'Cancelada')
            if motivo_k == 'NAO_COMPARECEU':  kpis_count['nao_compareceu'] += 1
            elif motivo_k == 'ALTERACAO_PROG': kpis_count['alteracao_prog'] += 1
            else:                              kpis_count['cancelamento']   += 1
        elif oc.status == 'concluida':
            status_display = 'Faturada'; kpis_count['faturada'] += 1
        else:
            status_display = 'Em Andamento'; kpis_count['em_andamento'] += 1

        ordem_oc = _ordem_efetiva(cliente)
        etapa_codigo = etapa_nome = '—'
        for codigo in ordem_oc:
            if codigo in etapas_dict:
                if etapas_dict[codigo].fim is None:
                    etapa_codigo = codigo; etapa_nome = ETAPAS.get(codigo,'—'); break
            else:
                etapa_codigo = codigo; etapa_nome = ETAPAS.get(codigo,'—'); break

        total_min = 0; etapas_detalhe = []
        for codigo in ordem_oc:
            e    = etapas_dict.get(codigo)
            dur  = e.duracao if e and e.duracao is not None else None
            regs = DadosEtapa.query.filter_by(etapa_id=e.id).all() if e else []
            if dur is not None:
                total_min += dur
                if codigo in tempo_por_etapa: tempo_por_etapa[codigo].append(dur)
            etapas_detalhe.append({
                'codigo': codigo, 'nome': ETAPAS.get(codigo,''), 'duracao': dur,
                'dados': [{'campo': r.campo, 'valor': r.valor} for r in regs]
            })

        # Tempos por fase (só faturadas)
        if oc.status == 'concluida':
            clt = dur_e(etapas_dict,'020')
            if clt: tempos_fase['criacao_lote'].append(clt)
            ent = dur_e(etapas_dict,'040') + dur_e(etapas_dict,'050') + dur_e(etapas_dict,'060')
            if ent: tempos_fase['entrada'].append(ent)
            car = dur_e(etapas_dict,'080')
            if car: tempos_fase['carregamento'].append(car)
            lab = dur_e(etapas_dict,'030') + dur_e(etapas_dict,'110')
            if lab: tempos_fase['laboratorio'].append(lab)
            fat = dur_e(etapas_dict,'120')
            if fat: tempos_fase['faturamento'].append(fat)

        # Acumula por produto
        if produto not in por_produto:
            por_produto[produto] = {'count':0, 'volume':0.0, 'tempos':[]}
        por_produto[produto]['count'] += 1
        if volume: por_produto[produto]['volume'] += volume
        if total_min: por_produto[produto]['tempos'].append(total_min)

        status_t = 'na' if total_min==0 else ('critico' if total_min>tempo_max_ref else 'ok')
        pct = round((total_min/tempo_max_ref)*100) if total_min else 0

        tabela.append({
            'oc': oc, 'cliente': cliente, 'produto': produto,
            'transportadora': transportadora, 'volume': volume,
            'etapa_codigo': etapa_codigo, 'etapa_nome': etapa_nome,
            'tempo_total': total_min or None, 'tempo_total_status': status_t,
            'tempo_pct': pct, 'tempo_max': tempo_max_ref,
            'status_display': status_display,
        })
        detalhes[oc.id] = {
            'numero_oc': oc.numero_oc, 'cliente': cliente, 'produto': produto,
            'transportadora': transportadora,
            'data_criacao': oc.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'status': oc.status, 'etapas': etapas_detalhe,
        }

    total_ocs = len(ocs)
    kpis = {
        'total':           total_ocs,
        'faturada':        kpis_count['faturada'],
        'em_andamento':    kpis_count['em_andamento'],
        'nao_compareceu':  kpis_count['nao_compareceu'],
        'alteracao_prog':  kpis_count['alteracao_prog'],
        'cancelamento':    kpis_count['cancelamento'],
    }

    tempos_medios = {
        'criacao_lote': avg_hm(tempos_fase['criacao_lote']),
        'entrada':      avg_hm(tempos_fase['entrada']),
        'carregamento': avg_hm(tempos_fase['carregamento']),
        'laboratorio':  avg_hm(tempos_fase['laboratorio']),
        'faturamento':  avg_hm(tempos_fase['faturamento']),
    }

    tabela_produto = sorted([
        {'produto': p, 'count': d['count'],
         'volume': round(d['volume'],1), 'tempo_medio': avg_hm(d['tempos'])}
        for p, d in por_produto.items()
    ], key=lambda x: x['count'], reverse=True)

    labels_g = [c for c in ORDEM_ETAPAS if c != '010']
    grafico = {
        'etapas': [ETAPAS.get(c, c) for c in labels_g],
        'medias': [round(sum(tempo_por_etapa[c])/len(tempo_por_etapa[c]),1)
                   if tempo_por_etapa[c] else 0 for c in labels_g],
        'metas':  [TEMPO_META.get(c) for c in labels_g],
    }

    return render_template('dashboard_gerencial.html',
        kpis=kpis, tabela=tabela,
        tabela_produto=tabela_produto, tempos_medios=tempos_medios,
        grafico_json=json.dumps(grafico), detalhes_json=json.dumps(detalhes),
        meta_json=json.dumps(TEMPO_META), etapas_json=json.dumps(ETAPAS),
        labels_campos_json=json.dumps(LABELS_CAMPOS),
        labels_ass_json=json.dumps(LABELS_ASS),
        campos_ass_json=json.dumps(CAMPOS_ASSINATURAS),
        campos_fotos_json=json.dumps(CAMPOS_FOTOS),
        data_ini=data_ini_str, data_fim=data_fim_str,
    )


# ─────────────────────────────────────────────
# EXPORTAÇÃO CSV
# ─────────────────────────────────────────────

@app.route('/dashboard/gerencial/exportar')
@login_required
def exportar_csv():
    from models import OrdemCarregamento, EtapaOC, DadosEtapa

    data_ini_str = request.args.get('data_ini','')
    data_fim_str = request.args.get('data_fim','')

    query = OrdemCarregamento.query
    if data_ini_str:
        try:
            query = query.filter(OrdemCarregamento.data_criacao >=
                                 datetime.strptime(data_ini_str,'%Y-%m-%d'))
        except ValueError: pass
    if data_fim_str:
        try:
            df = datetime.strptime(data_fim_str,'%Y-%m-%d').replace(hour=23,minute=59,second=59)
            query = query.filter(OrdemCarregamento.data_criacao <= df)
        except ValueError: pass

    ocs = query.order_by(OrdemCarregamento.id).all()

    MOTIVOS = {
        'NAO_COMPARECEU': 'Não Compareceu',
        'ALTERACAO_PROG': 'Alteração de Programação',
        'CANCELAMENTO':   'Cancelamento Operacional',
        'OUTRO':          'Outro',
    }

    buf = io.StringIO()
    w   = csv.writer(buf, delimiter=';')

    w.writerow([
        'Número OC', 'Data Criação', 'Status', 'Motivo Cancelamento',
        'Produto', 'Cliente', 'Transportadora',
        'Placa Carreta', 'Placa Cavalo', 'Motorista',
        'Pesagem Inicial (kg)', 'Pesagem Final (kg)', 'Volume (t)',
        'Número NF', 'Número Ticket',
        'PCP (020) min',
        'LCQ Inicial (030) min',
        'Check-in (040) min',
        'Espera Entrada 040→050 min',
        'Liberação Entrada (050) min',
        'Checklist Entrada (060) min',
        'Balança Inicial (070) min',
        'Checklist Carga (080) min',
        'Balança Final (090) min',
        'Check-out (100) min',
        'LCQ Final (110) min',
        'Faturamento (120) min',
        'Fase Entrada (040+050+060) min',
        'Fase Carregamento (080) min',
        'Fase Laboratório (030+110) min',
        'Fase Faturamento (120) min',
        'Tempo Total min',
    ])

    for oc in ocs:
        etapas      = EtapaOC.query.filter_by(oc_id=oc.id).order_by(EtapaOC.id).all()
        etapas_dict = {e.codigo_etapa: e for e in etapas}

        # Achata todos os dados em um único dict (último valor vence para campos repetidos)
        dados = {}
        for e in etapas:
            for d in DadosEtapa.query.filter_by(etapa_id=e.id).all():
                dados[d.campo] = d.valor or ''

        def dur(c):
            e = etapas_dict.get(c)
            return e.duracao if e and e.duracao is not None else ''

        def dur_int(c):
            e = etapas_dict.get(c)
            return e.duracao if e and e.duracao else 0

        def val(c):
            return dados.get(c, '')

        # Status
        if oc.excluida:
            mk = (oc.motivo_cancelamento or 'OUTRO').upper()
            status = MOTIVOS.get(mk, 'Cancelada')
            motivo = status
        elif oc.status == 'concluida':
            status, motivo = 'Faturada', ''
        else:
            status, motivo = 'Em Andamento', ''

        # Volume em toneladas
        volume = ''
        try:
            pi = float(dados.get('pesagem_inicial','') or 0)
            pf = float(dados.get('pesagem_final','')   or 0)
            if pf > pi: volume = round((pf - pi) / 1000, 1)
        except (ValueError, TypeError): pass

        # Espera entrada: intervalo entre fim do check-in (040) e início da liberação (050)
        espera_entrada = ''
        e040 = etapas_dict.get('040')
        e050 = etapas_dict.get('050')
        if e040 and e040.fim and e050 and e050.inicio:
            diff = (e050.inicio - e040.fim).total_seconds() / 60
            if diff >= 0: espera_entrada = round(diff, 1)

        # Fases agregadas
        fase_entrada      = dur_int('040') + dur_int('050') + dur_int('060') or ''
        fase_carregamento = dur_int('080') or ''
        fase_laboratorio  = dur_int('030') + dur_int('110') or ''
        fase_faturamento  = dur_int('120') or ''
        total_min         = sum(dur_int(c) for c in _ordem_efetiva(val('cliente'))) or ''

        w.writerow([
            oc.numero_oc,
            oc.data_criacao.strftime('%d/%m/%Y %H:%M'),
            status, motivo,
            val('produto'), val('cliente'), val('transportadora'),
            val('placa_carreta'), val('placa_cavalo'), val('motorista_nome'),
            val('pesagem_inicial'), val('pesagem_final'), volume,
            val('numero_nf'), val('numero_ticket'),
            dur('020'), dur('030'), dur('040'), espera_entrada,
            dur('050'), dur('060'), dur('070'), dur('080'),
            dur('090'), dur('100'), dur('110'), dur('120'),
            fase_entrada, fase_carregamento, fase_laboratorio, fase_faturamento,
            total_min,
        ])

    nome = 'relatorio_ocs'
    if data_ini_str: nome += f'_{data_ini_str}'
    if data_fim_str: nome += f'_a_{data_fim_str}'
    nome += '.csv'

    # BOM UTF-8 (﻿) para o Excel abrir com acentuação correta
    return Response(
        '﻿' + buf.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'}
    )


# ─────────────────────────────────────────────
# ERROS
# ─────────────────────────────────────────────

@app.errorhandler(403)
def acesso_negado(e):
    return render_template('403.html'), 403


if __name__ == '__main__':
    app.run(debug=True)
