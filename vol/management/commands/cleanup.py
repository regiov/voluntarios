# coding=UTF-8

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from allauth.account.models import EmailAddress
from vol.models import VinculoEntidade

class Command(BaseCommand):
    help = u"Apaga usuários que não confirmaram e-mail há mais de 3 meses e vínculos com entidades não confirmados há mais de 1 mês."
    usage_str = "Uso: ./manage.py cleanup"

    def add_arguments(self, parser):

        parser.add_argument('-m', '--max', type=int, default=500, help='Número máximo de usuários removidos')

    @transaction.atomic
    def handle(self, *args, **options):

        max_deletes = options['max'] if options['max'] else 500

        emails_antigos_nao_confirmados = EmailAddress.objects.filter(verified=False, user__date_joined__lte=timezone.now()-timedelta(days=90))
        n = 0
        for email in emails_antigos_nao_confirmados:
            if n == max_deletes:
                break
            # Verificamos se o usuário já cadastrou algo mais antes de apagá-lo.
            # É uma forma de contornar o fato de ainda não termos controle de quando o usuário
            # cadastrou o e-mail, uma vez que este pode ser alterado.
            if not email.user.is_voluntario:
                resultado = email.user.delete()
                n = n + 1

        vinculos_antigos_nao_confirmados = VinculoEntidade.objects.filter(confirmado=False, data_inicio__lte=timezone.now()-timedelta(days=30)).delete()
