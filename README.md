# Website voluntarios.com.br

Bem-vind@ ao código fonte do site voluntarios.com.br!

Este é um dos sites mais antigos no Brasil sobre voluntariado, conectando pessoas que desejam trabalhar voluntariamente com organizações sem fins lucrativos que precisam de voluntários. Apesar do domínio ".com.br", não somos uma empresa. Tampouco somos uma ONG. Estamos organizados como um simples coletivo informal de pessoas que tem como interesse comum promover a cultura do voluntariado.

O site dispõe de funcionalidades como: cadastro de voluntários, cadastro de organizações sem fins lucrativos, publicação de vagas de trabalho voluntário, busca de voluntários, busca de organizações, busca de vagas com possibilidade de inscrição, gerenciamento de processos seletivos, emissão de termos de adesão de trabalho voluntário, blog sobre o tema, entre outros, além de muito conteúdo relacionado ao voluntariado.

## Tecnologias

* Linguagens: Python 3 (backend) e JavaScript (frontend)
* Banco de dados: PostgreSQL com a extensão Postgis (consequentemente dependendo das libs GEOS e GDAL)
* Framework no backend: Django com os módulos:
    * [crispy-forms](https://django-crispy-forms.readthedocs.io/en/latest/index.html)
    * [tinymce](https://github.com/jazzband/django-tinymce/releases)
    * [allauth](https://github.com/pennersr/django-allauth/tags)
    * [mptt](https://github.com/django-mptt/django-mptt/tags)
    * [fsm](https://github.com/viewflow/django-fsm)
    * [fsm-log](https://github.com/gizmag/django-fsm-log)
* Libs no frontend: jQuery e Booststrap

## Instalação

### Opção 1: via Docker

Requisitos: Docker e Docker Compose

```
cd docker
docker-compose up
```

Observe que na pasta onde foi instalado o código do Voluntários, dentro do diretório *docker/website*, já há um arquivo pré-preenchido chamado *local_settings.py* contendo configurações básicas para rodar o site. No entanto, várias outras funcionalidades do site dependem de configurações adicionais que podem ser incluídas manualmente neste mesmo arquivo tomando como base o arquivo *settings.py* que contém todos os parâmetros de configuração e indica quais deles devem ser especificados na configuração local.

### Opção 2: via Python/pip

Requisitos: ter Python e PostgreSQL instalados, incluindo o gerenciador de pacotes do Python (pip) e o pacote de desenvolvimento do Python (normalmente chamado python-dev) para poder compilar o psycopg2.

```
git clone git@github.com:regiov/voluntarios.git $HOME/tmp/voluntarios
cd $HOME/tmp/voluntarios
virtualenv -p python3 $HOME/tmp/voluntarios/.venv/
source $HOME/tmp/voluntarios/.venv/bin/activate
pip install -r requirements.txt
```

A opção 3 à seguir contém as instruções adicionais após a instalação manual de todos os componentes.

### Opção 3: na raça

Requisitos: Python, PostgreSQL, GDAL, GEOS e Django instalados.

Instale manualmente psycopg2 (normalmente via pacote) e os módulos do Django, seja via pacote, seja via pip, seja via "python3 setup.py install". Faça também download do código do Voluntários.

(obs: as instruções abaixo foram feitas com base em ambiente GNU/Linux)

Crie um banco de dados PostgreSQL novo:

```
createdb NOME_DO_BANCO
```

Acesse o banco via linha de comando como superusuário (normalmente "postgres") para habilitar a extensão postgis:

```
sudo su - postgres
psql NOME_DO_BANCO
create extension postgis;
\q
```

Em seguida, na pasta onde foi instalado o código do Voluntários, dentro do diretório *website*, faça uma cópia do arquivo *settings.py* chamada *local_settings.py*:

```
cp website/settings.py website/local_settings.py
```

Edite o arquivo *local_settings.py*, removendo a maior parte das configurqações que não contenham *SET IN LOCAL SETTINGS*. Em seguida especifique todas as configurações locais da sua instalação, substituindo *SET IN LOCAL SETTINGS* pela sua configuração local. Mantenha apenas as configurações DEBUG e ALLOWED_HOSTS, com valores True e ['127.0.0.1', 'localhost'], respectivamente. Seu arquivo *local_settings.py* deverá ficar com este aspecto:

```
SECRET_KEY = 'DIGITE_UM_TEXTO_TOTALMENTE_ALEATORIO'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Você pode deixar para especificar as configurações de e-mail
# quando for de fato precisar das funcionalidades de envio de e-mail
ADMINS = (
     ('SEU NOME', 'SEU@EMAIL'), # Lista de contatos notificados em caso de erro
)
EMAIL_HOST = 'SET IN LOCAL SETTINGS'
EMAIL_PORT = 25
EMAIL_HOST_USER = 'SET IN LOCAL SETTINGS'
EMAIL_HOST_PASSWORD = 'SET IN LOCAL SETTINGS'
DEFAULT_FROM_EMAIL = 'SET IN LOCAL SETTINGS' # Remetente padrão de e-mails
SERVER_EMAIL = 'SET IN LOCAL SETTINGS' # Remetente de notificações de erro

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
Popule o banco com os estados e cidades :

```
python3 manage.py atualiza_municipios
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

## Dados de teste

É possível gerar usuários, voluntários e entidades fictícias através do programa *gerar_registros*.

Com Docker:

```
cd docker
docker-compose run web python3 manage.py gerar_registros --num-voluntarios X --num-entidades Y --num-vagas Z
```

Sem Docker:

```
python3 manage.py gerar_registros --num-voluntarios X --num-entidades Y --num-vagas Z
``` 

### Login por redes sociais

(obs: configurações opcionais, caso seja necessário habilitar o login por redes sociais)

Primeiro obtenha as chaves secretas e o identificador de cliente para cada provedor de acordo com as instruções a seguir:

#### Facebook

Acesse a [interface do Facebook para desenvolvedores](https://developers.facebook.com/) e crie um novo app com o produto "Login do Facebook".

Especifique nome de exibição, email de contato, domínios do app (localhost), URLs de política de privacidade e termos de uso (pode colocar os links oficiais do site) e URL de instruções de exclusão de dados (pode colocar o link oficial dos termos de uso). Salve as alterações.

Nas configurações do produto "Login do Facebook", especifique as "URIs de redirecionamento do OAuth válidos": https://localhost/aut/facebook/login/callback/ e salve as alterações.

No menu superior mude o modo do aplicativo para "ao vivo" (produção).

Na interface administrativa do Voluntários, adicione um novo aplicativo social do tipo "Facebook" colocando o id do aplicativo do Facebook no campo "Id do cliente" e a chave secreta do aplicativo no campo "chave secreta". Inclua o site sendo usado na lista "sites escolhidos" e salve as alterações.

O Facebook requer o uso de SSL nas requisições, então será necessário configurar um servidor web para acessar o Django, habilitando também SSL. Consulte as instruções do seu servidor web para isso.

#### Google

Acesse a [interface console do Google](https://console.cloud.google.com/) e crie um novo projeto chamado, por exemplo, "Website Voluntários". Dentro de "APIs e Serviços" / "Credenciais", crie uma nova credencial do tipo "Id do Cliente OAuth". Em "Origens JavaScript autorizadas" inclua http://127.0.0.1:8000, e em "URIs de redirecionamento autorizados" inclua http://127.0.0.1:8000/aut/google/login/callback/

Em seguida configure o app e a "Tela de permissão OAuth", marcando o tipo de usuário como "externo" e incluindo um e-mail para teste.


Por fim, adicione todos os SocialApps desejados através da interface administrativa, indicando os ids de cliente e chaves secretas fornecidas pelos provedores.

### Orientações adicionais a novos desenvolvedores

Consulte o [Wiki do Voluntários no github](https://github.com/regiov/voluntarios/wiki).
