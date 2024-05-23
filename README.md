# Website voluntarios.com.br

## Requisitos

Docker e Docker Compose

## Iniciar

```
cd docker
docker-compose up
```

## Configuração

Em seguida, na pasta onde foi instalado o código do Voluntários, dentro do diretório *docker/website*, tem um arquivo pre preenchido chamado *local_settings.py*:

Edite o arquivo *local_settings.py*, adicionar parte das configurações:

```
# Você pode deixar para especificar as configurações de e-mail
# quando for de fato precisar das funcionalidades de envio de e-mail
EMAIL_HOST = 'SET IN LOCAL SETTINGS'
EMAIL_PORT = 25
EMAIL_HOST_USER = 'SET IN LOCAL SETTINGS'
EMAIL_HOST_PASSWORD = 'SET IN LOCAL SETTINGS'
DEFAULT_FROM_EMAIL = 'SET IN LOCAL SETTINGS' # remetente das notificações

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

Para popular o banco de dados com dados fictícios de usuários, voluntários e entidades:

```
cd docker
docker-compose run web python3 manage.py gerar_registros (num_voluntarios) (num_entidades)
```

Atenção: (num_voluntarios) e (num_entidades) devem ser substituídos pelo número de voluntários ou entidades a serem gerados, respectivamente. Caso nenhum número seja especificado, o programa gerará e inserirá por padrão 5 voluntários e 5 entidades aleatórias no banco de dados.

Acesse a versão local do site em http://127.0.0.1:8000/

Pronto!

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
