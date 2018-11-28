# coding=UTF-8

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from allauth.account.models import EmailAddress

class Command(BaseCommand):
    help = u"Apaga usuários que não confirmaram e-mail há mais de 3 meses."
    usage_str = "Uso: ./manage.py cleanup"

    @transaction.atomic
    def handle(self, *args, **options):

        emails_antigos_nao_confirmados = EmailAddress.objects.filter(verified=False, user__date_joined__lte=timezone.now()-timedelta(days=90))
        for email in emails_antigos_nao_confirmados:
            # Verificamos se o usuário já cadastrou algo mais antes de apagá-lo.
            # É uma forma de contornar o fato de ainda não termos controle de quando o usuário
            # cadastrou o e-mail, uma vez que este pode ser alterado.
            if not email.user.is_voluntario:
                resultado = email.user.delete()
