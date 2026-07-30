from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from models import db
from constants import ETAPAS, TEMPO_META, AREAS, ORDEM_ETAPAS, PERMISSOES, LABELS_CAMPOS, LABELS_ASS, CAMPOS_ASSINATURAS, CAMPOS_FOTOS
from helpers import (
    admin_required, checar_permissao, _ordem_efetiva, _buscar_dados_oc,
    _contexto_oc, _montar_item_oc, _pendencias_usuario,
)

OCS_POR_PAGINA = 20

bp = Blueprint('ocs', __name__)


@bp.route('/oc/nova', methods=['GET','POST'])
@login_required
def nova_oc():
    if request.method == 'POST':
        from models import OrdemCarregamento, EtapaOC, DadosEtapa

        nova = None
        for _ in range(5):
            maior     = db.session.query(db.func.max(OrdemCarregamento.id)).scalar() or 0
            numero_oc = f"OC{maior + 1:05d}"
            nova      = OrdemCarregamento(numero_oc=numero_oc, status='em_andamento')
            db.session.add(nova)
            try:
                db.session.commit()
                break
            except IntegrityError:
                db.session.rollback()
                nova = None
        if nova is None:
            abort(500)

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
        return redirect(url_for('ocs.listar_ocs'))
    return render_template('nova_oc.html')


@bp.route('/ocs')
@login_required
def listar_ocs():
    from models import OrdemCarregamento

    status = request.args.get('status', 'todos')
    page   = request.args.get('page', 1, type=int)

    # Admin vê tudo (incluindo excluídas)
    # Usuário comum só vê não-excluídas
    query = OrdemCarregamento.query
    if not current_user.is_admin:
        query = query.filter_by(excluida=False)

    if status == 'em_andamento':
        query = query.filter_by(status='em_andamento', excluida=False)
    elif status == 'concluida':
        query = query.filter_by(status='concluida')
    elif status == 'excluida' and current_user.is_admin:
        query = query.filter_by(excluida=True)

    paginacao = query.order_by(OrdemCarregamento.id.desc())\
                      .paginate(page=page, per_page=OCS_POR_PAGINA, error_out=False)

    lista = [_montar_item_oc(oc) for oc in paginacao.items]
    pendentes_count = len(_pendencias_usuario())

    return render_template('ocs.html',
                           lista=lista,
                           paginacao=paginacao,
                           status_atual=status,
                           pendentes_count=pendentes_count,
                           is_admin=current_user.is_admin)


@bp.route('/oc/<int:id>')
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


@bp.route('/oc/<int:id>/resumo')
@login_required
def resumo_oc(id):
    from models import OrdemCarregamento, EtapaOC

    oc     = OrdemCarregamento.query.get_or_404(id)
    etapas = EtapaOC.query.filter_by(oc_id=id).order_by(EtapaOC.id).all()
    ctx    = _contexto_oc(id)
    dados  = _buscar_dados_oc(id)

    return render_template('resumo_oc.html',
        oc=oc, ctx=ctx, etapas=etapas, dados=dados,
        ETAPAS=ETAPAS, TEMPO_META=TEMPO_META, AREAS=AREAS,
        LABELS_CAMPOS=LABELS_CAMPOS, LABELS_ASS=LABELS_ASS,
        CAMPOS_ASSINATURAS=CAMPOS_ASSINATURAS, CAMPOS_FOTOS=CAMPOS_FOTOS,
        gerado_em=datetime.utcnow())


@bp.route('/oc/<int:id>/editar', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))

    vals = {c: (dados_dict[c].valor if c in dados_dict else '')
            for c in ['pedido_de_venda','tipo_de_frete','cliente',
                      'produto','codigo_produto','transportadora']}
    return render_template('editar_oc.html', oc=oc, vals=vals)


@bp.route('/oc/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_oc(id):
    from models import OrdemCarregamento
    motivo        = request.form.get('motivo_cancelamento','').strip()
    justificativa = request.form.get('justificativa','').strip()
    if not motivo:
        return redirect(url_for('ocs.ver_oc', id=id))
    oc = OrdemCarregamento.query.get_or_404(id)
    oc.excluida               = True
    oc.data_exclusao          = datetime.utcnow()
    oc.motivo_cancelamento    = motivo
    oc.justificativa_exclusao = justificativa or None
    oc.excluida_por           = current_user.id
    db.session.commit()
    return redirect(url_for('ocs.listar_ocs'))
