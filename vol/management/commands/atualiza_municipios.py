import json
import requests
from django.db import models
from vol.models import Cidade , Estado
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Resgata dados da API e salva no banco'
    usage_str = "Uso: ./manage.py atualiza_municipios"
    


    def handle(self, *args, **options):
        try:
            estados = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
            estadosJson = estados.json()
            for estado in estadosJson:
                if Estado.objects.filter(nome=estado['nome'],sigla=estado['sigla']).exists():
                    continue
                estado = Estado(
                    nome=estado['nome'],
                    sigla=estado['sigla'])
                estado.save()    

            UFs = ["RO","AC","AM","RR","PA","AP","MA","PI","CE","RN","PB","PE","AL","SE","BA","MG","ES","RJ","SP","PR","SC","RS","MS","MT","GO","DF"]
            for uf in UFs:
                response = requests.get(f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios")
                data = response.json()
                for cidade in data :
                    if Cidade.objects.filter(nome=cidade['nome'],
                    uf = cidade['microrregiao']['mesorregiao']['UF']['sigla']).exists():
                        continue
                    cidade = Cidade(
                        nome=cidade['nome'],
                        uf=cidade['microrregiao']['mesorregiao']['UF']['sigla'])
                    cidade.save()
                    print("done")    
        except :
            print("error")