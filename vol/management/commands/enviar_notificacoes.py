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
        ok = 0
        for notificacao in notificacoes_pendentes:
            if notificacao.enviar():
                ok = ok + 1
            n = n + 1

        texto_ok = 'notificações enviadas'
        if ok == 1:
            texto_ok = 'notificação enviada'

        texto_pendentes = 'notificações pendentes'
        if n == 1:
            texto_pendentes = 'notificação pendente'

        self.stdout.write(self.style.NOTICE(f"{ok} {texto_ok} de {n} {texto_pendentes}."))
