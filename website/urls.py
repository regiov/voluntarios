"""website URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
import os

from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.conf import settings
from django.views import static as views_static
from django.contrib.flatpages import views as flatpages

from vol import views

admin.site.site_header = u'Interface Administrativa'

urlpatterns = [

    url(r'^tinymce/', include('tinymce.urls')),

    url(r'^$', views.index, name='index'),
    url(r'^executivo.htm$', views.index),#old (na falta de pagina melhor para redirecionar)

    url(r'^aut/', include('allauth.urls')),

    url(r'^cadastro/?$', views.escolha_cadastro, name='escolha_cadastro'),

    # Usuário
    url(r'^usuario/?$', views.cadastro_usuario, name='cadastro_usuario'),

    # Voluntários
    url(r'^voluntario/novo/?$', views.link_voluntario_novo, name='link_voluntario_novo'),
    url(r'^voluntario.htm$', views.link_voluntario_novo),#old

    url(r'^voluntario/cadastro/?$', views.cadastro_voluntario, {'msg': None}, name='cadastro_voluntario'),

    url(r'^voluntario/busca$', views.busca_voluntarios, name='busca_voluntarios'),
    url(r'^contato.htm$', views.busca_voluntarios),#old

    url(r'^voluntario/(?P<id_voluntario>\d+)/?$', views.exibe_voluntario, name='exibe_voluntario'),
    url(r'^voluntario.asp$', views.exibe_voluntario_old),#old

    url(r'^voluntarios/aprovacao/?$', views.aprovacao_voluntarios, name='aprovacao_voluntarios'),

    url(r'^mural/frase/?$', views.frase_mural, name='frase_mural'),

    url(r'^mural/?$', views.mural, name='mural'),

    # Entidades
    url(r'^entidade/nova$', views.link_entidade_nova, name='link_entidade_nova'),
    url(r'^banco_de_dados.htm$', views.link_entidade_nova),#old

    url(r'^entidade/confmail/(?P<id_entidade>\d+)/?$', views.reenvia_confirmacao_email_entidade, name='reenvia_confirmacao_email_entidade'),

    url(r'^entidade/confvinc/(?P<id_entidade>\d+)/?$', views.envia_confirmacao_vinculo, name='envia_confirmacao_vinculo'),

    url(r'^e/valida$', views.valida_email_entidade, name='valida_email_entidade'),

    url(r'^e/vinculo$', views.confirma_vinculo, name='confirma_vinculo'),

    url(r'^entidade/cadastro/(?P<id_entidade>\d+)/?$', views.cadastro_entidade, name='cadastro_entidade_id'),
    url(r'^entidade/cadastro/?$', views.cadastro_entidade, {'id_entidade': None}, name='cadastro_entidade'),

    url(r'^entidade/busca$', views.busca_entidades, name='busca_entidades'),
    url(r'^pesquisa.htm$', views.busca_entidades),#old
    url(r'^resultadoent.asp$', views.busca_entidades),#old
    url(r'^ResultadoColocIcone.asp$', views.busca_entidades),#old

    url(r'^entidade/(?P<id_entidade>\d+)/?$', views.exibe_entidade, name='exibe_entidade'),
    url(r'^entidade.asp$', views.exibe_entidade_old),#old

    url(r'^entidade/mapa$', views.mapa_entidades, name='mapa_entidades'),
    
    url(r'^doacao/busca$', views.busca_doacoes, name='busca_doacoes'),
    url(r'^doacao.htm$', views.busca_doacoes),#old
    
    url(r'^entidades.kml$', views.entidades_kml, name='entidades_kml'),
    
    # Páginas estáticas
    url(r'^p/', include('django.contrib.flatpages.urls')),
    
    url(r'^oque_e_voluntariado.htm$', flatpages.flatpage, {'url': '/voluntariado/'}),
    url(r'^brasil.htm$', flatpages.flatpage, {'url': '/por-que-ser-voluntario/'}),
    url(r'^profissionalismo.htm$', flatpages.flatpage, {'url': '/bom-voluntario/'}),
    url(r'^leis.htm$', flatpages.flatpage, {'url': '/leis/'}),
    url(r'^termo.htm$', flatpages.flatpage, {'url': '/termo-adesao-voluntario/'}),
    url(r'^estatisticas.htm$', flatpages.flatpage, {'url': '/estatisticas/'}),
    url(r'^personalidades.htm$', flatpages.flatpage, {'url': '/personalidades/'}),
    url(r'^livros_voluntariado.htm$', flatpages.flatpage, {'url': '/livros-voluntariado/'}),

    url(r'^redirlogin/?', views.redirect_login, name='redirlogin'),

    url(r'^anonconf/?', views.anonymous_email_confirmation),

    #url(r'^assistencia.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-area-de-atuacao/'}),
    #url(r'^trabalho.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-area-de-trabalho/'}),
    #url(r'^distribuicao.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-estado/'}),
    #url(r'^idade.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-idade/'}),
    #url(r'^atuacao.htm$', flatpages.flatpage, {'url': '/p/entidades-por-area-de-atuacao/'}),
    #url(r'^estado.htm$', flatpages.flatpage, {'url': '/p/entidades-por-estado/'}),
    #url(r'^empresas.htm$', flatpages.flatpage, {'url': '/p/empresas/'}),#?texto vol-empresa
    #url(r'^lista.htm$', flatpages.flatpage, {'url': '/p/empresas-participantes/'}),#?
    #url(r'^icones.htm$', flatpages.flatpage, {'url': '/p/icones/'}),#?
    #url(r'^sites.htm$', flatpages.flatpage, {'url': '/p/sites/'}),
    #url(r'^curriculos.htm$', flatpages.flatpage, {'url': '/p/mensagem-do-coordenador/'}),
    #url(r'^pauta.htm$', flatpages.flatpage, {'url': '/p/pauta/'}),

    # Profissional voluntário
    #url(r'^executivo.htm$', flatpages.flatpage, {'url': '/p/executivo/'}),
    #url(r'^executivo_bomvoluntario.htm$', flatpages.flatpage, {'url': '/p/executivo-bom-voluntario/'}),
    #url(r'^executivo_espera.htm$', flatpages.flatpage, {'url': '/p/executivo-espera/'}),
    #url(r'^executivo_porqueImportante.htm$', flatpages.flatpage, {'url': '/p/executivo-porque-importante/'}),
    #url(r'^executivo_porqueservolunt.htm$', flatpages.flatpage, {'url': '/p/executivo-porque-voluntario/'}),

    # Páginas administrativas
    url(r'^indicadores$', views.indicadores, name='indicadores'),

    # Interface adm
    url(r'^' + settings.MY_ADMIN_PREFIX + '/', admin.site.urls),

    # Painel de controle
    url(r'^painel$', views.painel, name='painel'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url('__debug__/', include(debug_toolbar.urls)),
        url(r'^imagens/(?P<path>.*)$', views_static.serve, {'document_root': os.path.join(settings.STATIC_ROOT, 'imagens')}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
