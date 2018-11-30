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
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.urls import reverse

from vol.models import Voluntario, AreaTrabalho, AreaAtuacao, Entidade, Necessidade, AreaInteresse

from allauth.account.models import EmailAddress

from vol.forms import FormVoluntario, FormEntidade, FormAreaInteresse
from vol.util import ChangeUserProfileForm

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

@login_required
@transaction.atomic
def usuario_cadastro(request):
    template = loader.get_template('vol/formulario_usuario.html')
    if request.method == 'POST':
        form = ChangeUserProfileForm(request=request, data=request.POST)
        if form.is_valid():
            request.user.nome = form.cleaned_data['nome']
            confirm_email = False
            # Gerenciamento de alteração de e-mail
            if request.user.email != form.cleaned_data['email']:
                email_anterior = request.user.email
                request.user.email = form.cleaned_data['email']
                try:
                    email = EmailAddress.objects.get(user=request.user, email=form.cleaned_data['email'])
                    # Se o novo e-mail já existe:
                    if not email.primary:
                        email.set_as_primary()
                    if not email.verified:
                        confirm_email = True
                        email.send_confirmation(request=request)
                    # Apaga o outro email
                    try:
                        ex_email = EmailAddress.objects.get(user=request.user, email=email_anterior)
                        ex_email.delete()
                    except EmailAddress.DoesNotExist:
                        pass
                except EmailAddress.DoesNotExist:
                    # Se o novo e-mail não existe:
                    confirm_email = True
                    # Remove outros eventuais emails
                    EmailAddress.objects.filter(user=request.user).delete()
                    # Adiciona novo email no modelo do allauth (mensagem de confirmação é enviada automaticamente)
                    email = EmailAddress.objects.add_email(request, request.user, form.cleaned_data["email"], confirm=True)
                    email.set_as_primary()
                    confirm_email = True
            if len(form.cleaned_data['password1']) > 0:
                request.user.set_password(form.cleaned_data["password1"])
            request.user.save()
            messages.info(request, u'Alterações gravadas com sucesso.')
            if confirm_email:
                messages.info(request, u'Devido à troca de e-mail será necessário confirmá-lo antes de entrar novamente no sistema. Acabamos de enviar uma mensagem contendo um link para confirmação.')
                # Faz logout do usuário e não permite login até que o novo e-mail seja confirmado
                logout(request)
                # Redireciona para página de login
                return redirect('/aut/signin')
    else:
        form = ChangeUserProfileForm(initial={'nome': request.user.nome, 'email': request.user.email})
    context = {'form': form}
    return HttpResponse(template.render(context, request))

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

def voluntario_novo(request):
    '''Link para cadastro de novo voluntário'''
    if request.user.is_authenticated:
        # Redireciona para página de cadastro que irá exibir formulário preenchido ou não
        return redirect('/voluntario/cadastro')
    # Indica que usuário quer se cadastrar como voluntário e redireciona para cadastro básico
    request.session['link'] = 'voluntario_novo'
    return redirect('/aut/signup')

