# coding=UTF-8

import time
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from vol.models import Entidade

class Command(BaseCommand):
    help = u"Consulta a situação do CNPJ de entidades que ainda não foram consultadas ou que a última consulta tenha ocorrido há mais de 3 meses."
    usage_str = "Uso: ./manage.py consulta_cnpj"

    def handle(self, *args, **options):

        # Estipula um número máximo de consultas pra não exagerar
        max_consultas = 500

        # Primeiro pega entidades que nunca foram consultadas
        entidades = Entidade.objects.filter(cnpj__isnull=False, data_consulta_cnpj__isnull=True)

        i = 0

        for entidade in entidades:
            # Repete o teste de CNPJ válido pra não bagunçar a contagem de consultas
            if entidade.cnpj_valido():
                entidade.consulta_cnpj()
                # Serviço usado permite apenas 3 consultas por minuto no plano gratuito
                time.sleep(20)
                i = i + 1
            if i == max_consultas:
                break

        if i < max_consultas:
            # Começa a repetir consultas mais antigas
            current_tz = timezone.get_current_timezone()
            now = timezone.now().astimezone(current_tz)
            delta = datetime.timedelta(days=60)
            entidades = Entidade.objects.filter(cnpj__isnull=False, data_consulta_cnpj__lt=now-delta)
            
            for entidade in entidades:
                # Repete o teste de CNPJ válido pra não bagunçar a contagem de consultas
                if entidade.cnpj_valido():
                    entidade.consulta_cnpj()
                    # Serviço usado permite apenas 3 consultas por minuto no plano gratuito
                    time.sleep(20)
                    i = i + 1
                if i == max_consultas:
                    break
