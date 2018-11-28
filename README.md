# Website voluntarios.com.br

## Requisitos

* PostgreSQL 9.x
* Python 3
* Django 2.0
* django-tinymce 2.6.0
* django-bootstrapform 3.4
* django-allauth 0.37.0

## Configuração

Depois de instalar os programas acima, crie um banco de dados:

```
createdb NOME_DO_BANCO
```

Em seguida faça uma cópia local do website:

```
git clone https://github.com/regiov/voluntarios.git website
```

Dentro do diretório *website/website*, faça uma cópia do arquivo *settings.py* chamada *local_settings.py*:

```
cd website/website
cp settings.py local_settings.py
```

Edite o arquivo *local_settings.py*, removendo todas as configurações que não contenham *SET IN LOCAL SETTINGS*. Em seguida especifique todas as configurações locais da sua instalação.

Crie as tabelas através do Django:

```
./manage.py makemigrations
./manage.py migrate

```

Exporte os arquivos estáticos para um diretório previamente criado e já especificado nas configurações locais:

```
./manage.py collectstatic -l
```

Compile os dicionários com as traduções locais:

```
django-admin.py compilemessages --locale=pt_BR
```

Inicie o Django em modo desenvolvimento:

```
./manage.py runserver
```
