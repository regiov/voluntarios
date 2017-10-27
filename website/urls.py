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
from django.contrib import admin
from django.conf import settings
from django.views import static
from django.contrib.flatpages import views as flatpages

from vol import views

admin.site.site_header = u'Interface Administrativa'

urlpatterns = [

    url(r'^tinymce/', include('tinymce.urls')),

    url(r'^$', views.index, name='index'),#ok

    # Voluntários
    url(r'^voluntario/novo/?$', views.voluntario_novo, name='voluntario_novo'),#ok
    url(r'^voluntario.htm$', views.voluntario_novo),

    url(r'^voluntario/validacao/?$', views.valida_email_voluntario, name='valida_email_voluntario'),
    url(r'^confirma-cadastro-voluntario/?$', views.valida_email_voluntario),

    url(r'^voluntario/busca$', views.busca_voluntarios, name='busca_voluntarios'),#ok
    url(r'^contato.htm$', views.busca_voluntarios),

    url(r'^voluntario/(?P<id_voluntario>\d+)/?$', views.exibe_voluntario, name='exibe_voluntario'),#ok
    url(r'^voluntario.asp$', views.exibe_voluntario_old),

    # Entidades
    url(r'^entidade/nova$', views.entidade_nova, name='entidade_nova'),#ok
    url(r'^banco_de_dados.htm$', views.entidade_nova),

    url(r'^entidade/validacao/?$', views.valida_email_entidade, name='valida_email_entidade'),
    url(r'^confirma-cadastro-entidade/?$', views.valida_email_entidade),

    url(r'^entidade/busca$', views.busca_entidades, name='busca_entidades'),#ok
    url(r'^pesquisa.htm$', views.busca_entidades),

    url(r'^entidade/(?P<id_entidade>\d+)/?$', views.exibe_entidade, name='exibe_entidade'),#ok
    url(r'^entidade.asp$', views.exibe_entidade_old),

    url(r'^entidade/mapa$', views.mapa_entidades, name='mapa_entidades'),#ok
    
    url(r'^doacao/busca$', views.busca_doacoes, name='busca_doacoes'),#ok
    url(r'^doacao.htm$', views.busca_doacoes),
    
    url(r'^entidades.kml$', views.entidades_kml, name='entidades_kml'),#ok
    
    # Páginas estáticas
    url(r'^p/', include('django.contrib.flatpages.urls')),
    
    url(r'^oque_e_voluntariado.htm$', flatpages.flatpage, {'url': '/voluntariado/'}),#ok
    url(r'^brasil.htm$', flatpages.flatpage, {'url': '/por-que-ser-voluntario/'}),#ok
    url(r'^profissionalismo.htm$', flatpages.flatpage, {'url': '/bom-voluntario/'}),#ok
    url(r'^leis.htm$', flatpages.flatpage, {'url': '/leis/'}),#ok
    url(r'^termo.htm$', flatpages.flatpage, {'url': '/termo-adesao-voluntario/'}),#ok
    url(r'^estatisticas.htm$', flatpages.flatpage, {'url': '/estatisticas/'}),#ok
    url(r'^personalidades.htm$', flatpages.flatpage, {'url': '/personalidades/'}),#ok
    url(r'^livros_voluntariado.htm$', flatpages.flatpage, {'url': '/livros-voluntariado/'}),#ok

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

    # Interface adm
    url(r'^' + settings.MY_ADMIN_PREFIX + '/', admin.site.urls),#ok
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^imagens/(?P<path>.*)$', static.serve, {'document_root': os.path.join(settings.STATIC_ROOT, 'imagens')}),
]
