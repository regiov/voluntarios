# coding=UTF-8

from django.apps import apps

from .utils import notifica_aprovacao_voluntario, notifica_aprovacao_entidade

def my_user_signed_up(request, user, **kwargs):
    fields = ['is_active']
    # Ativa usuário que acaba de se registrar, do contrário
    # será exibida tela de usuário inativo
    user.is_active = True
    if 'link' in request.session:
        # Armazena origem do cadastro, para posteriormente
        # direcionar usuário corretamente após login
        user.link = request.session['link']
        fields.append('link')
        del request.session['link']
        request.session.modified = True
    elif 'termo' in request.session:
        # Armazena origem do cadastro, para posteriormente
        # direcionar usuário corretamente após login
        user.link = 'termo'
        fields.append('link')
    user.save(update_fields=fields)

def voluntario_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    '''Post save de voluntários. Atenção: a aprovação pelo painel de controle não dispara este sinal, pois usa update!'''
    # Se o atributo "aprovado" passou de nulo a verdadeiro
    if instance.old_value('aprovado') is None and instance.aprovado:
        notifica_aprovacao_voluntario(instance.usuario)

def entidade_pre_save(sender, instance, raw, using, update_fields, **kwargs):
    '''Pre save de entidades.'''
    # Se o atributo "aprovado" passou de nulo a qualquer valor
    if instance.old_value('aprovado') is None and instance.aprovado is not None:
        # Reseta eventual lock de registro
        # OBS: se na interface adm o usuário clicar em "salvar e continuar editando",
        # haverá novo bloqueio logo em seguida.
        if instance.resp_bloqueio is not None or instance.data_bloqueio is not None:
            instance.resp_bloqueio = None
            instance.data_bloqueio = None
            if update_fields:
                if 'resp_bloqueio' not in update_fields:
                    update_fields.append('resp_bloqueio')
                if 'data_bloqueio' not in update_fields:
                    update_fields.append('data_bloqueio')

def entidade_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    '''Post save de entidades. Atenção: a aprovação pelo painel de controle não dispara este sinal, pois usa update!'''
    # Se o atributo "aprovado" passou de nulo a verdadeiro
    if instance.old_value('aprovado') is None and instance.aprovado:
        notifica_aprovacao_entidade(instance)
        #instance.notifica_aprovacao()
