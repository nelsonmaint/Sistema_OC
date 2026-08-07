from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from models import db
from constants import CLIENTE_LCQ_FINAL
from helpers import checar_permissao, _contexto_oc, _finalizar, _salvar_upload, _etapa_base

bp = Blueprint('etapas', __name__)


@bp.route('/oc/<int:id>/iniciar/<codigo>')
@login_required
def iniciar_etapa(id, codigo):
    from models import EtapaOC
    if not checar_permissao(codigo): abort(403)

    rotas = {
        '020':'etapas.etapa_020','030':'etapas.etapa_030','040':'etapas.etapa_040',
        '050':'etapas.etapa_050','060':'etapas.etapa_060','070':'etapas.etapa_070',
        '080':'etapas.etapa_080','090':'etapas.etapa_090','100':'etapas.etapa_100',
        '110':'etapas.etapa_110','120':'etapas.etapa_120',
    }

    # Idempotência: clique duplo, F5 ou duas abas na mesma OC não podem criar
    # uma segunda linha para a mesma etapa (foi o que duplicou a etapa 060
    # na OC00002). Se já existe, reaproveita em vez de criar outra.
    etapa_existente = EtapaOC.query.filter_by(oc_id=id, codigo_etapa=codigo).first()
    if etapa_existente:
        if etapa_existente.fim is None and codigo in rotas:
            return redirect(url_for(rotas[codigo], id=id))
        return redirect(url_for('ocs.ver_oc', id=id))

    # 050 só pode iniciar depois do check-in (040) concluído
    if codigo == '050':
        e040 = EtapaOC.query.filter_by(oc_id=id, codigo_etapa='040').first()
        if not e040 or not e040.fim:
            return redirect(url_for('ocs.ver_oc', id=id))

    # 110 somente para cliente DA FONTE
    if codigo == '110':
        ctx = _contexto_oc(id)
        if CLIENTE_LCQ_FINAL not in (ctx.get('cliente', '') or '').upper():
            abort(403)

    etapa = EtapaOC(oc_id=id, codigo_etapa=codigo, usuario_id=current_user.id)
    db.session.add(etapa)
    db.session.commit()
    if codigo in rotas:
        return redirect(url_for(rotas[codigo], id=id))
    return redirect(url_for('ocs.ver_oc', id=id))


@bp.route('/oc/<int:id>/formulario/020', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_020.html', oc=oc, ctx=ctx)


@bp.route('/oc/<int:id>/formulario/030', methods=['GET','POST'])
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
            return redirect(url_for('ocs.ver_oc', id=id))
        db.session.commit()
        mensagem = 'Carga bloqueada.' if aprovacao == 'NAO' else 'Etapa em análise.'
    return render_template('etapa_030.html', oc=oc, ctx=ctx, mensagem=mensagem)


@bp.route('/oc/<int:id>/formulario/040', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_040.html', oc=oc, ctx=ctx)


@bp.route('/oc/<int:id>/formulario/050', methods=['GET','POST'])
@login_required
def etapa_050(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '050')
    if not etapa: return "Erro: etapa 050 não encontrada."
    if request.method == 'POST':
        db.session.add(DadosEtapa(etapa_id=etapa.id,
                                   campo='entrada_liberada', valor='SIM'))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ocs.ver_oc', id=id))
    dados = {}
    for e in oc.etapas:
        for r in e.dados:
            dados[r.campo] = r.valor
    return render_template('etapa_050.html', oc=oc, ctx=ctx, dados=dados)


@bp.route('/oc/<int:id>/formulario/060', methods=['GET','POST'])
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
        for arq in request.files.getlist('imagens'):
            caminho = _salvar_upload(arq, '060', etapa.id)
            if caminho:
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo='imagem', valor=caminho))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_060.html', oc=oc, ctx=ctx, mensagem=None)


@bp.route('/oc/<int:id>/formulario/070', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_070.html', oc=oc, ctx=ctx, mensagem=None)


@bp.route('/oc/<int:id>/formulario/080', methods=['GET','POST'])
@login_required
def etapa_080(id):
    from models import DadosEtapa
    oc, etapa, ctx = _etapa_base(id, '080')
    if not etapa: return "Erro: etapa 080 não encontrada."
    if request.method == 'POST':
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
            caminho = _salvar_upload(request.files.get(campo), campo, etapa.id)
            if caminho:
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo=campo, valor=caminho))
        for arq in request.files.getlist('img_lacres'):
            caminho = _salvar_upload(arq, 'img_lacres', etapa.id)
            if caminho:
                db.session.add(DadosEtapa(etapa_id=etapa.id, campo='img_lacres', valor=caminho))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_080.html', oc=oc, ctx=ctx)


@bp.route('/oc/<int:id>/formulario/090', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_090.html', oc=oc, ctx=ctx,
                           mensagem=None, pesagem_inicial=pesagem_inicial)


@bp.route('/oc/<int:id>/formulario/100', methods=['GET','POST'])
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
        caminho = _salvar_upload(request.files.get('img_valvula'), 'valvula', etapa.id)
        if caminho:
            db.session.add(DadosEtapa(etapa_id=etapa.id, campo='img_valvula', valor=caminho))
        _finalizar(etapa); db.session.commit()
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_100.html', oc=oc, ctx=ctx, mensagem=None)


@bp.route('/oc/<int:id>/formulario/110', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_110.html', oc=oc, ctx=ctx, mensagem=None)


@bp.route('/oc/<int:id>/formulario/120', methods=['GET','POST'])
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
        return redirect(url_for('ocs.ver_oc', id=id))
    return render_template('etapa_120.html', oc=oc, ctx=ctx, mensagem=None)