@login_required
@transaction.atomic
def voluntario_cadastro(request, msg=None):
    '''Página de cadastro de voluntário'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    FormSetAreaInteresse = formset_factory(FormAreaInteresse, formset=BaseFormSet, extra=1, max_num=10, can_delete=True)

    if request.method == 'GET':

        if request.user.is_voluntario:
            form = FormVoluntario(instance=request.user.voluntario)
            area_interesse_formset = FormSetAreaInteresse(initial=AreaInteresse.objects.filter(voluntario=request.user.voluntario).order_by('area_atuacao__nome').values('area_atuacao'))
        else:

            if msg is None:
                msg = u'Estamos cadastrando profissionais que queiram dedicar parte de seu tempo para ajudar como voluntários a quem precisa. Preencha o formulário abaixo para participar:'

            form = FormVoluntario()
            area_interesse_formset = FormSetAreaInteresse()

        if msg:
            messages.info(request, msg)
        
    if request.method == 'POST':
        agradece_cadastro = False
        if request.user.is_voluntario:
            form = FormVoluntario(request.POST, instance=request.user.voluntario)
        else:
            agradece_cadastro = True
            form = FormVoluntario(request.POST)
        if form.is_valid():
            voluntario = form.save(commit=False)
            areas_preexistentes = []
            if request.user.is_voluntario:
                areas_preexistentes = list(AreaInteresse.objects.filter(voluntario=request.user.voluntario).values_list('area_atuacao', flat=True))
            else:
                voluntario.usuario = request.user
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            if area_interesse_formset.is_valid():
                voluntario.save()
                areas_incluidas = []
                areas_selecionadas = []
                for area_interesse_form in area_interesse_formset:
                    area_atuacao = area_interesse_form.cleaned_data.get('area_atuacao')
                    if area_atuacao:
                        areas_selecionadas.append(area_atuacao.id)
                        if area_atuacao.id not in areas_preexistentes and area_atuacao.id not in areas_incluidas:
                            areas_incluidas.append(area_atuacao.id)
                            area_interesse = AreaInteresse(area_atuacao=area_atuacao, voluntario=voluntario)
                            area_interesse.save()
                        else:
                            # Ignora duplicidades e áreas já salvas
                            pass
                    else:
                        # Ignora combos vazios
                        pass
                # Apaga áreas removidas
                for area_preexistente in areas_preexistentes:
                    if area_preexistente not in areas_selecionadas:
                        try:
                            r_area = AreaInteresse.objects.get(area_atuacao=area_preexistente, voluntario=voluntario)
                            r_area.delete()
                        except AreaInteresse.DoesNotExist:
                            pass
                if agradece_cadastro:
                    # Redireciona para página de exibição de mensagem
                    messages.info(request, u'Obrigado! Assim que o seu cadastro for validado ele estará disponível para as entidades. Enquanto isso, você já pode procurar por entidades <a href="' + reverse('mapa_entidades') + '">próximas a você</a> ou que atendam a <a href="' + reverse('busca_entidades') + '">outros critérios de busca</a>.')
                    return mensagem(request, u'Cadastro de Voluntário')
                messages.info(request, u'Alterações gravadas com sucesso!')
        else:
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            
    context = {'form': form, 'area_interesse_formset': area_interesse_formset}
    template = loader.get_template('vol/formulario_voluntario.html')
    return HttpResponse(template.render(context, request))

def busca_voluntarios(request):
    '''Página para busca de voluntários'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_trabalho = AreaTrabalho.objects.all().order_by('nome')
    areas_de_interesse = AreaAtuacao.objects.all().order_by('nome')
    voluntarios = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'Envia' in request.GET:

        # Apenas voluntários cujo cadastro já tenha sido revisado e aprovado
        voluntarios = Voluntario.objects.select_related('area_trabalho', 'usuario').filter(aprovado=True)

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

        # Filtro por última atualização cadastral
        atualiza = request.GET.get('atualiza')
        if atualiza.isdigit():
            atualiza = int(atualiza)
            if atualiza in [5, 3, 2, 1]:
                now = datetime.datetime.now()
                year = datetime.timedelta(days=365)
                ref = now-atualiza*year
                voluntarios = voluntarios.filter(ultima_atualizacao__gt=ref)

        # Já inclui áreas de interesse para otimizar
        # obs: essa abordagem não funciona junto com paginação! (django 1.10.7)
        #voluntarios = voluntarios.prefetch_related('areainteresse__area_atuacao')

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
        voluntario = Voluntario.objects.select_related('area_trabalho', 'usuario').get(pk=id_voluntario, aprovado=True)
    except Voluntario.DoesNotExist:
        raise SuspiciousOperation('Voluntário inexistente ou cujo cadastro ainda não foi aprovado')
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
    # Obs: Existe pelo menos um site externo que faz buscas com POST
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_atuacao = AreaAtuacao.objects.all().order_by('id')

    buscar = False
    fasocial = fcidade = fbairro = fentidade = boxexato = entidades = params = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if request.method == 'GET':

        if 'Envia' in request.GET or 'envia' in request.GET:
            buscar = True
            fasocial = request.GET.get('fasocial')
            fcidade = request.GET.get('fcidade')
            fbairro = request.GET.get('fbairro')
            fentidade = request.GET.get('fentidade')
            params = request.GET.items()
            boxexato = 'boxexato' in request.GET
            
    if request.method == 'POST':

        if 'Envia' in request.POST or 'envia' in request.POST:
            buscar = True
            fasocial = request.POST.get('fasocial')
            fcidade = request.POST.get('fcidade')
            fbairro = request.POST.get('fbairro')
            fentidade = request.POST.get('fentidade')
            params = request.POST.items()
            boxexato = 'boxexato' in request.POST

    if buscar:

        entidades = Entidade.objects.select_related('area_atuacao').filter(confirmado=True)

        # Filtro por área de atuação
        if fasocial is not None and fasocial.isdigit() and fasocial not in [0, '0']:
            try:
                area_atuacao = AreaAtuacao.objects.get(pk=fasocial)
                if '.' in area_atuacao.indice:
                    entidades = entidades.filter(area_atuacao=fasocial)
                else:
                    entidades = entidades.filter(Q(area_atuacao=fasocial) | Q(area_atuacao__indice__startswith=str(area_atuacao.indice)+'.'))
            except AreaAtuacao.DoesNotExist:
                raise SuspiciousOperation('Área de Atuação inexistente')

        # Filtro por cidade
        if fcidade is not None:
            fcidade = fcidade.strip()
            if len(fcidade) > 0:
                if boxexato:
                    entidades = entidades.filter(cidade__iexact=fcidade)
                else:
                    entidades = entidades.filter(cidade__icontains=fcidade)

        # Filtro por bairro
        if fbairro is not None:
            fbairro = fbairro.strip()
            if len(fbairro) > 0:
                entidades = entidades.filter(bairro__icontains=fbairro)

        # Filtro por nome
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
        # Parâmetros GET na paginação
        for k, v in params:
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
        entidade = Entidade.objects.select_related('area_atuacao').get(pk=id_entidade, aprovado=True)
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

