# coding=UTF-8

from django.apps import apps

from notification.models import Message, Event
from notification.utils import notify_support, notify_user_msg

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
    user.save(update_fields=fields)

def voluntario_post_save(sender, instance, created, raw, using, update_fields, **kwargs):
    # Se o atributo "aprovado" passou de nulo a verdadeiro
    if instance.old_value('aprovado') is None and instance.aprovado:
        # Se o usuário nunca recebeu o aviso de aprovação
        msg = Message.objects.get(code='AVISO_APROVACAO_VOLUNTARIO')
        if Event.objects.filter(user=instance.usuario, message=msg).count() == 0:
            # Envia notificação
            notify_user_msg(instance.usuario, msg)
