# Website voluntarios.com.br

## Requisitos

* PostgreSQL >= 9.6
* Postgis >= 2.4.3
* Python >= 3.6
* Django >= 4.0.4
* [django-tinymce](https://github.com/jazzband/django-tinymce/releases) >= 3.4.0
* [django-bootstrapform](https://github.com/tzangms/django-bootstrap-form) 3.4 (clonar do master branch)
* [django-allauth](https://github.com/pennersr/django-allauth/tags) >= 0.50.0
* [django-mptt](https://github.com/django-mptt/django-mptt/tags) >= 0.13.4

## Configuração

(obs: instruções feitas com base em ambiente GNU/Linux)

Depois de instalar os programas acima, crie um banco de dados PostgreSQL novo. Em linha de comando seria:

```
createdb NOME_DO_BANCO
```

Acesse o banco de dados via linha de comando como superusuário (normalmente "postgres") para habilitar a extensão postgis:

```
sudo su - postgres
psql NOME_DO_BANCO
create extension postgis;
\q
```

Em seguida faça uma cópia local do website Voluntários num diretório de sua preferência:

```
cd /MEU/DIRETORIO/DE/INSTALACAO
git clone https://github.com/regiov/voluntarios.git website
```

Dentro do diretório *website/website*, faça uma cópia do arquivo *settings.py* chamada *local_settings.py*:

```
cd website/website
cp settings.py local_settings.py
```

Edite o arquivo *local_settings.py*, removendo a maior parte das configurqações que não contenham *SET IN LOCAL SETTINGS*. Em seguida especifique todas as configurações locais da sua instalação, substituindo *SET IN LOCAL SETTINGS* pela sua configuração local. Mantenha apenas as configurações DEBUG e ALLOWED_HOSTS, com valores True e ['127.0.0.1', 'localhost'], respectivamente. Seu arquivo local_settings.py deverá ficar com esse aspecto:

```
SECRET_KEY = 'DIGITE_UM_TEXTO_TOTALMENTE_ALEATORIO'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Você pode deixar para especificar as configurações de e-mail
# quando for de fato precisar das funcionalidades de envio de e-mail
EMAIL_HOST = 'SET IN LOCAL SETTINGS'
EMAIL_PORT = 25
EMAIL_HOST_USER = 'SET IN LOCAL SETTINGS'
EMAIL_HOST_PASSWORD = 'SET IN LOCAL SETTINGS'
DEFAULT_FROM_EMAIL = 'SET IN LOCAL SETTINGS' # remetente das notificações

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'NOME_DO_BANCO',
    }
}

# Lembre de criar o diretório "static"
STATIC_ROOT = '/MEU/DIRETORIO/DE/INSTALACAO/static'

# Lembre de criar o diretório "media"
MEDIA_ROOT = '/MEU/DIRETORIO/DE/INSTALACAO/media'
MEDIA_URL = 'http://127.0.0.1:8000/media/'

MY_ADMIN_PREFIX = 'adm'

# Caso queira testar o mapa de entidades, insira
# aqui uma chave própria para uso do Google Maps
GOOGLE_MAPS_API_KEY = 'SET IN LOCAL SETTINGS'

# Você pode deixar para especificar essas configurações
# quando for precisar das funcionalidades de notificação automática
NOTIFY_SUPPORT_FROM = 'SET IN LOCAL SETTINGS'
NOTIFY_SUPPORT_TO = 'SET IN LOCAL SETTINGS'
NOTIFY_USER_FROM = 'SET IN LOCAL SETTINGS'

CONTACT_EMAIL = 'seu@email.com'

# A menos que se queira usar a funcionalidade de recepção de entidades,
# as configurações abaixo não precisam ser especificadas
ONBOARDING_EMAIL_FROM = 'SET IN LOCAL SETTINGS'
ONBOARDING_IMAP_SERVER = 'SET IN LOCAL SETTINGS'
ONBOARDING_EMAIL_HOST_USER = 'SET IN LOCAL SETTINGS'
ONBOARDING_EMAIL_HOST_PASSWORD = 'SET IN LOCAL SETTINGS'
ONBOARDING_NOTIFY_RESPONSE_ARRIVAL = 'SET IN LOCAL SETTINGS'
ONBOARDING_TEAM_EMAIL = 'SET IN LOCAL SETTINGS'
```

Feita a configuração, crie as tabelas através do Django migrations, lembrando de antes criar as migrações iniciais para os módulos *notification* e *vol*:

```
python3 manage.py makemigrations vol
python3 manage.py makemigrations notification
python3 manage.py migrate
```

Faça a carga inicial de dados nas principais tabelas, removendo antes o conteúdo das tabelas *auth_permission* e *django_content_type*:

```
python3 manage.py dbshell -- -c 'delete from auth_permission'
python3 manage.py dbshell -- -c 'delete from django_content_type'
python3 manage.py loaddata vol/fixtures/django_*
python3 manage.py loaddata vol/fixtures/auth_*
python3 manage.py loaddata vol/fixtures/notification_*
python3 manage.py loaddata vol/fixtures/vol_*
```

Exporte os arquivos estáticos para um diretório previamente criado e já especificado nas configurações locais:

```
python3 manage.py collectstatic -l
```

Compile os dicionários com as traduções locais:

```
python3 manage.py compilemessages --locale=pt_BR
```

Inicie o Django em modo desenvolvimento:

```
python3 manage.py runserver
```

Acesse a versão local do site em http://127.0.0.1:8000/
