# coding=UTF-8

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from vol.models import Usuario, Voluntario
from notification.models import Message, Event

from notification.utils import notify_user_msg

class Command(BaseCommand):
    help = u"Relembra usuários que se cadastraram há mais de uma semana mas não preencheram cadastro de voluntário."
    usage_str = "Uso: ./manage.py remind"

    @transaction.atomic
    def handle(self, *args, **options):

        msg = Message.objects.get(code='LEMBRETE_CADASTRO_VOLUNTARIO')

        usuarios = Usuario.objects.annotate(sem_cadastro=~Exists(Voluntario.objects.filter(usuario=OuterRef('pk')))).annotate(sem_notificacao=~Exists(Event.objects.filter(user=OuterRef('pk'), message=msg))).filter(link='voluntario_novo', date_joined__lte=timezone.now()-timedelta(days=7), date_joined__gte=timezone.now()-timedelta(days=30), sem_cadastro=True, sem_notificacao=True, emailaddress__verified=True)

        for usuario in usuarios:
            notify_user_msg(usuario, msg)

