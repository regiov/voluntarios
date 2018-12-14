# coding=UTF-8

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from vol.models import Usuario
from notification.models import Message, Event

from notification.utils import notify_user_msg

class Command(BaseCommand):
    help = u"Relembra usuários que se cadastraram há mais de uma semana mas não preencheram cadastro de voluntário."
    usage_str = "Uso: ./manage.py remind"

    @transaction.atomic
    def handle(self, *args, **options):

        usuarios = Usuario.objects.filter(link='voluntario_novo', date_joined__lte=timezone.now()-timedelta(days=7), date_joined__gte=timezone.now()-timedelta(days=30))

        msg = Message.objects.get(code='LEMBRETE_CADASTRO_VOLUNTARIO')

        for usuario in usuarios:
            if not usuario.is_voluntario:
                try:
                    evt = Event.objects.get(user=usuario, message=msg)
                except Message.DoesNotExist:
                    notify_user_msg(usuario, msg)

