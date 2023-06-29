import json
import requests
from vol.models import Cidade, Estado
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Resgata dados da API do IBGE e atualiza no banco'
    usage_str = "Uso: ./manage.py atualiza_municipios"

    def handle(self, *args, **options):
        try:
            estados = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
            estadosJson = estados.json()
            n = 0
            for estado in estadosJson:
                if Estado.objects.filter(nome=estado['nome'], sigla=estado['sigla']).exists():
                    continue
                estado = Estado(
                    nome=estado['nome'],
                    sigla=estado['sigla'])
                estado.save()
                n = n + 1
            print(n, 'estados incluídos')

            UFs = list(Estado.objects.all().values_list('sigla', flat=True))
            for uf in UFs:
                n = 0
                print('Processando', uf)
                cidades_no_banco = list(Cidade.objects.filter(uf=uf).values_list('nome', flat=True))
                response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
                data = response.json()
                for cidade in data:
                    if cidade['nome'] in cidades_no_banco:
                        continue
                    cidade = Cidade(nome=cidade['nome'], uf=uf)
                    cidade.save()
                    n = n + 1
                print(n, 'municípios incluídos')
        except Exception as e:
            print('Erro:', str(e))
