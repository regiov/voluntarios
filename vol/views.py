# coding=UTF-8

import datetime
import os
import random

from django.shortcuts import render, redirect
from django.template import loader
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseNotAllowed
from django.core.exceptions import ValidationError, SuspiciousOperation
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.forms.formsets import BaseFormSet, formset_factory
from django.conf import settings
from django.urls import reverse
from django.views.decorators.cache import cache_page

from vol.models import Voluntario, AreaTrabalho, AreaAtuacao, Entidade, Necessidade, AreaInteresse

from vol.forms import FormVoluntario, FormEntidade, FormAreaInteresse

from notification.utils import notify_support, notify_email

def csrf_failure(request, reason=""):
    '''Erro de CSRF'''
    notify_support(u'Erro de CSRF', reason, request, 300) # 5h
    return render(request, 'csrf_failure.html', content_type='text/html; charset=utf-8', status=403)

def index(request):
    '''Página principal'''

    # Imagem "splash"
    path = ['images', 'home'] # local onde devem estar armazenadas dentro do static files
    prefixo = 'slide'

    # Lógica de mostrar imagem aleatoriamente cada vez que a página é carregada
    #numeros = []
    #for i in range(1,10):
    #    if os.path.exists(settings.STATIC_ROOT + os.sep + 'images' + os.sep + 'home' + os.sep + prefixo + str(i) + '.jpg'):
    #        numeros.append(i)
    #img = random.choice(numeros)

    # Lógica de mostrar uma imagem por dia, começando sempre numa imagem
    # diferente a cada semana porém seguindo sempre a mesma sequência.
    # Obs: Devem existir 7 imagens no padrão: slide1.jpg, slide2.jpg, etc.
    now = datetime.datetime.now()
    week_of_year = int(now.strftime("%W"))  # semana do ano, começando na primeira segunda [0, 53]
    start_at = (week_of_year % 7) + 1 # imagem para mostrar no primeiro dia da semana [1,7]
    img = start_at + now.weekday() # weekday: [0,6] img: [1,13] imagem para mostrar no dia
    if img > 7:
        img = img - 7

    slide = settings.STATIC_URL + 'images/home/slide' + str(img) + '.jpg'

    context = {'slide': slide}
    template = loader.get_template('vol/index.html')
    return HttpResponse(template.render(context, request))

def mensagem(request, titulo=''):
    '''Página para exibir mensagem genérica'''
    template = loader.get_template('vol/mensagem.html')
    context = {'titulo': titulo}
    return HttpResponse(template.render(context, request))

