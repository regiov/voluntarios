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

def usuario_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    '''Post save de usuários para propagar alteração de e-mail.'''
    if not created:
        if instance.has_changed('email'):
            old_email_address = instance.emailaddress_set.filter(email=instance.old_value('email')).first()
            if old_email_address:
                # A lógica abaixo foi introduzida em função de erros esporádicos de violação
                # de unicidade de email ao atualizar o endereço. Não se sabe que condição deflagra
                # esse tipo de situação.
                new_email_address = instance.emailaddress_set.filter(email=instance.email).first()
                if new_email_address:
                    # Se já existir um email atualizado para o usuário, apaga o email antigo
                    old_email_address.delete()
                else:
                    # Do contrário, atualiza o email antigo
                    old_email_address.email = instance.email
                    old_email_address.save(update_fields=['email'])

def voluntario_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    '''Post save de voluntários. Atenção: a aprovação pelo painel de controle não dispara este sinal, pois usa update!'''
    if instance.old_value('aprovado') is None and instance.aprovado:
        # Voluntário aprovado pela primeira vez
        notifica_aprovacao_voluntario(instance.usuario)

    if instance.old_value('aprovado') in (None, True) and instance.aprovado == False:
        # Cadastro rejeitado de voluntário, cancela inscrições em processos seletivos em aberto
        for inscricao in instance.inscricoes():
            if inscricao.aguardando_selecao():
                inscricao.cancelar()
                inscricao.save()
            else:
                # devemos notificar a área administrativa?
                pass

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
        if hasattr(instance, 'bloquear_notificacoes') and instance.bloquear_notificacoes:
            return
        notifica_aprovacao_entidade(instance)
        #instance.notifica_aprovacao()
