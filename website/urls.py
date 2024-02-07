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

from django.urls import include, re_path, path
from django.conf.urls.static import static
from django.contrib import admin
from django.conf import settings
from django.views import static as views_static
from django.contrib.flatpages import views as flatpages

from vol import views

admin.site.site_header = u'Interface Administrativa'

urlpatterns = [

    re_path(r'^tinymce/', include('tinymce.urls')),

    re_path(r'^$', views.index, name='index'),
    re_path(r'^executivo.htm$', views.index),#old (na falta de pagina melhor para redirecionar)

    re_path(r'^aut/', include('allauth.urls')),

    re_path(r'^cadastro/?$', views.escolha_cadastro, name='escolha_cadastro'),

    re_path(r'^logo/?$', views.logo_rastreado, name='logo_rastreado'),

    # Usuário
    re_path(r'^usuario/novo/?$', views.link_usuario_novo, name='link_usuario_novo'),
    re_path(r'^usuario/?$', views.cadastro_usuario, name='cadastro_usuario'),

    # Voluntários
    re_path(r'^voluntario/novo/?$', views.link_voluntario_novo, name='link_voluntario_novo'),
    re_path(r'^voluntario.htm$', views.link_voluntario_novo),#old

    re_path(r'^voluntario/cadastro/?$', views.cadastro_voluntario, {'msg': None}, name='cadastro_voluntario'),
    re_path(r'^voluntario/termos/?$', views.termos_de_adesao_de_voluntario, name='termos_de_adesao_de_voluntario'),

    re_path(r'^voluntario/busca$', views.busca_voluntarios, name='busca_voluntarios'),
    re_path(r'^contato.htm$', views.busca_voluntarios),#old

    re_path(r'^voluntario/(?P<id_voluntario>\d+)/?$', views.exibe_voluntario, name='exibe_voluntario'),
    #re_path(r'^voluntario.asp$', views.exibe_voluntario_old),#old

    re_path(r'^mural/frase/?$', views.frase_mural, name='frase_mural'),

    re_path(r'^mural/?$', views.mural, name='mural'),

    # Entidades
    re_path(r'^entidade/nova$', views.link_entidade_nova, name='link_entidade_nova'),
    re_path(r'^banco_de_dados.htm$', views.link_entidade_nova),#old

    re_path(r'^entidade/confmail/(?P<id_entidade>\d+)/?$', views.reenvia_confirmacao_email_entidade, name='reenvia_confirmacao_email_entidade'),

    re_path(r'^entidade/confvinc/(?P<id_entidade>\d+)/?$', views.envia_confirmacao_vinculo, name='envia_confirmacao_vinculo'),

    re_path(r'^e/valida$', views.valida_email_entidade, name='valida_email_entidade'),

    re_path(r'^e/vinculo$', views.confirma_vinculo, name='confirma_vinculo'),

    re_path(r'^entidade/cadastro/(?P<id_entidade>\d+)/?$', views.cadastro_entidade, name='cadastro_entidade_id'),
    re_path(r'^entidade/cadastro/?$', views.cadastro_entidade, {'id_entidade': None}, name='cadastro_entidade'),

    re_path(r'^entidade/(?P<id_entidade>\d+)/termos/novo/?$', views.novo_termo_de_adesao, name='novo_termo_de_adesao'),
    re_path(r'^entidade/(?P<id_entidade>\d+)/termos/?$', views.termos_de_adesao_de_entidade, name='termos_de_adesao_de_entidade'),
    re_path(r'^entidades$', views.lista_entidades_vinculadas, name='lista_entidades_vinculadas'),
    re_path(r'^entidade/(?P<id_entidade>\d+)$', views.index_entidade, name='index_entidade'),

    re_path(r'^termo/(?P<slug_termo>[\w-]+)/enviar$', views.enviar_termo_de_adesao, name='enviar_termo_de_adesao'),
    re_path(r'^termo/(?P<slug_termo>[\w-]+)/cancelar$', views.cancelar_termo_de_adesao, name='cancelar_termo_de_adesao'),
    re_path(r'^termo/(?P<slug_termo>[\w-]+)/rescindir$', views.rescindir_termo_de_adesao, name='rescindir_termo_de_adesao'),
    re_path(r'^t/avol/?$', views.assinatura_vol_termo_de_adesao, name='assinatura_vol_termo_de_adesao'),
    re_path(r'^termo/(?P<slug_termo>[\w-]+)/?$', views.termo_de_adesao, name='termo_de_adesao'),

    re_path(r'^entidade/busca$', views.busca_entidades, name='busca_entidades'),
    re_path(r'^pesquisa.htm$', views.busca_entidades),#old
    #re_path(r'^resultadoent.asp$', views.busca_entidades),#old
    #re_path(r'^ResultadoColocIcone.asp$', views.busca_entidades),#old

    re_path(r'^entidade/(?P<id_entidade>\d+)/?$', views.exibe_entidade, name='exibe_entidade'),
    #re_path(r'^entidade.asp$', views.exibe_entidade_old),#old

    re_path(r'^entidade/mapa$', views.mapa_entidades, name='mapa_entidades'),
    
    re_path(r'^doacao/busca$', views.busca_doacoes, name='busca_doacoes'),
    re_path(r'^doacao.htm$', views.busca_doacoes),#old
    
    re_path(r'^gis/entidades.json$', views.entidades_points, name='entidades_points'),

    # Mantido para evitar erro 404 de usuários que clicam em buscas do google
    # (o google indexou o kml, acredita?)
    re_path(r'^entidades.kml$', views.busca_entidades),
    re_path(r'^kmls/010205/entidades.kml$', views.busca_entidades),

    re_path(r'^numeros$', views.numeros, name='numeros'),
    
    # Páginas estáticas
    re_path(r'^p/', include('django.contrib.flatpages.urls')),
    
    re_path(r'^oque_e_voluntariado.htm$', flatpages.flatpage, {'url': '/voluntariado/'}),
    re_path(r'^brasil.htm$', flatpages.flatpage, {'url': '/por-que-ser-voluntario/'}),
    re_path(r'^profissionalismo.htm$', flatpages.flatpage, {'url': '/bom-voluntario/'}),
    re_path(r'^leis.htm$', flatpages.flatpage, {'url': '/leis/'}),
    re_path(r'^termo.htm$', flatpages.flatpage, {'url': '/termo-adesao-voluntario/'}),
    re_path(r'^estatisticas.htm$', flatpages.flatpage, {'url': '/estatisticas/'}),
    re_path(r'^personalidades.htm$', flatpages.flatpage, {'url': '/personalidades/'}),
    re_path(r'^livros_voluntariado.htm$', flatpages.flatpage, {'url': '/livros-voluntariado/'}),

    re_path(r'^redirlogin/?', views.redirect_login, name='redirlogin'),

    re_path(r'^anonconf/?', views.anonymous_email_confirmation),

    #re_path(r'^assistencia.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-area-de-atuacao/'}),
    #re_path(r'^trabalho.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-area-de-trabalho/'}),
    #re_path(r'^distribuicao.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-estado/'}),
    #re_path(r'^idade.htm$', flatpages.flatpage, {'url': '/p/voluntarios-por-idade/'}),
    #re_path(r'^atuacao.htm$', flatpages.flatpage, {'url': '/p/entidades-por-area-de-atuacao/'}),
    #re_path(r'^estado.htm$', flatpages.flatpage, {'url': '/p/entidades-por-estado/'}),
    #re_path(r'^empresas.htm$', flatpages.flatpage, {'url': '/p/empresas/'}),#?texto vol-empresa
    #re_path(r'^lista.htm$', flatpages.flatpage, {'url': '/p/empresas-participantes/'}),#?
    #re_path(r'^icones.htm$', flatpages.flatpage, {'url': '/p/icones/'}),#?
    #re_path(r'^sites.htm$', flatpages.flatpage, {'url': '/p/sites/'}),
    #re_path(r'^curriculos.htm$', flatpages.flatpage, {'url': '/p/mensagem-do-coordenador/'}),
    #re_path(r'^pauta.htm$', flatpages.flatpage, {'url': '/p/pauta/'}),

    # Profissional voluntário
    #re_path(r'^executivo.htm$', flatpages.flatpage, {'url': '/p/executivo/'}),
    #re_path(r'^executivo_bomvoluntario.htm$', flatpages.flatpage, {'url': '/p/executivo-bom-voluntario/'}),
    #re_path(r'^executivo_espera.htm$', flatpages.flatpage, {'url': '/p/executivo-espera/'}),
    #re_path(r'^executivo_porqueImportante.htm$', flatpages.flatpage, {'url': '/p/executivo-porque-importante/'}),
    #re_path(r'^executivo_porqueservolunt.htm$', flatpages.flatpage, {'url': '/p/executivo-porque-voluntario/'}),

    # Páginas administrativas
    re_path(r'^indicadores$', views.indicadores, name='indicadores'),
    re_path(r'^funcao/(?P<id_funcao>\d+)/?$', views.exibe_funcao, name='exibe_funcao'),

    # Interface adm
    re_path(r'^' + settings.MY_ADMIN_PREFIX + '/', admin.site.urls),

    # Painel de controle
    re_path(r'^painel/?$', views.painel, name='painel'),
    re_path(r'^painel/voluntarios/revisao$', views.aprovacao_voluntarios, name='aprovacao_voluntarios'),
    re_path(r'^painel/voluntarios/revisao/panorama$', views.panorama_revisao_voluntarios, name='panorama_revisao_voluntarios'),
    re_path(r'^painel/voluntarios/revisao/carga$', views.carga_revisao_voluntarios, name='carga_revisao_voluntarios'),
    re_path(r'^painel/entidades/revisao$', views.revisao_entidades, name='revisao_entidades'),
    re_path(r'^painel/tarefa/(?P<codigo_tarefa>[\w\-]+)/?$', views.exibe_tarefa, name='exibe_tarefa'),
    re_path(r'^painel/tarefa/(?P<codigo_tarefa>[\w\-]+)/orientacoes/?$', views.exibe_orientacoes_tarefa, name='exibe_orientacoes_tarefa'),
    re_path(r'^painel/cata-email/progresso/uf$', views.progresso_cata_email_por_uf, name='progresso_cata_email_por_uf'),
    re_path(r'^painel/cata-email/progresso/uf/(?P<sigla>[\w]{2})/?$', views.progresso_cata_email_por_municipio, name='progresso_cata_email_por_municipio'),
    re_path(r'^painel/entidades/pendencias$', views.exibe_pendencias_entidades, name='exibe_pendencias_entidades'),
    re_path(r'^painel/entidades/problemacnpj$', views.exibe_entidades_com_problema_na_receita, name='exibe_entidades_com_problema_na_receita'),
    re_path(r'^painel/entidades/onboarding/?$', views.onboarding_entidades, name='onboarding_entidades'),
    re_path(r'^painel/entidades/onboarding/(?P<id_entidade>\d+)/?$', views.onboarding_entidade, name='onboarding_entidade'),
    re_path(r'^painel/processos$', views.revisao_processos_seletivos, name='revisao_processos_seletivos'),
    re_path(r'^painel/processos/(?P<codigo_processo>[\d-]+)$', views.revisao_processo_seletivo, name='revisao_processo_seletivo'),
    re_path(r'^painel/processos/monitoramento$', views.monitoramento_processos_seletivos, name='monitoramento_processos_seletivos'),

    # Blog
    path('blog/<slug:slug>', views.PostagemNoBlog.as_view(), name='postagem_blog'),
    path('blog', views.ListaDePostagensNoBlog.as_view(), name='blog'),

    # Charada
    re_path(r'^'+chr(120)+chr(100)+chr(101)+chr(118)+'$', views.exibir_charada),

    path('retorna_cidades/', views.retorna_cidades, name='retorna_cidades'),

    path('alternar_entidade_favorita/', views.alternar_entidade_favorita, name="alternar_entidade_favorita"),

    path('entidades/favoritas/', views.entidades_favoritas, name="entidades_favoritas"),

    # Processos seletivos
    re_path(r'^entidade/(?P<id_entidade>\d+)/selecao/?$', views.processos_seletivos_entidade, name='processos_seletivos_entidade'),

    re_path(r'^entidade/(?P<id_entidade>\d+)/selecao/nova/?$', views.novo_processo_seletivo, name='novo_processo_seletivo'),
    re_path(r'^entidade/(?P<id_entidade>\d+)/selecao/(?P<codigo_processo>[\d-]+)/inscricoes$', views.inscricoes_processo_seletivo, name='inscricoes_processo_seletivo'),
    re_path(r'^entidade/(?P<id_entidade>\d+)/selecao/(?P<codigo_processo>[\d-]+)/?$', views.editar_processo_seletivo, name='editar_processo_seletivo'),

    re_path(r'^voluntario/inscricoes/?$', views.processos_seletivos_voluntario, name='processos_seletivos_voluntario'),

    re_path(r'^vaga/busca$', views.busca_vagas, name='busca_vagas'),
    re_path(r'^vaga/(?P<codigo_processo>[\d-]+)/inscricao$', views.inscricao_processo_seletivo, name='inscricao_processo_seletivo'),
    re_path(r'^vaga/(?P<codigo_processo>[\d-]+)/?$', views.exibe_processo_seletivo, name='exibe_processo_seletivo'),
    re_path(r'^classificar_inscricao$', views.classificar_inscricao, name='classificar_inscricao'),

]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        re_path('__debug__/', include(debug_toolbar.urls)),
        re_path(r'^imagens/(?P<path>.*)$', views_static.serve, {'document_root': os.path.join(settings.STATIC_ROOT, 'imagens')}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