def envia_confirmacao_voluntario(nome, email):
    '''Envia mensagem de confirmação de cadastro ao voluntário'''
    context = {'primeiro_nome': nome.split(' ')[0],
               'email': email,
               'url': 'http://voluntarios.com.br' + reverse('valida_email_voluntario')}
    try:
        notify_email(email, u'Cadastro de voluntário', 'vol/msg_confirmacao_cadastro_voluntario.txt', from_email=settings.NOREPLY_EMAIL, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

def envia_confirmacao_entidade(nome, email):
    context = {'razao_social': nome,
               'email': email,
               'url': 'http://voluntarios.com.br' + reverse('valida_email_entidade')}
    try:
        notify_email(email, u'Cadastro de entidade', 'vol/msg_confirmacao_cadastro_entidade.txt', from_email=settings.NOREPLY_EMAIL, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

@transaction.atomic
def voluntario_novo(request):
    '''Página de cadastro de voluntário'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    FormSetAreaInteresse = formset_factory(FormAreaInteresse, formset=BaseFormSet, extra=1, max_num=10, can_delete=True)

    if request.method == 'GET':
        messages.info(request, u'Estamos cadastrando profissionais que queiram dedicar parte de seu tempo para ajudar como voluntários a quem precisa.<br>Ao enviar os dados, você receberá um e-mail para confirmação do cadastro.')
        form = FormVoluntario()
        area_interesse_formset = FormSetAreaInteresse()
    if request.method == 'POST':
        form = FormVoluntario(request.POST)
        if form.is_valid():
            voluntario = form.save(commit=False)
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            if area_interesse_formset.is_valid():
                voluntario.save()
                areas = []
                for area_interesse_form in area_interesse_formset:
                    area_atuacao = area_interesse_form.cleaned_data.get('area_atuacao')
                    if area_atuacao:
                        if area_atuacao not in areas:
                            areas.append(area_atuacao)
                            area_interesse = AreaInteresse(area_atuacao=area_atuacao, voluntario=voluntario)
                            area_interesse.save()
                        else:
                            # Ignora duplicidades
                            pass
                    else:
                        # Ignora combos vazios
                        pass
                # Envia mensagem de confirmação
                envia_confirmacao_voluntario(form.cleaned_data['nome'], form.cleaned_data['email'])
                # Redireciona para página de exibição de mensagem
                messages.info(request, u'Obrigado! Você receberá um e-mail de confirmação. Para ter seu cadastro validado, clique no link indicado no e-mail que receber.')
                return mensagem(request, u'Cadastro de Voluntário')
        else:
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            
    context = {'form': form, 'area_interesse_formset': area_interesse_formset}
    template = loader.get_template('vol/formulario_voluntario.html')
    return HttpResponse(template.render(context, request))

def valida_email_voluntario(request):
    '''Confirmação de e-mail de voluntário'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    email = request.GET.get('email')
    if email:
        voluntarios = Voluntario.objects.filter(email=email)
        if len(voluntarios) > 0:
            voluntarios.update(confirmado=True)

        messages.info(request, u'Obrigado! Cadastro validado com sucesso.')
        return mensagem(request, u'Confirmação de Cadastro')

    raise SuspiciousOperation(u'Parâmetro email ausente')

def busca_voluntarios(request):
    '''Página para busca de voluntários'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_trabalho = AreaTrabalho.objects.all().order_by('nome')
    areas_de_interesse = AreaAtuacao.objects.all().order_by('id')
    voluntarios = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'Envia' in request.GET:

        voluntarios = Voluntario.objects.select_related('area_trabalho').filter(confirmado=True)

        # Filtro por área de interesse
        fasocial = request.GET.get('fasocial')
        if fasocial.isdigit() and fasocial not in [0, '0']:
            try:
                area_interesse = AreaAtuacao.objects.get(pk=fasocial)
                if '.' in area_interesse.indice:
                    voluntarios = voluntarios.filter(areainteresse__area_atuacao=fasocial)
                else:
                    voluntarios = voluntarios.filter(Q(areainteresse__area_atuacao=fasocial) | Q(areainteresse__area_atuacao__indice__startswith=str(area_interesse.indice)+'.'))
            except AreaAtuacao.DoesNotExist:
                raise SuspiciousOperation(u'Área de Interesse inexistente')

        # Filtro por cidade
        fcidade = request.GET.get('fcidade')
        if fcidade is not None:
            fcidade = fcidade.strip()
            if len(fcidade) > 0:
                if 'boxexato' in request.GET:
                    voluntarios = voluntarios.filter(cidade__iexact=fcidade)
                else:
                    voluntarios = voluntarios.filter(cidade__icontains=fcidade)

        # Filtro por área de trabalho
        fareatrabalho = request.GET.get('fareatrabalho')
        if fareatrabalho.isdigit() and fareatrabalho not in [0, '0']:
            voluntarios = voluntarios.filter(area_trabalho=fareatrabalho)

        # Ordem dos resultados
        if request.GET.get('ordem', 'interesse') == 'interesse':
            voluntarios = voluntarios.order_by('areainteresse__area_atuacao__nome', 'nome')
        else:
            voluntarios = voluntarios.order_by('area_trabalho__nome', 'nome')

        # Paginação
        paginador = Paginator(voluntarios, 20) # 20 pessoas por página
        pagina = request.GET.get('page')
        try:
            voluntarios = paginador.page(pagina)
        except PageNotAnInteger:
            # Se a página não é um número inteiro, exibe a primeira
            voluntarios = paginador.page(1)
        except EmptyPage:
            # Se a página está fora dos limites (ex 9999), exibe a última
            voluntarios = paginador.page(paginator.num_pages)
        pagina_atual = voluntarios.number
        max_links_visiveis = 10
        intervalo = 10/2
        pagina_inicial = pagina_atual - intervalo
        pagina_final = pagina_atual + intervalo -1
        if pagina_inicial <= 0:
            pagina_final = pagina_final - pagina_inicial + 1
            pagina_inicial = 1
        if pagina_final > paginador.num_pages:
            pagina_final = paginador.num_pages
            pagina_inicial = max(pagina_final - (2*intervalo) + 1, 1)
        # Parâmetros GET
        for k, v in request.GET.items():
            if k in ('page', 'csrfmiddlewaretoken'):
                continue
            if len(get_params) > 0:
                get_params += '&'
            get_params += k + '=' + v

    context = {'areas_de_trabalho': areas_de_trabalho,
               'areas_de_interesse': areas_de_interesse,
               'voluntarios': voluntarios,
               'get_params': get_params,
               'pagina_inicial': pagina_inicial,
               'pagina_final': pagina_final}
    
    template = loader.get_template('vol/busca_voluntarios.html')
    return HttpResponse(template.render(context, request))

def exibe_voluntario(request, id_voluntario):
    '''Página para exibir detalhes de um voluntário'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if not id_voluntario.isdigit():
        raise SuspiciousOperation('Parâmetro id inválido')
    try:
        voluntario = Voluntario.objects.select_related('area_trabalho').get(pk=id_voluntario, confirmado=True)
    except Voluntario.DoesNotExist:
        raise SuspiciousOperation('Voluntário inexistente')
    areas_de_interesse = voluntario.areainteresse_set.all()
    now = datetime.datetime.now()
    context = {'voluntario': voluntario,
               'agora': now,
               'areas_de_interesse': areas_de_interesse}
    template = loader.get_template('vol/exibe_voluntario.html')
    return HttpResponse(template.render(context, request))

def exibe_voluntario_old(request):
    '''Detalhes de voluntário usando URL antiga'''
    if 'idvoluntario' not in request.GET:
        raise SuspiciousOperation('Ausência do parâmetro idvoluntario')
    id_voluntario = request.GET.get('idvoluntario')
    return exibe_voluntario(request, id_voluntario)

@transaction.atomic
def entidade_nova(request):
    '''Página de cadastro de entidade'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    if request.method == 'GET':
        form = FormEntidade()
    if request.method == 'POST':
        form = FormEntidade(request.POST)
        if form.is_valid():
            form.save(commit=True)
            # Tenta georeferenciar
            if form.instance is not None:
                form.instance.geocode()
            # Envia mensagem de confirmação
            envia_confirmacao_entidade(form.cleaned_data['razao_social'], form.cleaned_data['email'])
            # Redireciona para página de exibição de mensagem
            messages.info(request, u'Obrigado! Você receberá um e-mail de confirmação. Para ter o cadastro de entidade validado, clique no link indicado no e-mail que receber.')
            return mensagem(request, u'Cadastro de Entidade')
            
    context = {'form': form}
    template = loader.get_template('vol/formulario_entidade.html')
    return HttpResponse(template.render(context, request))

def valida_email_entidade(request):
    '''Confirmação de e-mail de entidade'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    email = request.GET.get('email')
    if email:
        entidades = Entidade.objects.filter(email=email)
        if len(entidades) > 0:
            entidades.update(confirmado=True)

        messages.info(request, u'Obrigado! Cadastro validado com sucesso.')
    
        return mensagem(request, u'Confirmação de Cadastro')

    raise SuspiciousOperation(u'Parâmetro email ausente')

def busca_entidades(request):
    '''Página de busca de entidades'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_atuacao = AreaAtuacao.objects.all().order_by('id')
    entidades = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'Envia' in request.GET:

        entidades = Entidade.objects.select_related('area_atuacao').filter(confirmado=True)

        # Filtro por área de atuação
        fasocial = request.GET.get('fasocial')
        if fasocial.isdigit() and fasocial not in [0, '0']:
            try:
                area_atuacao = AreaAtuacao.objects.get(pk=fasocial)
                if '.' in area_atuacao.indice:
                    entidades = entidades.filter(area_atuacao=fasocial)
                else:
                    entidades = entidades.filter(Q(area_atuacao=fasocial) | Q(area_atuacao__indice__startswith=str(area_atuacao.indice)+'.'))
            except AreaAtuacao.DoesNotExist:
                raise SuspiciousOperation('Área de Atuação inexistente')

        # Filtro por cidade
        fcidade = request.GET.get('fcidade')
        if fcidade is not None:
            fcidade = fcidade.strip()
            if len(fcidade) > 0:
                if 'boxexato' in request.GET:
                    entidades = entidades.filter(cidade__iexact=fcidade)
                else:
                    entidades = entidades.filter(cidade__icontains=fcidade)

        # Filtro por bairro
        fbairro = request.GET.get('fbairro')
        if fbairro is not None:
            fbairro = fbairro.strip()
            if len(fbairro) > 0:
                entidades = entidades.filter(bairro__icontains=fbairro)

        # Filtro por nome
        fentidade = request.GET.get('fentidade')
        if fentidade is not None:
            fentidade = fentidade.strip()
            if len(fentidade) > 0:
                entidades = entidades.filter(nome_fantasia__icontains=fentidade)

        # Ordem dos resultados
        entidades = entidades.order_by('estado', 'cidade', 'bairro', 'nome_fantasia')

        # Paginação
        paginador = Paginator(entidades, 20) # 20 entidades por página
        pagina = request.GET.get('page')
        try:
            entidades = paginador.page(pagina)
        except PageNotAnInteger:
            # Se a página não é um número inteiro, exibe a primeira
            entidades = paginador.page(1)
        except EmptyPage:
            # Se a página está fora dos limites (ex 9999), exibe a última
            entidades = paginador.page(paginator.num_pages)
        pagina_atual = entidades.number
        max_links_visiveis = 10
        intervalo = 10/2
        pagina_inicial = pagina_atual - intervalo
        pagina_final = pagina_atual + intervalo -1
        if pagina_inicial <= 0:
            pagina_final = pagina_final - pagina_inicial + 1
            pagina_inicial = 1
        if pagina_final > paginador.num_pages:
            pagina_final = paginador.num_pages
            pagina_inicial = max(pagina_final - (2*intervalo) + 1, 1)
        # Parâmetros GET
        for k, v in request.GET.items():
            if k in ('page', 'csrfmiddlewaretoken'):
                continue
            if len(get_params) > 0:
                get_params += '&'
            get_params += k + '=' + v

    context = {'areas_de_atuacao': areas_de_atuacao,
               'entidades': entidades,
               'get_params': get_params,
               'pagina_inicial': pagina_inicial,
               'pagina_final': pagina_final}
    
    template = loader.get_template('vol/busca_entidades.html')
    return HttpResponse(template.render(context, request))

def exibe_entidade(request, id_entidade):
    '''Página para exibir detalhes de uma Entidade'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if not id_entidade.isdigit():
        raise SuspiciousOperation('Parâmetro id inválido')
    try:
        entidade = Entidade.objects.select_related('area_atuacao').get(pk=id_entidade, confirmado=True)
    except Entidade.DoesNotExist:
        raise SuspiciousOperation('Entidade inexistente')
    necessidades = entidade.necessidade_set.all().order_by('-data_solicitacao')
    now = datetime.datetime.now()
    context = {'entidade': entidade,
               'agora': now,
               'necessidades': necessidades}
    template = loader.get_template('vol/exibe_entidade.html')
    return HttpResponse(template.render(context, request))

def exibe_entidade_old(request):
    '''Detalhes de entidade usando URL antiga'''
    if 'colocweb' not in request.GET:
        raise SuspiciousOperation('Ausência do parâmetro colocweb')
    id_entidade = request.GET.get('colocweb')
    return exibe_entidade(request, id_entidade)

@cache_page(60 * 60 * 24) # timeout: 24h
def entidades_kml(request):
    '''KML de todas as Entidades'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    entidades_georref = Entidade.objects.filter(coordenadas__isnull=False, aprovado=True)
    context = {'entidades': entidades_georref}
    return render(request, 'vol/entidades.kml', context=context, content_type='application/vnd.google-earth.kml+xml; charset=utf-8')

def busca_doacoes(request):
    '''Página de busca de doações'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    doacoes = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'pesquisa_ajuda' in request.GET or 'pesquisa_entidade' in request.GET:

        doacoes = Necessidade.objects.select_related('entidade').all()

        if 'pesquisa_ajuda' in request.GET:

            # Filtro por descrição
            fpalavra = request.GET.get('fpalavra')
            if fpalavra is not None:
                fpalavra = fpalavra.strip()
                if len(fpalavra) > 0:
                    doacoes = doacoes.filter(descricao__icontains=fpalavra)

            # Filtro por cidade
            fcidade = request.GET.get('fcidade')
            if fcidade is not None:
                fcidade = fcidade.strip()
                if len(fcidade) > 0:
                    doacoes = doacoes.filter(entidade__cidade__iexact=fcidade)

        if 'pesquisa_entidade' in request.GET:

            # Filtro por nome
            fentidade = request.GET.get('fentidade')
            if fentidade is not None:
                fentidade = fentidade.strip()
                if len(fentidade) > 0:
                    doacoes = doacoes.filter(entidade__nome_fantasia__icontains=fentidade)

            # Filtro por cidade
            fcidade = request.GET.get('fcidade2')
            if fcidade is not None:
                fcidade = fcidade.strip()
                if len(fcidade) > 0:
                    doacoes = doacoes.filter(entidade__cidade__iexact=fcidade)

        # Ordem dos resultados
        doacoes = doacoes.order_by('entidade__razao_social', 'descricao')

        # Paginação
        paginador = Paginator(doacoes, 20) # 20 doações por página
        pagina = request.GET.get('page')
        try:
            doacoes = paginador.page(pagina)
        except PageNotAnInteger:
            # Se a página não é um número inteiro, exibe a primeira
            doacoes = paginador.page(1)
        except EmptyPage:
            # Se a página está fora dos limites (ex 9999), exibe a última
            doacoes = paginador.page(paginator.num_pages)
        pagina_atual = doacoes.number
        max_links_visiveis = 10
        intervalo = 10/2
        pagina_inicial = pagina_atual - intervalo
        pagina_final = pagina_atual + intervalo -1
        if pagina_inicial <= 0:
            pagina_final = pagina_final - pagina_inicial + 1
            pagina_inicial = 1
        if pagina_final > paginador.num_pages:
            pagina_final = paginador.num_pages
            pagina_inicial = max(pagina_final - (2*intervalo) + 1, 1)
        # Parâmetros GET
        for k, v in request.GET.items():
            if k in ('page', 'csrfmiddlewaretoken'):
                continue
            if len(get_params) > 0:
                get_params += '&'
            get_params += k + '=' + v

    context = {'doacoes': doacoes,
               'get_params': get_params,
               'pagina_inicial': pagina_inicial,
               'pagina_final': pagina_final}
    
    template = loader.get_template('vol/busca_doacoes.html')
    return HttpResponse(template.render(context, request))

def mapa_entidades(request):
    '''Página com mapa de Entidades'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    now = datetime.datetime.now()
    context = {'agora': now}
    template = loader.get_template('vol/mapa_entidades.html')
    return HttpResponse(template.render(context, request))

def mural(request):
    '''Página para exibir frases de voluntários'''
    context = {}
    template = loader.get_template('vol/mural.html')
    return HttpResponse(template.render(context, request))

def frase_mural(request):
    '''Retorna descrição aleatória de voluntário'''
    from django.db.models import TextField
    from django.db.models.functions import Length

    c = TextField.register_lookup(Length, 'length')

    query = Voluntario.objects.filter(aprovado=True, descricao__length__gt=30, descricao__length__lt=100)

    cnt = query.count()

    i = random.randint(0, cnt-1)

    vol = query[i]

    return JsonResponse({'texto': vol.descricao,
                         'iniciais': vol.iniciais(),
                         'idade': vol.idade(),
                         'cidade': vol.cidade.title(),
                         'estado': vol.estado.upper()})