#@login_required
@transaction.atomic
def revisao_voluntarios(request):
    '''Página temporária apenas para revisar o banco de dados de voluntários e eliminar duplicidades'''
    from django.db.models import Count

    # Primeiro grava alterações se necessário
    if request.method == 'POST' and 'salvar' in request.POST:

        vol0 = Voluntario.objects.get(pk=int(request.POST.get('id0')), email=request.POST.get('email'))
        vol1 = Voluntario.objects.get(pk=int(request.POST.get('id1')), email=request.POST.get('email'))

        if request.POST.get('id') == '0':
            vol_fica = vol0
            vol_vai = vol1
        elif request.POST.get('id') == '1':
            vol_fica = vol1
            vol_vai = vol0
        else:
            raise SuspiciousOperation(u'Parâmetro id incorreto')

        campos = ['nome', 'profissao', 'data_aniversario_orig', 'ddd', 'telefone', 'cidade', 'estado', 'empresa', 'foi_voluntario', 'entidade_que_ajudou', 'area_trabalho', 'descricao']

        salvar = False

        for campo in campos:
            if request.POST.get('id') != request.POST.get(campo):
                setattr(vol_fica, campo, getattr(vol_vai, campo))
                salvar = True

        if salvar:
            vol_fica.save()

        for interesse in vol_vai.areainteresse_set.all():
            if interesse.area_atuacao not in AreaAtuacao.objects.filter(areainteresse__voluntario=vol_fica):
                interesse.voluntario = vol_fica
                interesse.save()

        vol_vai.delete()

    # Depois atualiza a contagem e pega a próxima duplicidade
    dups = Voluntario.objects.values('email').order_by('email').annotate(total=Count('email')).filter(total__gt=1)
    total = dups.count()

    dup = None
    vols = None
    i = None

    if total > 0:

        if request.method == 'GET':

            i = int(request.GET.get('i', 0))

        else:

            i = int(request.POST.get('i', 0))

            if 'pular' in request.POST:
                
                i = i + 1

        if i >= total:
            
            i = total - 1

        dup = dups[i]
        vols = Voluntario.objects.filter(email=dup['email']).order_by('data_cadastro')

    context = {'total': total,
               'dup': dup,
               'vols': vols,
               'i': i}
    template = loader.get_template('vol/revisao_voluntarios.html')
    return HttpResponse(template.render(context, request))

@login_required
def redirect_login(request):
    "Redireciona usuário após login bem sucedido"
    # Se o link original de cadastro era para voluntário
    if request.user.link == 'voluntario_novo':
        if request.user.is_voluntario:
            # Se já é voluntário, busca entidades
            return redirect(reverse('busca_entidades'))
        # Caso contrário exibe página de cadastro
        return voluntario_cadastro(request, msg=u'Para finalizar o cadatro de voluntário, complete o formulário abaixo:')
    return redirect(reverse('index'))

def anonymous_email_confirmation(request):
    "Chamado após confirmação de e-mail sem estar logado"
    messages.info(request, u'Agora você já pode identificar-se no sistema e prosseguir.')
    # Sinal para omitir link de cadastro na página de login
    request.session['omit_reg_link'] = 1
    return redirect(reverse('redirlogin'))
