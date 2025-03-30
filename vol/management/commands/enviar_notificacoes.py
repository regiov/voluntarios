# coding=UTF-8

from django.core.management.base import BaseCommand
from django.db import transaction

from vol.models import Notificacao

class Command(BaseCommand):
    help = u"Envia notificações pendentes para o canal feed da nossa comunidade no Discord."
    usage_str = "Uso: ./manage.py enviar_notificacoes"

    @transaction.atomic
    def handle(self, *args, **options):

        notificacoes_pendentes = Notificacao.objects.all().order_by('criada_em')
        n = 0
        for notificacao in notificacoes_pendentes:
            notificacao.enviar()
            n = n + 1

        texto = 'notificações enviadas'
        if n == 1:
            texto = 'notificação enviada'
            
        self.stdout.write(self.style.NOTICE(f"{n} {texto}.'))
