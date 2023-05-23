import json
import requests
from django.db import models
from vol.models import Cidade
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Resgata dados da API e salva no banco'
    usage_str = "Uso: ./manage.py atualiza_municipios"
    # "https://servicodados.ibge.gov.br/api/v1/localidades/estados" #localidades/estados/{Estado}/municipios"


    def handle(self, *args, **options):
        try:
            UFs = ["RO","AC","AM","RR","PA","AP","MA","PI","CE","RN","PB","PE","AL","SE","BA","MG","ES","RJ","SP","PR","SC","RS","MS","MT","GO","DF"]
            for uf in UFs:
                response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
                data = response.json()
                for cidade in data :
                    dados_atuais = Cidade.objects.all()
                    if Cidade.objects.filter(nome=cidade['nome'],
                    uf=cidade['microrregiao']['mesorregiao']['UF']['sigla']).exists():
                        continue
                    cidade = Cidade(
                        nome=cidade['nome'],
                        uf=cidade['microrregiao']['mesorregiao']['UF']['sigla'])
                    cidade.save()
                    print('done')    
        except :
            print("error")