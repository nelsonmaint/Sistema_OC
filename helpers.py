import os
from datetime import datetime
from functools import wraps
from uuid import uuid4

from flask import abort
from flask_login import current_user
from werkzeug.utils import secure_filename

from models import db, User
from constants import (
    ORDEM_ETAPAS, CLIENTE_LCQ_FINAL, PERMISSOES, EXTENSOES_IMAGEM_PERMITIDAS,
)

base_dir = os.path.abspath(os.path.dirname(__file__))


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
    from models import OrdemCarregamento
    oc = OrdemCarregamento.query.get(oc_id)
    if not oc: return {}
    return {e.codigo_etapa: e.dados for e in oc.etapas}


def _campo_valor(lista, campo):
    for r in lista:
        if r.campo == campo:
            return r.valor or '—'
    return '—'


def _extensao_valida(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES_IMAGEM_PERMITIDAS


def _salvar_upload(arquivo, prefixo, etapa_id):
    """Valida e salva um upload de imagem com nome seguro. Retorna o caminho
    relativo (para gravar em DadosEtapa) ou None se o arquivo for inválido/ausente."""
    if not arquivo or not arquivo.filename or not _extensao_valida(arquivo.filename):
        return None
    nome_seguro = secure_filename(arquivo.filename) or 'imagem'
    nome = f"{prefixo}_{etapa_id}_{uuid4().hex}_{nome_seguro}"
    upload_dir = os.path.join(base_dir, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    arquivo.save(os.path.join(upload_dir, nome))
    return f'static/uploads/{nome}'


def _finalizar(etapa):
    etapa.fim     = datetime.utcnow()
    etapa.duracao = int((etapa.fim - etapa.inicio).total_seconds() / 60)


def _contexto_oc(oc_id):
    from models import OrdemCarregamento
    ctx = {k: '—' for k in ['cliente','produto','transportadora',
                              'tipo_de_frete','codigo_produto',
                              'motorista','placa_carreta','placa_cavalo']}
    oc = OrdemCarregamento.query.get(oc_id)
    if not oc: return ctx
    etapas_dict = {e.codigo_etapa: e for e in oc.etapas}

    e010 = etapas_dict.get('010')
    if e010:
        for campo in ['cliente','produto','transportadora','tipo_de_frete','codigo_produto']:
            ctx[campo] = _campo_valor(e010.dados, campo)
    e040 = etapas_dict.get('040')
    if e040:
        ctx['motorista']     = _campo_valor(e040.dados, 'motorista_nome')
        ctx['placa_carreta'] = _campo_valor(e040.dados, 'placa_carreta')
        ctx['placa_cavalo']  = _campo_valor(e040.dados, 'placa_cavalo')
    return ctx


def _pendencias_usuario():
    from models import OrdemCarregamento
    if current_user.is_admin: return []
    etapas_da_area = PERMISSOES.get(current_user.area, [])
    if not etapas_da_area: return []
    pendentes = []
    adicionadas = set()
    for oc in OrdemCarregamento.query.filter_by(
            status='em_andamento', excluida=False).all():
        etapas_dict = {e.codigo_etapa: e for e in oc.etapas}

        cliente = '—'
        e010 = etapas_dict.get('010')
        if e010:
            cliente = _campo_valor(e010.dados, 'cliente')

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
    from constants import ETAPAS, AREAS

    etapas_dict = {e.codigo_etapa: e for e in oc.etapas}
    e010        = etapas_dict.get('010')

    criador = e010.usuario.nome if (e010 and e010.usuario) else '—'

    cliente = produto = '—'
    if e010:
        cliente = _campo_valor(e010.dados, 'cliente')
        produto = _campo_valor(e010.dados, 'produto')

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


def _etapa_base(id, codigo):
    from models import OrdemCarregamento, EtapaOC
    if not checar_permissao(codigo): abort(403)
    oc    = OrdemCarregamento.query.get_or_404(id)
    etapa = EtapaOC.query.filter_by(oc_id=id, codigo_etapa=codigo, fim=None).first()
    ctx   = _contexto_oc(id)
    return oc, etapa, ctx
