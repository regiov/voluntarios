# coding=UTF-8

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from vol.models import Voluntario

class Command(BaseCommand):
    help = u"Apaga voluntários que não confirmaram e-mail há mais de 3 meses."
    usage_str = "Uso: ./manage.py cleanup"

    @transaction.atomic
    def handle(self, *args, **options):

        result = Voluntario.objects.filter(aprovado__isnull=True, confirmado=False, data_cadastro__lte=timezone.now()-timedelta(days=90)).delete()
