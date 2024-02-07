# coding=UTF-8

import datetime
import os
import random
from math import ceil, log10
from copy import deepcopy
import urllib.parse
import urllib.request
import json

from django.shortcuts import render, redirect
from django.template import loader, engines
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseNotAllowed, HttpResponseBadRequest
from django.core.exceptions import ValidationError, SuspiciousOperation, PermissionDenied, ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import mail
from django.core.validators import URLValidator
from django.core.signing import SignatureExpired
from django.db import transaction
from django.db.models import Q, F, Count, Avg, Max, Min
from django.db.models.functions import TruncMonth, TruncWeek
from django.contrib import messages
from django.forms.formsets import BaseFormSet, formset_factory
from django.forms import inlineformset_factory
from django.conf import settings
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views import generic
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.postgres.search import SearchVector
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.utils.http import urlencode
from django.apps import apps

from .models import Voluntario, AreaTrabalho, AreaAtuacao, Entidade, VinculoEntidade, Necessidade, AreaInteresse, Telefone, Email, RemocaoUsuario, AtividadeAdmin, Usuario, ForcaTarefa, Conteudo, AcessoAConteudo, FraseMotivacional, NecessidadeArtigo, TipoArtigo, AnotacaoEntidade, Funcao, UFS, TermoAdesao, PostagemBlog, Cidade, Estado, EntidadeFavorita, StatusProcessoSeletivo, ProcessoSeletivo, ParticipacaoEmProcessoSeletivo, StatusParticipacaoEmProcessoSeletivo, MODO_TRABALHO, AreaTrabalhoEmProcessoSeletivo

from allauth.account.models import EmailAddress

from .forms import FormVoluntario, FormEntidade, FormCriarTermoAdesao, FormAssinarTermoAdesaoVol, FormAreaInteresse, FormTelefone, FormEmail, FormOnboarding, FormProcessoSeletivo, FormAreaTrabalho
from .auth import ChangeUserProfileForm

from .utils import notifica_aprovacao_voluntario

from notification.utils import notify_support, notify_email_template

def csrf_failure(request, reason=""):
    '''Erro de CSRF'''
    if settings.NOTIFY_CSRF_ERROR:
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

def escolha_cadastro(request):
    '''Página para exibir tipo de cadastro a ser feito'''
    if request.user.is_authenticated:
        msg = u'Clique na opção desejada:'
    else:
        msg = u'Clique na opção desejada. Em ambos os casos será necessário cadastrar-se antes como usuário (pessoa física).'
    messages.info(request, msg)
    template = loader.get_template('vol/escolha_cadastro.html')
    context = {}
    return HttpResponse(template.render(context, request))

def link_usuario_novo(request):
    '''Link para cadastro de novo usuário'''
    if request.user.is_authenticated:
        messages.info(request, u'<strong>Você já possui cadastro no sistema. Utilize o menu para escolher o que deseja fazer agora (ex: cadastrar um perfil de voluntário, cadastrar uma entidade, etc.).</strong>')
        # Redireciona para página de cadastro
        return redirect('/usuario')
    # Redireciona para cadastro básico
    messages.info(request, u'<strong>Para utilizar o sistema, seja como voluntário, seja como responsável por uma ou mais entidades, é preciso antes possuir um cadastro básico de usuário preenchendo os campos abaixo:</strong>')
    return redirect('/aut/signup')

@login_required
@transaction.atomic
def cadastro_usuario(request):
    template = loader.get_template('vol/formulario_usuario.html')
    if request.method == 'POST':

        if 'delete' in request.POST:
            user_email = request.user.email
            user = request.user
            logout(request)
            try:
                user.delete()
                messages.info(request, u'Seu cadastro foi totalmente removido. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.CONTACT_EMAIL + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
                try:
                    registro_remocao = RemocaoUsuario()
                    registro_remocao.save()
                    notify_email_template(user_email, u'Remoção de cadastro :-(', 'vol/msg_remocao_usuario.txt', from_email=settings.NOTIFY_USER_FROM)
                except Exception as e:
                    # Se houver erro no envio da notificação, o próprio notify_email_template já tenta avisar o suporte,
                    # portanto só cairá aqui se houver erro nas outras ações
                    pass
            except Exception as e:
                messages.warning(request, u'Não foi possível remover o seu cadastro. Caso em algum momento você tenha auxiliado na parte administrativa do site, é possível que haja referências importantes a você no histórico de nosso banco de dados. Neste caso entre em contato conosco se realmente deseja remover seu cadastro. Caso nunca tenha trabalhado na parte administrativa do site, por favor <a href="mailto:' + settings.CONTACT_EMAIL + '">entre em contato conosco</a> para verificarmos o que houve.')

            # Redireciona para página de exibição de mensagem
            return mensagem(request, u'Remoção de cadastro')
        
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
                update_session_auth_hash(request, request.user)
            request.user.save()
            messages.info(request, u'Alterações gravadas com sucesso.')
            if confirm_email:
                messages.info(request, u'Devido à troca de e-mail será necessário confirmá-lo antes de entrar novamente no sistema. Acabamos de enviar uma mensagem contendo um link para confirmação.')
                # Faz logout do usuário e não permite login até que o novo e-mail seja confirmado
                logout(request)
                # Redireciona para página de login
                return redirect('/aut/login')
    else:
        form = ChangeUserProfileForm(initial={'nome': request.user.nome, 'email': request.user.email})
    context = {'form': form}
    return HttpResponse(template.render(context, request))

def link_voluntario_novo(request):
    '''Link para cadastro de novo voluntário'''
    if request.user.is_authenticated:
        # Redireciona para página de cadastro que irá exibir formulário preenchido ou não
        return redirect('/voluntario/cadastro')
    # Indica que usuário quer se cadastrar como voluntário e redireciona para cadastro básico
    request.session['link'] = 'voluntario_novo'
    messages.info(request, u'<strong>Para cadastrar um perfil de voluntário, é preciso antes possuir um cadastro de usuário (pessoa física).</strong>')
    return redirect('/aut/signup')

@login_required
@transaction.atomic
def cadastro_voluntario(request, msg=None):
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

            #if msg is None:
            #    msg = u'Estamos cadastrando pessoas que queiram dedicar parte de seu tempo para ajudar como voluntários a quem precisa. Preencha o formulário abaixo para participar:'

            form = FormVoluntario()
            area_interesse_formset = FormSetAreaInteresse()

        if msg:
            messages.info(request, msg)

    if request.method == 'POST':
        agradece_cadastro = False
        if request.user.is_voluntario:

            if 'delete' in request.POST:
                request.user.voluntario.delete()
                del request.user.is_voluntario
                request.user.voluntario = None # Só assim para desacoplar de fato!
                # Redireciona para página de exibição de mensagem
                messages.info(request, u'Seu perfil de voluntário foi removido. Note que isto não remove seu cadastro de usuário, ou seja, você continuará podendo entrar no site, podendo inclusive cadastrar um novo perfil de voluntário quando desejar. Se a intenção for remover também seu cadastro de usuário, basta acessar sua <a href="' + reverse('cadastro_usuario') + '">página de dados pessoais</a>. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.CONTACT_EMAIL + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
                return mensagem(request, u'Remoção de Perfil de Voluntário')
            
            form = FormVoluntario(request.POST, instance=request.user.voluntario)
        else:
            agradece_cadastro = True
            form = FormVoluntario(request.POST)

        if form.is_valid():
            voluntario = form.save(commit=False) # Repare que ainda não está gravando!
            # Não sei porque esse campo fica igual a '' em alguns casos!
            if voluntario.empregado == '':
                voluntario.empregado = None
            # Ajusta conteúdos interligados
            # (apaga entidade que ajudou caso não tenha sido voluntário)
            if voluntario.entidade_que_ajudou and not voluntario.foi_voluntario:
                voluntario.entidade_que_ajudou = None
            # (apaga empresa caso não esteja empregado)
            if voluntario.empresa and voluntario.empregado == False:
                voluntario.empresa = None
            areas_preexistentes = []
            update_cache = False
            ok_idade = True
            if request.user.is_voluntario:
                areas_preexistentes = list(AreaInteresse.objects.filter(voluntario=request.user.voluntario).values_list('area_atuacao', flat=True))
            else:
                voluntario.usuario = request.user
                update_cache = True
                # Esta verificação está aqui para usufruir do método menor_de_idade, que não
                # está acessível através do FormVoluntario no momento da validação, pois ainda
                # não existe instância, além de envolver um tipo de validação que envolve dois
                # campos, sendo que o template não exibe erros gerais.
                #Note que para chegar aqui o formulário tem que ser válido!
                if voluntario.menor_de_idade() and not voluntario.ciente_autorizacao:
                    # Adicionamos um erro ao form do voluntário, mas precisamos também de uma flag para não prosseguir com a gravação
                    form.add_error('data_aniversario', u'Por ser menor de idade, faltou indicar no final do formulário que você está ciente da necessidade de autorização dos pais.')
                    ok_idade = False
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            if area_interesse_formset.is_valid() and ok_idade:
                voluntario.save()
                if update_cache:
                    del request.user.is_voluntario
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
                    # Caso haja termos de adesão sem voluntario e mas com o mesmo email do usuário, já vincula,
                    # pois já houve confirmação do email no cadastro de usuário.
                    # Obs: se o voluntário assinou um termo, removeu seu perfil, depois cadastrou de novo um perfil,
                    # vai vincular de novo também.
                    termos = TermoAdesao.objects.filter(voluntario__isnull=True, email_voluntario=request.user.email)
                    for termo in termos:
                        termo.voluntario = voluntario
                        termo.save(update_fields=['voluntario'])
                    if 'termo' in request.session:
                        # Se o cadastro foi feito em função de um termo de adesão, redireciona para o termo
                        # obs: lá ele é removido da sessão
                        try:
                            messages.info(request, u'Pronto! Você já pode preencher e assinar o termo de adesão.')
                            termo = TermoAdesao.objects.get(slug=request.session['termo'])
                            link_assinatura = termo.link_assinatura_vol(request, absolute=False)
                            return redirect(link_assinatura)
                        except TermoAdesao.DoesNotExist:
                            # Nunca deveria cair aqui...
                            messages.warning(request, u'Ops, salvamos seu perfil de voluntária(o), mas não conseguimos identificar o termo de adesão. Por favor, clique novamente no link fornecido por e-mail e caso o problema persista entre em contato conosco.')
                            return mensagem(request, u'Cadastro de Voluntário')
                    # Redireciona para página de exibição de mensagem
                    msg = u'Gravação feita com sucesso! '
                    if request.user.link and 'vaga_' in request.user.link:
                        msg = msg + u'Seus dados passarão por uma validação que normalmente leva 1 dia útil. Enviaremos uma notificação por e-mail assim que houver a aprovação, e logo em seguida você poderá se inscrever nas vagas disponíveis.'
                    else:
                        if voluntario.invisivel:
                            msg = msg + u'Seu cadastro passará por uma validação, mas você já pode usufruir de várias funcionalidades no site, como por exemplo'
                        else:
                            msg = msg + u'Assim que seu cadastro for validado, ele estará disponível para as entidades e você também poderá se inscrever em vagas de trabalho voluntário disponíveis. Enquanto isso, você já pode'
                        msg = msg + u' procurar por entidades <a href="' + reverse('mapa_entidades') + '">próximas a você</a> ou que atendam a <a href="' + reverse('busca_entidades') + '">outros critérios de busca</a>.'
                    messages.info(request, msg)
                    return mensagem(request, u'Cadastro de Voluntário')
                messages.info(request, u'Alterações gravadas com sucesso!')
        else:
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            
    context = {'form': form, 'area_interesse_formset': area_interesse_formset}
    template = loader.get_template('vol/formulario_voluntario.html')
    return HttpResponse(template.render(context, request))

def tem_acesso_a_voluntarios(request):
    '''Lógica de controle de acesso à busca e visualização de voluntários'''
    if not request.user.is_authenticated:
        messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar cadastrado no sistema como usuário, além de estar vinculado a pelo menos uma entidade com cadastro aprovado. Clique <a href="' + reverse('link_entidade_nova') + '">aqui</a> para dar início a este procedimento.')
        return False

    # Há casos especiais em que algumas pessoas podem fazer buscas através de uma permissão customizada
    if not request.user.has_perm('vol.search_volunteers'):

        # Do contrário apenas usuários com entidades aprovadas
        if not request.user.has_entidade:
            messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar vinculado a pelo menos uma entidade com cadastro aprovado. Clique <a href="' + reverse('link_entidade_nova') + '">aqui</a> para dar início a este procedimento.')
            return False

        if not request.user.has_entidade_aprovada:
            messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar vinculado a pelo menos uma entidade com cadastro aprovado. Pedimos que aguarde a aprovação da entidade cadastrada.')
            return False
    return True

def busca_voluntarios(request):
    '''Página para busca de voluntários'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    if not tem_acesso_a_voluntarios(request):
        return mensagem(request, u'Busca de voluntários')

    areas_de_trabalho = AreaTrabalho.objects.all().order_by('nome')
    areas_de_interesse = AreaAtuacao.objects.all().order_by('indice')
    voluntarios = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'Envia' in request.GET:

        # Apenas voluntários cujo cadastro já tenha sido revisado e aprovado, e sejam visíveis nas buscas
        voluntarios = Voluntario.objects.select_related('area_trabalho', 'usuario').filter(Q(invisivel=False) | Q(invisivel__isnull=True), aprovado=True)

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
                    voluntarios = voluntarios.filter(cidade__unaccent__iexact=fcidade)
                else:
                    voluntarios = voluntarios.filter(cidade__unaccent__icontains=fcidade)

        # Filtro por área de trabalho
        fareatrabalho = request.GET.get('fareatrabalho')
        if fareatrabalho.isdigit() and fareatrabalho not in [0, '0']:
            voluntarios = voluntarios.filter(area_trabalho=fareatrabalho)

        # Filtro por palavras-chave
        fpalavras = request.GET.get('fpalavras')
        if fpalavras is not None and len(fpalavras) > 0:
            # Aqui utilizamos outro queryset para evitar duplicidade de registros devido ao uso de distinct com order_by mais pra frente 
            ids = Voluntario.objects.annotate(search=SearchVector('profissao', 'descricao')).filter(search=fpalavras).distinct('pk')
            voluntarios = voluntarios.filter(pk__in=ids)

        # Filtro por última atualização cadastral
        atualiza = request.GET.get('atualiza')
        if atualiza.isdigit():
            atualiza = int(atualiza)
            if atualiza in [5, 3, 2, 1]:
                now = datetime.datetime.now()
                year = datetime.timedelta(days=365)
                ref = now-atualiza*year
                voluntarios = voluntarios.filter(ultima_atualizacao__date__gt=ref.date())

        # Já inclui áreas de interesse para otimizar
        # obs: essa abordagem não funciona junto com paginação! (django 1.10.7)
        #voluntarios = voluntarios.prefetch_related('areainteresse__area_atuacao')

        # Ordem dos resultados
        ordem = request.GET.get('ordem', 'nome')
        if ordem == 'trabalho':
            voluntarios = voluntarios.order_by('area_trabalho__nome', 'usuario__nome')
        else: # nome
            voluntarios = voluntarios.order_by('usuario__nome', 'area_trabalho__nome')
        #else: # interesse
        #    voluntarios = voluntarios.order_by('areainteresse__area_atuacao__nome', 'usuario__nome')

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
            voluntarios = paginador.page(paginador.num_pages)
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
    if not tem_acesso_a_voluntarios(request):
        return mensagem(request, u'Busca de voluntários')
    if not id_voluntario.isdigit():
        raise SuspiciousOperation('Parâmetro id inválido')
    try:
        voluntario = Voluntario.objects.select_related('area_trabalho', 'usuario').get(pk=id_voluntario, aprovado=True)
    except Voluntario.DoesNotExist:
        #raise SuspiciousOperation('Voluntário inexistente ou cujo cadastro ainda não foi aprovado')
        raise Http404
    voluntario.hit()
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

def link_entidade_nova(request):
    '''Link para cadastro de nova entidade'''
    if request.user.is_authenticated:
        # Redireciona para página de cadastro que irá exibir formulário preenchido ou não
        return redirect('/entidade/cadastro')
    # Indica que usuário quer cadastrar uma entidade e redireciona para cadastro básico
    request.session['link'] = 'entidade_nova'
    messages.info(request, u'<strong>Para cadastrar uma entidade, é preciso antes possuir um cadastro de usuário (pessoa física).</strong>')
    return redirect('/aut/signup')

def envia_confirmacao_email_entidade(request, email):
    context = {'nome': email.entidade.menor_nome(),
               'scheme': 'https' if request.is_secure() else 'http',
               'host': request.get_host(),
               'key': email.hmac_key()}
    try:
        notify_email_template(email.endereco, u'Confirmação de e-mail de entidade', 'vol/msg_confirmacao_email_entidade.txt', from_email=settings.NOTIFY_USER_FROM, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email_template já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

@login_required
def lista_entidades_vinculadas(request):
    '''Lista entidades gerenciadas pelo usuário'''
    context = {'entidades': request.user.entidades()}
    template = loader.get_template('vol/lista_entidades.html')
    return HttpResponse(template.render(context, request))

@login_required
def index_entidade(request, id_entidade):
    '''Página principal de gerenciamento de uma entidade '''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404

    # Garante que apenas usuários vinculados à entidade vejam e emitam termos de adesão
    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    processos = []

    if entidade.aprovado:

        processos = ProcessoSeletivo.objects.filter(entidade=entidade)

    context = {'entidade': entidade,
               'processos': processos}
    
    template = loader.get_template('vol/index_entidade.html')
    return HttpResponse(template.render(context, request))

@login_required
def reenvia_confirmacao_email_entidade(request, id_entidade):
    '''Reenvia mensagem de confirmação de e-mail da entidade'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        messages.error(request, u'Entidade inexistente!')
        return lista_entidades_vinculadas(request)
    # Verifica se entidade está entre as gerenciadas pelo usuário
    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        messages.error(request, u'Não é permitido enviar confirmação para esta entidade!')
        return lista_entidades_vinculadas(request)
    # Verifica se email já foi confirmado
    if entidade.email_principal_confirmado:
        messages.error(request, u'O e-mail principal da entidade já consta como confirmado!')
        return lista_entidades_vinculadas(request)
    envia_confirmacao_email_entidade(request, entidade.email_principal_obj)
    messages.info(request, u'Mensagem de confirmação reenviada para ' + entidade.email_principal + '. Verifique a caixa postal do e-mail da entidade e clique no link fornecido na mensagem.')
    # Melhor redirecionar para evitar link recarregável indesejado
    return redirect('/entidade/cadastro')

def valida_email_entidade(request):
    '''Valida e-mail de uma entidade com base no parâmetro t que deverá conter a chave HMAC da entidade.
    OBS: esta função também pode ser chamada pela interface administrativa.'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if 't' in request.GET:
        # Validação antiga, quando só havia um e-mail por entidade
        # OBS: REMOVER depois que não houver mais nenhuma entidade com
        #      validação de e-mail pendente antes de 16/02/2019
        entidade = Entidade.objects.from_hmac_key(request.GET['t'])
        if entidade is None:
            messages.error(request, u'Não foi possível validar o e-mail. Certifique-se de ter usado corretamente o link fornecido na mensagem. Na dúvida, copie o link manualmente e cole no campo de endereço do seu navegador. Se o problema persistir, entre em contato conosco.')
            return mensagem(request, u'Validação de e-mail de entidade')
        email_principal = entidade.email_principal_obj
        if not email_principal:
            messages.error(request, u'Não foi possível validar o e-mail principal desta entidade. Nossa equipe de suporte já foi notificada para verificar a situação do cadastro desta entidade.')
            notify_support(u'Entidade sem e-mail principal', str(entidade.id) + u': ' + entidade.razao_social, request)
            return mensagem(request, u'Validação de e-mail de entidade')
        email_principal.confirmado = True
        email_principal.data_confirmacao = datetime.datetime.now()
        email_principal.save(update_fields=['confirmado', 'data_confirmacao'])
    elif 'o' in request.GET:
        email = Email.objects.from_hmac_key(request.GET['o'])
        if email is None:
            messages.error(request, u'Não foi possível validar o e-mail. Certifique-se de ter usado corretamente o link fornecido na mensagem. Na dúvida, copie o link manualmente e cole no campo de endereço do seu navegador. Se o problema persistir, entre em contato conosco.')
            return mensagem(request, u'Validação de e-mail de entidade')
        email.confirmado = True
        # obs: caso já tenha sido confirmado anteriormente, atualiza data de confirmação
        email.data_confirmacao = datetime.datetime.now()
        email.save(update_fields=['confirmado', 'data_confirmacao'])
        entidade = email.entidade
    else:
        return HttpResponseBadRequest('Ausência do parâmetro token')
    msg = u'E-mail confirmado com sucesso!'
    if not entidade.aprovado:
        msg = msg + ' Agora basta aguardar a aprovação do cadastro para que a entidade apareça nas buscas.'
    messages.info(request, msg)
    return mensagem(request, u'Validação de e-mail de entidade')

@login_required
def envia_confirmacao_vinculo(request, id_entidade):
    '''Envia mensagem de confirmação de vínculo com entidade'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        messages.error(request, u'Entidade inexistente!')
        return mensagem(request, u'Solicitação de vínculo com entidade')

    # Verifica se a entidade possui e-mail
    if not entidade.email_principal:
        messages.error(request, u'Esta entidade não possui e-mail. Entre em contato conosco para resolver isso.')
        return mensagem(request, u'Solicitação de vínculo com entidade')

    # Verifica se a entidade já está entre as gerenciadas pelo usuário
    if int(id_entidade) in request.user.entidades().values_list('pk', flat=True):
        messages.error(request, u'Esta entidade já possui vínculo confirmado com você!')
        return mensagem(request, u'Solicitação de vínculo com entidade')

    # Caso não exista um vínculo pendente, cria um aguardando confirmação
    try:
        vinculo = VinculoEntidade.objects.get(usuario=request.user, entidade=entidade, data_fim__isnull=True, confirmado=False)
    except VinculoEntidade.DoesNotExist:
        vinculo = VinculoEntidade(usuario=request.user, entidade=entidade, confirmado=False)
        vinculo.save()

    # Envia mensagem de confirmação de vínculo
    context = {'usuario': request.user.nome,
               'entidade': entidade.menor_nome(),
               'scheme': 'https' if request.is_secure() else 'http',
               'host': request.get_host(),
               'key': vinculo.hmac_key()}
    try:
        notify_email_template(entidade.email_principal, u'Confirmação de vínculo com entidade', 'vol/msg_confirmacao_vinculo.txt', from_email=settings.NOTIFY_USER_FROM, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email_template já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

    messages.info(request, u'Acabamos de enviar uma mensagem para o e-mail ' + entidade.email_principal + '. Alguém com acesso à caixa postal da entidade deverá clicar no link fornecido na mensagem para confirmar a existência do seu vínculo com a entidade, permitindo que você possa editar os dados cadastrais da mesma. Entre em contato com a pessoa se necessário.')
    return mensagem(request, u'Solicitação de vínculo com entidade')

def confirma_vinculo(request):
    '''Confirma vínculo de usuário com entidade com base no parâmetro t que deverá conter a chave HMAC do vínculo.'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if 't' not in request.GET:
        return HttpResponseBadRequest('Ausência do parâmetro t')
    vinculo = VinculoEntidade.objects.from_hmac_key(request.GET['t'])
    if vinculo is None:
        messages.error(request, u'Não foi possível confirmar o vínculo com a entidade. Certifique-se de ter usado corretamente o link fornecido na mensagem. Na dúvida, copie o link manualmente e cole no campo de endereço do seu navegador. Se o problema persistir, entre em contato conosco.')
        return mensagem(request, u'Solicitação de vínculo com entidade')
    vinculo.confirmado = True
    vinculo.save(update_fields=['confirmado'])
    usuario = vinculo.usuario
    # Se houver outras entidades com o mesmo e-mail sem ninguém vinculado a elas, já cria outros vínculos com o mesmo usuário
    entidades_com_mesmo_email = Entidade.objects.filter(email_set__endereco=vinculo.entidade.email_principal).exclude(pk=vinculo.entidade.pk)
    for entidade_irma in entidades_com_mesmo_email:
        if VinculoEntidade.objects.filter(entidade=entidade_irma).count() == 0:
            novo_vinculo = VinculoEntidade(entidade=entidade_irma, usuario=usuario, confirmado=True)
            novo_vinculo.save()
    messages.info(request, u'Vínculo confirmado com sucesso! Para gerenciar o cadastro de suas entidades clique <a href="' + reverse('cadastro_entidade') + '">aqui</a>')
    return mensagem(request, u'Confirmação de vínculo com entidade')

@login_required
@transaction.atomic
def cadastro_entidade(request, id_entidade=None):
    '''Página de cadastro de entidade, podendo exibir a lista de entidades
    gerenciadas ou o formulário de edição dos dados de uma das entidades.'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    FormSetTelefone = inlineformset_factory(Entidade, Telefone, fields=('tipo', 'prefixo', 'numero',), form=FormTelefone, min_num=1, max_num=5, extra=0, validate_min=True)

    FormSetEmail = inlineformset_factory(Entidade, Email, fields=('endereco', 'principal',), form=FormEmail, min_num=1, max_num=5, extra=0, validate_min=True)

    entidade = None

    # Entidades gerenciadas pelo usuário
    entidades = request.user.entidades()

    if id_entidade is not None:

        try:
            entidade = Entidade.objects.get(pk=id_entidade)
        except Entidade.DoesNotExist:
            raise Http404

        # Garante que apenas usuários vinculados à entidade editem seus dados
        if int(id_entidade) not in entidades.values_list('pk', flat=True):
            raise PermissionDenied

    if request.method == 'GET':
        
        if entidade is not None:
            
            form = FormEntidade(instance=entidade)
            telformset = FormSetTelefone(instance=entidade)
            emailformset = FormSetEmail(instance=entidade)

        else:
            
            if 'nova' in request.GET:
                
                form = FormEntidade()
                telformset = FormSetTelefone()
                emailformset = FormSetEmail()
            else:
                
                # Exibe lista de entidades
                return lista_entidades_vinculadas(request)

    elif request.method == 'POST':

        # Entidade já cadastrada no banco
        if entidade is not None:

            if 'delete' in request.POST:
                notify_support(u'Remoção de entidade', entidade.razao_social, request)
                entidade.delete()
                # Redireciona para gerenciamento de entidades
                messages.info(request, u'Entidade removida!')
                return redirect('/entidade/cadastro')

            # ATENÇÃO: instanciar um formulário especificando o parâmetro instance
            # automaticamente atribui os valores do form à instância em questão!
            # Portanto o armazenamento de valores originais deve permanecer aqui,
            # antes de criar o formulário.
            
            # Armazena alguns valores originais pra ver se mudaram
            nome_fantasia_anterior = entidade.nome_fantasia.lower() if entidade.nome_fantasia else ''
            razao_social_anterior = entidade.razao_social.lower() if entidade.razao_social else ''
            endereco_original = entidade.endereco()
            telefones_anteriores = list(entidade.tel_set.all().order_by('id')) # força busca
            emails_anteriores = list(entidade.email_set.all().order_by('id'))  # força busca

            form = FormEntidade(request.POST, instance=entidade)
            telformset = FormSetTelefone(request.POST, request.FILES, instance=entidade)
            emailformset = FormSetEmail(request.POST, request.FILES, instance=entidade)

        else:

            # Nova entidade
            form = FormEntidade(request.POST)
            telformset = FormSetTelefone(request.POST, request.FILES)
            emailformset = FormSetEmail(request.POST, request.FILES)

        if form.is_valid() and telformset.is_valid() and emailformset.is_valid():

            # Entidade já cadastrada no banco
            if entidade is not None:

                entidade = form.save(commit=False)
                entidade.ultima_atualizacao = datetime.datetime.now()
                entidade.save()
                telformset.save()
                emailformset.save()
                # Grava manualmente os tipos de artigo aceitos como doação
                artigos_originais = form.initial['doacoes'] # ids como inteiros
                artigos_finais = form.cleaned_data['doacoes'] # objetos!
                for artigo in artigos_finais:
                    if artigo.id not in artigos_originais:
                        # Por algum motivo tem havido erro de duplicidade no create, então acrescentei
                        # mais uma verificação com o try
                        try:
                            nec = NecessidadeArtigo.objects.get(entidade=entidade, tipoartigo=artigo)
                        except NecessidadeArtigo.DoesNotExist:
                            NecessidadeArtigo.objects.create(entidade=entidade, tipoartigo=artigo, resp_cadastro=request.user)
                for artigo_id in artigos_originais:
                    artigo = TipoArtigo.objects.get(pk=artigo_id)
                    if artigo not in artigos_finais:
                        NecessidadeArtigo.objects.filter(entidade=entidade, tipoartigo=artigo).delete()

                messages.info(request, u'Alterações gravadas com sucesso!')

                num_confirmacoes = 0

                # Envia confirmação de e-mail para os novos e-mails cadastrados
                for email in emailformset.new_objects:
                    # Se o email já existe no sistema e já foi confirmado por alguém anteriormente
                    if EmailAddress.objects.filter(email__iexact=email.endereco, verified=True).count() > 0 or Email.objects.filter(endereco__iexact=email.endereco, confirmado=True).count() > 0:
                        # Confirma automaticamente
                        email.confirmado = True
                        # obs: não especifica data de confirmação quando o e-mail é confirmado "por tabela"
                        email.save(update_fields=['confirmado'])
                    else:
                        # Do contrário dispara nova confirmação de e-mail
                        envia_confirmacao_email_entidade(request, email)
                        num_confirmacoes = num_confirmacoes + 1

                # Verifica se algum email que já havia sido confirmado foi alterado
                for obj_tuple in emailformset.changed_objects:
                    if obj_tuple[0].confirmado:
                        for email_anterior in emails_anteriores:
                            if email_anterior.id == obj_tuple[0].id:
                                if email_anterior.endereco != obj_tuple[0].endereco:
                                    obj_tuple[0].confirmado = False
                                    obj_tuple[0].data_confirmacao = None
                                    obj_tuple[0].save(update_fields=['confirmado', 'data_confirmacao'])
                                    envia_confirmacao_email_entidade(request, obj_tuple[0])
                                    num_confirmacoes = num_confirmacoes + 1
                                break

                if num_confirmacoes > 1:
                    messages.info(request, u'Foram enviadas mensagens de confirmação para e-mails novos ou alterados. Verifique a caixa postal para efetuar a validação deles.')
                elif num_confirmacoes > 0:
                    messages.info(request, u'Foi enviada uma mensagem de confirmação para o e-mail novo ou alterado. Verifique a caixa postal para efetuar a validação do mesmo.')

                # Força reaprovação de cadastro caso dados importantes tenham mudado
                #if entidade.aprovado and (nome_fantasia_anterior != request.POST['nome_fantasia'].lower() or razao_social_anterior != request.POST['razao_social'].lower()):
                #    entidade.aprovado = None
                #    entidade.save(update_fields=['aprovado'])
                #    messages.warning(request, u'Atenção: a alteração no nome dá início a uma nova etapa de revisão/aprovação do cadastro da entidade. Aguarde a aprovação para que a entidade volte a aparecer nas buscas.')

                # Caso tenha alterado o endereço, tenta georreferenciar novamente
                if endereco_original != entidade.endereco():
                    entidade.geocode()

                # Caso tenha alterado telefone aprovado, notifica alteração
                houve_mudanca = False
                telefones_atuais = entidade.tel_set.all().order_by('id')
                for tel in telefones_atuais:
                    if tel.confirmado:
                        for tel_orig in telefones_anteriores:
                            if tel_orig.id == tel.id:
                                if tel.mudou_numero(tel_orig):
                                    houve_mudanca = True
                                    tel.confirmado = False
                                    tel.confirmado_por = None
                                    tel.data_confirmacao = None
                                    tel.save(update_fields=['confirmado', 'confirmado_por', 'data_confirmacao'])
                                break
                if houve_mudanca:
                    notify_email_template(settings.NOTIFY_USER_FROM, u'Alteração de telefone', 'vol/msg_alteracao_telefone.txt', from_email=settings.NOTIFY_USER_FROM, context={'entidade': entidade, 'telefones_anteriores': telefones_anteriores, 'telefones_atuais': telefones_atuais})

            # Nova entidade
            else:

                # Aqui tb é necessário usar commit=False, do contrário o Django vai automaticamente tentar salvar
                # as doações através do save_m2m interno e vai dar erro, porque temos campos extras
                entidade = form.save(commit=False)
                entidade.save()
                telformset.instance = entidade
                telformset.save()
                emailformset.instance = entidade
                emailformset.save()
                # Grava manualmente os tipos de artigo aceitos como doação
                for artigo in form.cleaned_data['doacoes']:
                    NecessidadeArtigo.objects.create(entidade=entidade, tipoartigo=artigo, resp_cadastro=request.user)

                msg = u'Entidade cadastrada com sucesso!'

                num_confirmacoes = 0

                # Trata novos e-mails
                for email in emailformset.new_objects:
                    # Se o email já existe no sistema e já foi confirmado por alguém anteriormente
                    if EmailAddress.objects.filter(email__iexact=email.endereco, verified=True).count() > 0 or Email.objects.filter(endereco__iexact=email.endereco, confirmado=True).count() > 0:
                        # Confirma automaticamente
                        email.confirmado = True
                        # obs: não especifica data de confirmação quando o e-mail é confirmado "por tabela"
                        email.save(update_fields=['confirmado'])

                    else:
                
                        # Do contrário dispara nova confirmação de e-mail
                        envia_confirmacao_email_entidade(request, email)
                        num_confirmacoes = num_confirmacoes + 1

                if num_confirmacoes > 0:
                    if num_confirmacoes > 1:
                        msg = msg + u' Foram enviadas mensagens de confirmação para os e-mails cadastrados. Acesse a caixa postal deles para validá-los. Caso não tenha recebido, verifique a pasta de spam ou clique no botão "reenviar" abaixo em se tratando do e-mail principal.'
                    else:
                        msg = msg + u' Foi enviada uma mensagem de confirmação para o e-mail cadastrado. Acesse a caixa postal dele para validá-lo. Caso não tenha recebido, verifique a pasta de spam ou clique no botão "reenviar" abaixo.'
                else:
                    msg = msg + u' Aguarde a aprovação do cadastro para que ela comece a aparecer nas buscas.'

                messages.info(request, msg)

                # Tenta georeferenciar
                entidade.geocode()
                
                # Vincula usuário à entidade
                vinculo = VinculoEntidade(usuario=request.user, entidade=entidade, confirmado=True)
                vinculo.save()

            # Garante apenas um e-mail principal por entidade
            entidade.verifica_email_principal()

            # Exibe lista de entidades
            return redirect('/entidade/cadastro')

    # Exibe formulário de cadastro de entidade
    context = {'form': form,
               'telformset': telformset,
               'emailformset': emailformset,
               'entidade': form.instance}
    template = loader.get_template('vol/formulario_entidade.html')
    return HttpResponse(template.render(context, request))

@login_required
def termos_de_adesao_de_entidade(request, id_entidade):
    '''Exibe lista de termos de adesão da entidade'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404

    # Garante que apenas usuários vinculados à entidade vejam e emitam termos de adesão
    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    termos = TermoAdesao.objects.filter(entidade=entidade).order_by('-data_cadastro')

    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)

    context = {'entidade': entidade,
               'termos': termos,
               'hoje': now.date()}
    template = loader.get_template('vol/termos_de_adesao_de_entidade.html')
    return HttpResponse(template.render(context, request))

@login_required
def termos_de_adesao_de_voluntario(request):
    '''Exibe lista de termos de adesão do voluntário'''
    termos = TermoAdesao.objects.none()
    if request.user.is_voluntario:
        termos = TermoAdesao.objects.filter(voluntario=request.user.voluntario).order_by('-data_cadastro')

    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)

    context = {'termos': termos,
               'hoje': now.date()}
    template = loader.get_template('vol/termos_de_adesao_de_voluntario.html')
    return HttpResponse(template.render(context, request))

@login_required
@transaction.atomic
def enviar_termo_de_adesao(request, slug_termo):
    '''Envia termo de adesão para voluntário'''
    try:
        termo = TermoAdesao.objects.get(slug=slug_termo)
    except TermoAdesao.DoesNotExist:
        raise Http404

    if termo.entidade_id not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    termo.enviar_para_voluntario(request)

    return redirect(reverse('termos_de_adesao_de_entidade', kwargs={'id_entidade': termo.entidade_id}))

@login_required
@transaction.atomic
def cancelar_termo_de_adesao(request, slug_termo):
    '''Cancela termo de adesão para voluntário'''
    if request.method != 'POST':
        return HttpResponseNotAllowed(metodos)

    try:
        termo = TermoAdesao.objects.get(slug=slug_termo)
    except TermoAdesao.DoesNotExist:
        raise Http404

    # termos só pode ser cancelados pela entidade, quando o voluntário ainda não assinou
    if termo.entidade_id not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    if termo.data_aceitacao_vol is not None:
        messages.error(request, u'Não é possível excluir termos de adesão que já foram aceitos pelo voluntário. Utilize a opção rescindir.')
    else:
        termo.delete()
        messages.info(request, u'Termo de adesão excluído com sucesso.')

    return redirect(reverse('termos_de_adesao_de_entidade', kwargs={'id_entidade': termo.entidade_id}))

@login_required
@transaction.atomic
def rescindir_termo_de_adesao(request, slug_termo):
    '''Rescinde termo de adesão para voluntário'''
    if request.method != 'POST':
        return HttpResponseNotAllowed(metodos)

    try:
        termo = TermoAdesao.objects.get(slug=slug_termo)
    except TermoAdesao.DoesNotExist:
        raise Http404

    motivo = request.POST.get('motivo')

    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)

    # termos só podem ser rescindidos pela entidade ou pelo próprio voluntário
    rescisao_pela_entidade = None
    if termo.voluntario is not None and request.user == termo.voluntario.usuario:
        rescisao_pela_entidade = False
    elif termo.entidade_id in request.user.entidades().values_list('pk', flat=True):
        rescisao_pela_entidade = True
    else:
        raise PermissionDenied

    if termo.data_aceitacao_vol is None:
        messages.error(request, u'Não é possível rescindir termos de adesão que sequer foram aceitos pelo voluntário. Utilize a opção cancelar.')
    elif termo.data_fim and termo.data_fim <= now.date():
        messages.error(request, u'Não é possível rescindir termos de adesão que já expiraram.')
    elif termo.data_rescisao is not None:
        messages.error(request, u'Não é possível rescindir termos de adesão que já foram rescindidos.')
    elif not motivo:
        messages.error(request, u'É necessário informar o motivo da rescisão.')
    else:
        termo.data_rescisao = timezone.now()
        termo.resp_rescisao = request.user
        termo.nome_resp_rescisao = request.user.nome
        termo.motivo_rescisao = motivo
        termo.save()

        # Notifica a outra parte sobre a rescisão
        dest = None
        if rescisao_pela_entidade:
            # rescisão sendo feita pela entidade
            dest = termo.email_voluntario
        else:
            # rescisão sendo feita pelo voluntário
            if termo.entidade: # pode ser que a entidade tenha sido removida!
                dest = termo.entidade.email_principal

        if dest:

            context = {'nome_voluntario': termo.nome_voluntario,
                       'nome_entidade': termo.nome_entidade,
                       'nome_resp_rescisao': request.user.nome,
                       'data_rescisao': termo.data_rescisao,
                       'motivo_rescisao': motivo}
            
            try:
                notify_email_template(dest, u'Rescisão de termo de adesão', 'vol/msg_rescisao.txt', from_email=settings.NOTIFY_USER_FROM, context=context)
            except Exception as e:
                # Se houver erro o próprio notify_email_template já tenta notificar o suporte,
                # portanto só cairá aqui se houver erro na notificação ao suporte
                pass
        
        messages.info(request, u'Termo de adesão rescindido com sucesso.')

    if 'Referer' in request.headers and 'entidade' in request.headers['Referer']:
        return redirect(reverse('termos_de_adesao_de_entidade', kwargs={'id_entidade': termo.entidade_id}))

    return redirect(reverse('termos_de_adesao_de_voluntario'))

@login_required
@transaction.atomic
def novo_termo_de_adesao(request, id_entidade):
    '''Novo termo de adesão para voluntário'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404

    # Garante que apenas usuários vinculados à entidade vejam e emitam termos de adesão
    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    if request.method == 'POST':

        form = FormCriarTermoAdesao(request.POST)

        if form.is_valid():
            ok = False
            # Validações que dependem da entidade
            if entidade.cnpj_valido():
                if form.cleaned_data['sou_responsavel'] == 'False':
                    messages.error(request, u'Para emitir termos na versão atual do sistema é necessário ser responsável legal pela entidade. Entre em contato conosco se isto for um problema.')
                else:
                    ok = True
            else:
                if form.cleaned_data['tem_responsavel'] is None:
                    messages.error(request, u'Favor indicar se você deseja constar como responsável por parte da entidade neste termo.')
                else:
                    ok = True

            if ok:
                enviados = []
                for email in form.cleaned_data['email_voluntarios'].lower().replace(' ', '').split(','):
                    # Evita criar mais de um termo para a mesma pessoa caso esteja repetida na lista
                    if email not in enviados:
                        novo_termo = TermoAdesao(entidade=entidade,
                                                 nome_entidade=entidade.razao_social,
                                                 cnpj_entidade=entidade.cnpj,
                                                 endereco_entidade=entidade.endereco(),
                                                 email_voluntario=email,
                                                 condicoes=form.cleaned_data['condicoes'],
                                                 atividades=form.cleaned_data['atividades'],
                                                 texto_aceitacao=form.cleaned_data['texto_aceitacao'],
                                                 data_inicio=form.cleaned_data['data_inicio'],
                                                 data_fim=form.cleaned_data['data_fim'],
                                                 carga_horaria=form.cleaned_data['carga_horaria'],
                                                 resp_cadastro=request.user,
                                                 nome_resp_cadastro=request.user.nome)
                        if entidade.cnpj_valido():
                            # Se a entidade possui existência formal, assume que o usuário é representante legal
                            novo_termo.resp_entidade = request.user
                            novo_termo.nome_resp_entidade = request.user.nome
                        else:
                            # Caso contrário, somente registra o usuário como responsável se ele quiser
                            if form.cleaned_data['tem_responsavel'] == 'True':
                                novo_termo.resp_entidade = request.user
                                novo_termo.nome_resp_entidade = request.user.nome
                        # Se já houver um voluntário cadastrado no sistema com o e-mail, vincula ele ao termo
                        try:
                            voluntario = Voluntario.objects.get(usuario__email=email)
                            novo_termo.voluntario = voluntario
                        except Voluntario.DoesNotExist:
                            pass # sem problema
                        novo_termo.save()
                        novo_termo.enviar_para_voluntario(request)
                        enviados.append(email)
                return redirect(reverse('termos_de_adesao_de_entidade', kwargs={'id_entidade': id_entidade}))
    else:

        condicoes_default = "Pelo presente Termo de Adesão e ciente da Lei n. 9.608/1998 que rege o trabalho voluntário, decido espontaneamente realizar atividade voluntária nesta organização.\nDeclaro, ainda, que estou ciente de que o trabalho não será remunerado e que não configurará vínculo empregatício ou gerará qualquer obrigação de natureza trabalhista, previdenciária ou afim.\nDeclaro, por fim, que estou ciente de que eventuais danos pessoais ou materiais causados no exercício do trabalho voluntário serão de total e integral responsabilidade minha e não serão imputados à esta organização."
        texto_aceitacao_default = "Declaro estar de acordo com todas as condições deste termo e que as informações por mim prestadas estão completas e são verdadeiras."
        
        termos = TermoAdesao.objects.filter(entidade=entidade).order_by('-data_cadastro')
        if len(termos) > 0:
            ultimo_termo = termos[0]
            condicoes_default = ultimo_termo.condicoes
            texto_aceitacao_default = ultimo_termo.texto_aceitacao
        
        form = FormCriarTermoAdesao(initial={'condicoes': condicoes_default, 'texto_aceitacao': texto_aceitacao_default})

    context = {'entidade': entidade,
               'form': form}
    template = loader.get_template('vol/formulario_criacao_termo_de_adesao.html')
    return HttpResponse(template.render(context, request))

def termo_de_adesao(request, slug_termo):
    '''Exibe termo de adesão'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    try:
        termo = TermoAdesao.objects.get(slug=slug_termo)
    except Entidade.DoesNotExist:
        raise Http404

    if termo.data_aceitacao_vol is None:
        # Caso o termo ainda não tenha sido aceito
        if request.user.is_authenticated and termo.email_voluntario == request.user.email:
            link_assinatura = termo.link_assinatura_vol(request, absolute=False)
            return redirect(link_assinatura)
        return mensagem(request, u'Este termo ainda não foi aceito. Se ele estiver relacionado a você, utilize o link fornecido por e-mail para poder acessá-lo.')

    contexto = request.GET.get('contexto')

    exibir_no_contexto_do_voluntario = None
    entidade = None
    if contexto == 'voluntario':
        exibir_no_contexto_do_voluntario = True
    elif contexto == 'entidade':
        # Exibe o termo no contexto da entidade somente se o usuário estiver vinculado à entidade
        if request.user.is_authenticated and termo.entidade.id in request.user.entidades().values_list('pk', flat=True):
            exibir_no_contexto_do_voluntario = False
            entidade = termo.entidade

    if 'print' in request.GET:
        template = loader.get_template('vol/termo_de_adesao_para_impressao.html')
    else:
        template = loader.get_template('vol/termo_de_adesao.html')

    context = {'termo': termo,
               'exibir_no_contexto_do_voluntario': exibir_no_contexto_do_voluntario,
               'entidade': entidade}

    return HttpResponse(template.render(context, request))

def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def assinatura_vol_termo_de_adesao(request):
    '''Assinatura do termo de adesão pelo voluntário'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if request.method == 'GET':
        if 'h' not in request.GET:
            return HttpResponseBadRequest('Ausência do parâmetro h')
        hmac_key = request.GET['h']
    if request.method == 'POST':
        if 'h' not in request.POST:
            return HttpResponseBadRequest('Ausência do parâmetro h')
        hmac_key = request.POST['h']
    try:
        termo = TermoAdesao.objects.from_hmac_key(hmac_key)
    except SignatureExpired:
        messages.error(request, u'O prazo para confirmar este termo de adesão expirou. Favor solicitar a emissão de novo termo junto à entidade emissora.')
        return mensagem(request, u'Assinatura de termo de adesão')
    if termo is None:
        messages.error(request, u'Não foi possível localizar este termo de adesão. Certifique-se de ter usado corretamente o link fornecido na mensagem. Na dúvida, copie o link manualmente e cole no campo de endereço do seu navegador. Caso você tenha recebido a notificação há muito tempo, pode ser também que a entidade tenha cancelado o termo de adesão, portanto também vale a pena confirmar com a entidade se o termo continua disponível, ou se é necessário emitir um novo termo. Se precisar de ajuda, entre em contato conosco.')
        return mensagem(request, u'Assinatura de termo de adesão')
    if termo.data_aceitacao_vol is not None:
        # Se o termo já foi aceito, simplesmente exibe ele
        messages.info(request, u'Este termo de adesão já foi aceito.')
        return termo_de_adesao(request, termo.slug)
    if not request.user.is_authenticated:
        # Redireciona para página de cadastro de usuário
        messages.info(request, u'Para visualizar e aceitar o termo de adesão, é preciso possuir cadastro no sistema juntamente com um perfil de voluntário. Se você já possui cadastro, faça o login, caso contrário clique no link para se cadastrar e depois siga as instruções.')
        link_assinatura = termo.link_assinatura_vol(request, absolute=False)
        request.session['termo'] = termo.slug
        return redirect('/aut/login' + '?next=' + link_assinatura)
    if not request.user.is_voluntario:
        # Redireciona para página de cadastro de voluntário
        messages.info(request, u'Para visualizar e aceitar o termo de adesão, é preciso possuir um perfil de voluntário cadastrado no sistema. Complete o formulário abaixo para em seguida visualizar o termo.')
        if 'termo' not in request.session:
            request.session['termo'] = termo.slug
        return redirect('/voluntario/cadastro')

    if 'termo' in request.session:
        # Neste ponto esta variável não é mais necessária
        del request.session['termo']
        request.session.modified = True

    # Assume que o usuário que possui o link de assinatura é quem está logado
    voluntario = request.user.voluntario

    ip = _get_client_ip(request)

    if request.method == 'POST':

        form = FormAssinarTermoAdesaoVol(request.POST)

        if form.is_valid():

            termo.voluntario = voluntario
            termo.nome_voluntario = request.user.nome # fixo
            termo.nascimento_voluntario = voluntario.data_aniversario # fixo
            termo.profissao_voluntario = form.cleaned_data['profissao_voluntario']
            termo.nacionalidade_voluntario = form.cleaned_data['nacionalidade_voluntario']
            termo.tipo_identif_voluntario = form.cleaned_data['tipo_identif_voluntario']
            termo.identif_voluntario = form.cleaned_data['identif_voluntario']
            termo.cpf_voluntario = form.cleaned_data['cpf_voluntario']
            termo.estado_civil_voluntario = form.cleaned_data['estado_civil_voluntario']
            termo.endereco_voluntario = form.cleaned_data['endereco_voluntario']
            termo.ddd_voluntario = form.cleaned_data['ddd_voluntario']
            termo.telefone_voluntario = form.cleaned_data['telefone_voluntario']
            termo.ip_aceitacao_vol = ip
            termo.data_aceitacao_vol = timezone.now()
            
            termo.save()
            messages.info(request, u'Termo de adesão aceito com sucesso!')
            return redirect(reverse('termo_de_adesao', kwargs={'slug_termo': termo.slug}))
    else:

        # termos já preenchidos pelo usuário
        termos = TermoAdesao.objects.filter(voluntario=voluntario, data_aceitacao_vol__isnull=False).order_by('-data_cadastro')
        if len(termos) > 0:
            ultimo_termo = termos[0]
            profissao_voluntario = ultimo_termo.profissao_voluntario
            nacionalidade_voluntario = ultimo_termo.nacionalidade_voluntario
            tipo_identif_voluntario = ultimo_termo.tipo_identif_voluntario
            identif_voluntario = ultimo_termo.identif_voluntario
            cpf_voluntario = ultimo_termo.cpf_voluntario
            estado_civil_voluntario = ultimo_termo.estado_civil_voluntario
            endereco_voluntario = ultimo_termo.endereco_voluntario
            ddd_voluntario = ultimo_termo.ddd_voluntario
            telefone_voluntario = ultimo_termo.telefone_voluntario
        else:
            profissao_voluntario = voluntario.profissao
            nacionalidade_voluntario = u'brasileira'
            tipo_identif_voluntario = 'RG'
            identif_voluntario = ''
            cpf_voluntario = ''
            estado_civil_voluntario = None
            endereco_voluntario = u'???, ' + voluntario.cidade + ', ' + voluntario.estado
            ddd_voluntario = voluntario.ddd
            telefone_voluntario = voluntario.telefone

        form = FormAssinarTermoAdesaoVol(initial={'profissao_voluntario': profissao_voluntario,
                                                  'nacionalidade_voluntario': nacionalidade_voluntario,
                                                  'tipo_identif_voluntario': tipo_identif_voluntario,
                                                  'identif_voluntario': identif_voluntario,
                                                  'cpf_voluntario': cpf_voluntario,
                                                  'estado_civil_voluntario': estado_civil_voluntario,
                                                  'endereco_voluntario': endereco_voluntario,
                                                  'ddd_voluntario': ddd_voluntario,
                                                  'telefone_voluntario': telefone_voluntario})

    context = {'hmac_key': hmac_key,
               'termo': termo,
               'voluntario': voluntario,
               'form': form,
               'ip': ip}
    template = loader.get_template('vol/formulario_aceitacao_vol_termo_de_adesao.html')
    return HttpResponse(template.render(context, request))

def busca_entidades(request):
    '''Página de busca de entidades'''
    # Obs: Existe pelo menos um site externo que faz buscas com POST
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_atuacao = AreaAtuacao.objects.all().order_by('indice')
    tipos_de_artigo = TipoArtigo.objects.all().order_by('ordem')

    buscar = False
    fasocial = fcidade = fbairro = fentidade = boxexato = entidades = params = atualiza = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if request.method == 'GET':

        if 'Envia' in request.GET or 'envia' in request.GET:
            buscar = True
            fasocial = request.GET.get('fasocial')
            fcidade = request.GET.get('fcidade')
            fbairro = request.GET.get('fbairro')
            fentidade = request.GET.get('fentidade')
            ftipoartigo = request.GET.get('ftipoartigo')
            params = request.GET.items()
            boxexato = 'boxexato' in request.GET
            atualiza = request.GET.get('atualiza')
            
    if request.method == 'POST':

        if 'Envia' in request.POST or 'envia' in request.POST:
            buscar = True
            fasocial = request.POST.get('fasocial')
            fcidade = request.POST.get('fcidade')
            fbairro = request.POST.get('fbairro')
            fentidade = request.POST.get('fentidade')
            ftipoartigo = request.POST.get('ftipoartigo')
            params = request.POST.items()
            boxexato = 'boxexato' in request.POST
            atualiza = request.POST.get('atualiza')

    if buscar:

        entidades = Entidade.objects.select_related('area_atuacao').filter(aprovado=True)

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

        # Filtro por tipo de artigo
        if ftipoartigo is not None and ftipoartigo.isdigit() and ftipoartigo not in [0, '0']:
            try:
                tipo_artigo = TipoArtigo.objects.get(pk=ftipoartigo)
                entidades = entidades.filter(doacoes=ftipoartigo)
            except TipoArtigo.DoesNotExist:
                raise SuspiciousOperation('Tipo de artigo não aceito pelo sistema.')

        # Filtro por cidade
        if fcidade is not None:
            fcidade = fcidade.strip()
            if len(fcidade) > 0:
                # Obs: unaccent deve vir antes dos outros operadores!
                if boxexato:
                    entidades = entidades.filter(cidade__unaccent__iexact=fcidade)
                else:
                    entidades = entidades.filter(cidade__unaccent__icontains=fcidade)

        # Filtro por bairro
        if fbairro is not None:
            fbairro = fbairro.strip()
            if len(fbairro) > 0:
                entidades = entidades.filter(bairro__unaccent__icontains=fbairro)

        # Filtro por nome
        if fentidade is not None:
            fentidade = fentidade.strip()
            if len(fentidade) > 0:
                entidades = entidades.filter(Q(nome_fantasia__unaccent__icontains=fentidade) | Q(razao_social__unaccent__icontains=fentidade))

        # Filtro por data de última atualização
        if atualiza is not None and atualiza.isdigit():
            atualiza = int(atualiza)
            if atualiza in [3, 2, 1]:
                now = datetime.datetime.now()
                year = datetime.timedelta(days=365)
                ref = now-atualiza*year
                entidades = entidades.filter(ultima_atualizacao__date__gt=ref.date())

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
            entidades = paginador.page(paginador.num_pages)
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
               'tipos_de_artigo': tipos_de_artigo,
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
        #raise SuspiciousOperation('Entidade inexistente')
        raise Http404

    entidade.hit()

    processos_abertos = ProcessoSeletivo.objects.filter(entidade_id=entidade, status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES).order_by('titulo')
    
    dois_meses_atras = timezone.now() - datetime.timedelta(days=60)
    necessidades = entidade.necessidade_set.filter(data_solicitacao__gt=dois_meses_atras).order_by('-data_solicitacao')

    now = datetime.datetime.now()
    favorita = False
    if request.user.is_authenticated and request.user.is_voluntario:
        try:
            EntidadeFavorita.objects.get(voluntario=request.user.voluntario, entidade_id=entidade, fim__isnull=True)
            favorita = True
        except EntidadeFavorita.DoesNotExist:
            pass

    context = {'entidade': entidade,
               'agora': now,
               'processos_abertos': processos_abertos,
               'necessidades': necessidades,
               'favorita': favorita}
    template = loader.get_template('vol/exibe_entidade.html')
    return HttpResponse(template.render(context, request))

def exibe_entidade_old(request):
    '''Detalhes de entidade usando URL antiga'''
    if 'colocweb' not in request.GET:
        return HttpResponseBadRequest('Ausência do parâmetro colocweb')
    id_entidade = request.GET.get('colocweb')
    return exibe_entidade(request, id_entidade)

@cache_page(60 * 60 * 24) # timeout: 24h
def entidades_kml(request, id_last):
    '''KML de todas as Entidades. Obs: não usamos mais o KML, e sim o json gerado no próximo método.'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    entidades_georref = Entidade.objects.filter(coordenadas__isnull=False, aprovado=True)
    context = {'entidades': entidades_georref}
    return render(request, 'vol/entidades.kml', context=context, content_type='application/vnd.google-earth.kml+xml; charset=utf-8')

@cache_page(60 * 60 * 24) # timeout: 24h
def entidades_points(request):
    '''Localização geográfica de todas as Entidades'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    entidades_georref = Entidade.objects.filter(coordenadas__isnull=False, aprovado=True)
    context = {'entidades': entidades_georref}
    return render(request, 'vol/entidades.json', context=context, content_type='application/json; charset=utf-8')

def busca_doacoes(request):
    '''Página de busca de doações'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    doacoes = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'pesquisa_ajuda' in request.GET or 'pesquisa_entidade' in request.GET:

        doacoes = Necessidade.objects.select_related('entidade').filter(entidade__isnull=False, entidade__aprovado=True)

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
            doacoes = paginador.page(paginador.num_pages)
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
    context = {'GOOGLE_MAPS_API_KEY':settings.GOOGLE_MAPS_API_KEY}
    template = loader.get_template('vol/mapa_entidades.html')
    return HttpResponse(template.render(context, request))

@login_required
def mural(request):
    '''Página para exibir frases de voluntários'''
    notify_support(u'Acesso ao mural!!', request.user.email, request)
    context = {}
    template = loader.get_template('vol/mural.html')
    return HttpResponse(template.render(context, request))

@login_required
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
                         'idade': vol.idade_str(),
                         'cidade': vol.cidade.title(),
                         'estado': vol.estado.upper()})

def exibir_charada(request):
    # Código propositalmente ofuscado para gerar koan de teste de instalação
    d = {}
    for c in (65, 97):
        for i in range(26):
            d[chr(i+c)] = chr((i+13) % 26 + c)
    s = 'Fr pubirffr cnynien, rz qvn qr fby avathrz snynevn!'
    if settings.DEBUG:
        cod = "".join([d.get(c, c) for c in s])
        return HttpResponse(cod + '<small> (copie o texto ao lado e cole na <a href="mailto:tecno' + '@' + 'voluntarios.com.br?subject=Ticket%20para%20a%20equipe%20de%20TI">seguinte mensagem</a>)</small>')
    return redirect('/')

@login_required
def redirect_login(request):
    "Redireciona usuário após login bem sucedido quando não há o parâmetro next"
    # Se o link original de cadastro era para voluntário
    if request.user.link == 'voluntario_novo':
        if request.user.is_voluntario:
            # Se já é voluntário, busca entidades
            return redirect(reverse('busca_entidades'))
        # Caso contrário exibe página de cadastro
        return cadastro_voluntario(request, msg=u'Para finalizar o cadastro de voluntário, complete o formulário abaixo:')
    elif request.user.link == 'entidade_nova':
        if request.user.is_voluntario:
            # Existem casos de voluntários que se cadastram pelo caminho de entidades.
            # Nestes casos, ao cadastrar um perfil de voluntário, melhor parar de redirecionar
            # para a página de gerenciamento de entidades, redirecionando para busca de entidades
            return redirect(reverse('busca_entidades'))
        else:
            # Independente do usuário possuir entidade cadastrada, redireciona para página
            # de gerenciamento de entidades, onde pode-se atualizar ou cadastrar entidades
            return cadastro_entidade(request)
    elif request.user.link and 'vaga_' in request.user.link:
        if not request.user.is_voluntario:
            # Se ainda não for voluntário, exibe página de cadastro
            # obs: precisamos verificar isso aqui, pois a query mais abaixo só funciona para voluntários
            return cadastro_voluntario(request, msg=u'Para finalizar o cadastro de voluntário e poder se inscrever em vagas disponíveis após aprovação do cadastro (normalmente leva 1 dia útil), complete o formulário abaixo:')
        codigo_processo = request.user.codigo_de_processo_seletivo_de_entrada()
        try:
            processo = ProcessoSeletivo.objects.get(codigo=codigo_processo)
            if processo.inscricoes_abertas() and ParticipacaoEmProcessoSeletivo.objects.filter(processo_seletivo=processo, voluntario=request.user.voluntario).count() == 0:
                # Se a seleção ainda está aberta e o voluntário não se inscreveu,
                # vai para a página do processo seletivo, com todas as verificações que são feitas lá
                return exibe_processo_seletivo(request, codigo_processo)
        except ProcessoSeletivo.DoesNotExist:
            pass
        # Utiliza busca de vagas como página default
        return redirect(reverse('busca_vagas'))

    if 'link' in request.session:
        if request.session['link'] == 'entidade_nova':
            del request.session['link']
            request.session.modified = True
            return cadastro_entidade(request)
    return redirect(reverse('index'))

def anonymous_email_confirmation(request):
    "Chamado após confirmação de e-mail sem estar logado"
    messages.info(request, u'Agora você já pode identificar-se no sistema e prosseguir.')
    # Sinal para omitir link de cadastro na página de login
    request.session['omit_reg_link'] = 1
    if 'termo' in request.session:
        try:
            termo = TermoAdesao.objects.get(slug=request.session['termo'])
            link_assinatura = termo.link_assinatura_vol(request, absolute=False)
        except TermoAdesao.DoesNotExist:
            # Nunca deveria cair aqui...
            pass
        if link_assinatura:
            return redirect('/aut/login' + '?next=' + link_assinatura)
    return redirect(reverse('redirlogin'))

@login_required
def indicadores(request):
    '''Página para exibir indicadores do site'''
    if not request.user.is_staff:
        raise PermissionDenied
    
    # Histórico de voluntários cadastrados
    vols = Voluntario.objects.filter(aprovado=True).annotate(cadastro=TruncMonth('data_cadastro')).values('cadastro').annotate(cnt=Count('id')).order_by('cadastro')
    vols_labels = ''
    vols_values = ''
    total = 0
    n = 0
    for vol in vols:
        if n > 0:
            vols_labels = vols_labels + ','
            vols_values = vols_values + ','
        # label = mês / ano
        vols_labels = vols_labels + "'" + str(vol['cadastro'].month) + '/' + str(vol['cadastro'].year) + "'"
        # Acumula valores
        total = total + vol['cnt']
        vols_values = vols_values + str(total)
        n = n + 1

    # Histórico de entidades cadastradas
    ents = Entidade.objects.filter(aprovado=True, data_cadastro__isnull=False).annotate(cadastro=TruncMonth('data_cadastro')).values('cadastro').annotate(cnt=Count('id')).order_by('cadastro')
    ents_labels = ''
    ents_values = ''
    total = Entidade.objects.filter(aprovado=True, data_cadastro__isnull=True).count()
    n = 0
    for ent in ents:
        if n > 0:
            ents_labels = ents_labels + ','
            ents_values = ents_values + ','
        # label = mês / ano
        ents_labels = ents_labels + "'" + str(ent['cadastro'].month) + '/' + str(ent['cadastro'].year) + "'"
        # Acumula valores
        total = total + ent['cnt']
        ents_values = ents_values + str(total)
        n = n + 1

    context = {'vols_labels': vols_labels,
               'vols_values': vols_values,
               'ents_labels': ents_labels,
               'ents_values': ents_values}
    template = loader.get_template('vol/indicadores.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
@transaction.atomic
def aprovacao_voluntarios(request):
    '''Página para revisar novos cadastros de voluntários'''

    # Controle de exibição da página sobre o compromisso de privacidade
    try:
        atividade_admin = request.user.atividadeadmin
    except ObjectDoesNotExist:
        atividade_admin = AtividadeAdmin(usuario=request.user)
        atividade_admin.save()

    if atividade_admin.ciencia_privacidade is None:
        
        if request.method == 'POST' and 'ciente' in request.POST:

            atividade_admin.ciencia_privacidade = timezone.now()
            atividade_admin.save(update_fields=['ciencia_privacidade'])
        else:
            
            template = loader.get_template('vol/ciencia_privacidade.html')
            return HttpResponse(template.render({}, request))

    # Controle de exibição das orientações
    if atividade_admin.viu_instrucoes_vol is None:
        
        atividade_admin.viu_instrucoes_vol = timezone.now()
        atividade_admin.save(update_fields=['viu_instrucoes_vol'])

        return redirect('/p/orientacoes-aprovacao-voluntarios/')

    # Lógica da aprovação de voluntários propriamente dita
    error = None
    proximo = False

    # Primeiro grava alterações se necessário
    if request.method == 'POST':

        concurrency_error_msg = 'Sua análise não foi gravada, pois o mesmo cadastro acaba de ser analisado por outra pessoa. Pule alguns registros para evitar concorrência.'
        
        vol_id = int(request.POST.get('id'))

        alteracoes_vol = {'resp_analise': request.user,
                          'data_analise': timezone.now()}

        # Este objeto não é mais usado na gravação, porém é usado na validação do formulário e como
        # referência no template em caso de erro de preenchimento de dados
        myvol = Voluntario.objects.get(pk=vol_id)
        myvol.resp_analise = request.user
        myvol.data_analise = timezone.now()
        dif = ''

        usuario_update_fields = []

        if 'aprovar' in request.POST:

            if myvol.usuario.nome != request.POST.get('nome'):
                dif = 'Nome: ' + myvol.usuario.nome + ' -> ' + request.POST.get('nome') + "\n" + dif
                usuario_update_fields.append('nome')
                myvol.usuario.nome = request.POST.get('nome')

            if myvol.usuario.email != request.POST.get('email'):
                dif = dif + 'E-mail: ' + myvol.usuario.email + ' -> ' + request.POST.get('email') + "\n"
                usuario_update_fields.append('email')
                myvol.usuario.email = request.POST.get('email')

            campos_editaveis = ['profissao', 'ddd', 'telefone', 'empresa',  'entidade_que_ajudou',  'descricao']

            for campo in campos_editaveis:
                if campo in request.POST and getattr(myvol, campo) != request.POST.get(campo):
                    dif = dif + campo + ': ' + getattr(myvol, campo) + ' -> ' + request.POST.get(campo) + "\n"
                    alteracoes_vol[campo] = request.POST.get(campo)
                    setattr(myvol, campo, request.POST.get(campo))

            form = FormVoluntario(request.POST, instance=myvol)

            email_repetido = Usuario.objects.filter(email=request.POST.get('email')).exclude(id=myvol.usuario.id).count() > 0

            if form.is_valid() and len(request.POST.get('nome')) > 0 and len(request.POST.get('email')) > 0 and not email_repetido:

                alteracoes_vol['aprovado'] = True
                alteracoes_vol['dif_analise'] = dif

                # Só atualiza se objeto continuar aguardando análise, evitando sobrepor gravação de outro usuário concorrente.
                # Importante: o método update não usa save, e portanto nenhum sinal é disparado (pre ou post save)
                updated = Voluntario.objects.filter(
                    id=vol_id,
                    data_analise__isnull=True,
                ).update(**alteracoes_vol)

                if updated > 0:

                    # Assume que se conseguiu alterar os dados de voluntário, então não haverá mais problema
                    # de concorrência na alteração de dados de usuário na sequência. Porém é preciso verificar
                    # algum outro erro de gravação (unicidade de e-mail, campo vazio, etc).
                    if len(usuario_update_fields) > 0:
                        try:
                            myvol.usuario.save(update_fields=usuario_update_fields)
                        except Exception as e:
                            notify_support(u'Erro na aprovação de voluntários',  u'Usuário: ' + str(myvol.usuario.id) + "\n" + u'Nome: ' + myvol.usuario.nome + "\n" + u'E-mail: ' + myvol.usuario.email + "\n" + u'Exceção: ' + str(e), request)
                            error = 'Houve um erro na gravação do nome e/ou email. Mesmo assim o cadastro foi aprovado e o suporte já foi automaticamente notificado para averiguar o que houve.'

                    # Envia notificação de aprovação manualmente, pois o post_save não é disparado acima
                    try:
                        notifica_aprovacao_voluntario(myvol.usuario)
                    except Exception as e:
                        notify_support(u'Erro ao notificar aprovação de voluntário',  u'Usuário: ' + str(myvol.usuario.id) + "\n" + u'Nome: ' + myvol.usuario.nome + "\n" + u'E-mail: ' + myvol.usuario.email + "\n" + u'Exceção: ' + str(e), request)
                else:
                    error = concurrency_error_msg

                proximo = True

            else:
                error = ''

                if len(request.POST.get('nome')) == 0:
                    error = "O campo 'nome' deve ser preenchido!\n"

                if len(request.POST.get('email')) == 0:
                    error = error + "O campo 'email' deve ser preenchido!\n"
                else:
                    if email_repetido:
                        error = error + "O campo 'email' foi preenchido com um valor que já existe no banco de dados!\n"

                for field in form:
                    for e in field.errors:
                        error = error + "Erro de preenchimento no campo '" + field.label + "'.\n"

        elif 'rejeitar' in request.POST:

            alteracoes_vol['aprovado'] = False

            # Só atualiza se objeto continuar aguardando análise, evitando sobrepor gravação de outro usuário concorrente
            # importante: o método update não usa save, e portanto nenhum sinal é disparado (pre ou post save)
            updated = Voluntario.objects.filter(
                id=vol_id,
                data_analise__isnull=True,
            ).update(**alteracoes_vol)

            if updated == 0:
                error = concurrency_error_msg
            
            proximo = True

    # Total de voluntários que confirmaram o email e estão aguardando aprovação
    queue = Voluntario.objects.filter(aprovado__isnull=True, usuario__emailaddress__verified=True).order_by('data_cadastro')
    total = queue.count()

    rec = None
    new_rec = None
    i = None # i controla a posição na fila, ou seja, é um offset! só deve ser alterado no pular
    frase = None

    if total > 0:

        if request.method == 'GET':

            i = int(request.GET.get('i', 0)) # ou o parâmetro i, ou 0

        else: # POST

            i = int(request.POST.get('i', 0)) # ou o parâmetro i, ou 0

            if 'pular' in request.POST:

                i = i + 1
            else:

                if proximo:

                    # Mantem a mesma posição na fila, pois o registro aprovado/rejeitado saiu da fila
                    pass
                
                else:

                    # Se caiu aqui, houve erro, então vamos manter o mesmo registro sendo editado
                    new_rec = myvol

        if i >= total:

            i = total - 1

        if new_rec is None:
            rec = queue[i]
            # Pega outra cópia do registro para normalizar os dados
            new_rec = Voluntario.objects.get(pk=rec.id)
            new_rec.normalizar()
        else:
            # Pega os dados originais do registro sendo editado
            rec = Voluntario.objects.get(pk=new_rec.id)
            
    else: # total == 0

        frase = FraseMotivacional.objects.reflexao_do_dia()
            
    context = {'total': total,
               'rec': rec,
               'new_rec': new_rec,
               'i': i,
               'last': (i == total-1),
               'error': error,
               'frase': frase}
    template = loader.get_template('vol/aprovacao_voluntarios.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
@permission_required('vol.change_entidadeaguardandoaprovacao')
@transaction.atomic
def revisao_entidades(request):
    '''Página para revisar novos cadastros de entidades'''

    # Controle de exibição das orientações
    codigo_conteudo = 'orientacoes-revisao-entidades'
    acessos = AcessoAConteudo.objects.filter(conteudo__codigo=codigo_conteudo, usuario=request.user).count()
    if acessos == 0:
        # Caso não tenha visualizado as orientações, redireciona pra ela
        return exibe_conteudo(request, codigo_conteudo)

    changelist_url = reverse('admin:vol_entidadeaguardandoaprovacao_changelist')
    return redirect(changelist_url)

@login_required
@staff_member_required
def painel(request):
    '''Painel de controle administrativo'''

    # Total de voluntários que confirmaram o email e estão aguardando aprovação
    total_vol = Voluntario.objects.filter(aprovado__isnull=True, usuario__emailaddress__verified=True).count()

    # Intervalo de tempo histórico para revisão de cadastros de voluntários
    duracao = Voluntario.objects.filter(data_analise__isnull=False).aggregate(avg=Avg(F('data_analise') - F('data_cadastro')), max=Max(F('data_analise') - F('data_cadastro')))

    # Tempo médio
    tempo_vol = int(duracao['avg'].total_seconds()/3600)

    # Tempo máximo
    tempo_vol_max = int(duracao['max'].total_seconds()/3600)

    # Intervalo de tempo nos últimos 7 dias para revisão de cadastros de voluntários
    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)
    delta = datetime.timedelta(days=7)
    duracao_recente = Voluntario.objects.filter(data_analise__date__gt=now-delta).aggregate(avg=Avg(F('data_analise') - F('data_cadastro')), max=Max(F('data_analise') - F('data_cadastro')))

    # Tempo médio & máximo
    tempo_vol_recente = None
    tempo_vol_max_recente = None
    
    if duracao_recente['avg']:
        tempo_vol_recente = int(duracao_recente['avg'].total_seconds()/3600)

    if duracao_recente['max']:
        tempo_vol_max_recente = int(duracao_recente['max'].total_seconds()/3600)

    # Total de voluntários aprovados no dia
    total_vol_dia = Voluntario.objects.filter(aprovado__isnull=False, data_analise__date=datetime.datetime.now()).count()

    # Total de voluntários revisados pelo usuário
    total_vol_pessoal = Voluntario.objects.filter(aprovado__isnull=False, resp_analise=request.user).count()

    # Data da primeira análise do usuário
    primeira_analise = Voluntario.objects.filter(resp_analise=request.user).aggregate(data=Min(F('data_analise')))

    # Total de voluntários revisados por todos desde que o usuário logado começou a revisar
    total_vol_geral = 0
    if primeira_analise['data']:
        total_vol_geral = Voluntario.objects.filter(aprovado__isnull=False, data_analise__gte=primeira_analise['data']).count()

    # Percentual de revisão
    indice_revisao_vol_pessoal = None
    if total_vol_pessoal > 0 and total_vol_geral > 0:
        indice_revisao_vol_pessoal = round(100*(total_vol_pessoal/total_vol_geral), 3)

    # Total de entidades que confirmaram o email e estão aguardando aprovação
    id_entidades = Email.objects.filter(entidade__aprovado__isnull=True, confirmado=True).values_list('entidade_id')

    total_ents = Entidade.objects.filter(pk__in=id_entidades).count()

    # Total de entidades revisadas no dia
    total_ents_dia = Entidade.objects.filter(aprovado__isnull=False, data_analise__date=datetime.datetime.now()).count()

    # Total de entidades aguardando boas vindas
    total_onboarding = Entidade.objects.filter(aprovado=True, data_cadastro__gt=datetime.datetime(2020,9,21, tzinfo=datetime.timezone.utc), data_envio_onboarding__isnull=True, cancelamento_onboarding__isnull=True).count()

    # Total de pendências em entidades aprovadas
    total_pendencias_ents = AnotacaoEntidade.objects.filter(req_acao=True, entidade__aprovado=True, rev__isnull=True).count()

    # Total de entidades com problema na receita
    total_problemas_cnpj = Entidade.objects.filter(aprovado=True, data_consulta_cnpj__isnull=False, erro_consulta_cnpj__isnull=True).exclude(situacao_cnpj='ATIVA').count()

    # Total de entidades revisadas pelo usuário
    total_ents_pessoal = Entidade.objects.filter(aprovado__isnull=False, resp_analise=request.user).count()

    # Total de e-mails de entidades descobertos pelo usuário
    total_emails_descobertos = Email.objects.filter(entidade__isnull=False, entidade__aprovado=True, resp_cadastro=request.user).count()

    # Total de processos seletivos aguardando revisão
    total_procs_revisao = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.AGUARDANDO_APROVACAO).count()

    # Total de processos seletivos
    total_procs = ProcessoSeletivo.objects.filter().count()

    # Forças tarefas
    tarefas_ativas = ForcaTarefa.objects.filter(visivel=True).order_by('data_cadastro')

    tarefas = []

    # Determina o progresso de cada tarefa
    for tarefa in tarefas_ativas:
        m = apps.get_model('vol', tarefa.modelo)
        filtro = eval(tarefa.filtro)
        qs = m.objects.filter(**filtro)
        total_atual = qs.count()
        if tarefa.meta is None:
            tarefa.meta = total_atual
            tarefa.save(update_fields=['meta'])
        tarefa.previsao_termino = None
        if tarefa.meta > 0:
            tarefa.progresso = 100*(abs(total_atual-tarefa.meta)/tarefa.meta)
            if tarefa.progresso > 0:
                # Calcula o número de casas decimais que deve ser exibido no progresso de forma a garantir que a
                # revisão de um único registro sempre resulte numa alteração, mesmo que pequena
                incremento = 100*(1/tarefa.meta) # incremento no progresso com um único registro
                pos_primeiro_digito = int(ceil(-log10(incremento))) # posição do primeiro dígito significativo
                tarefa.progresso = round(tarefa.progresso, pos_primeiro_digito)
                # Calcula a previsão de término por regra de três
                delta = now - tarefa.data_cadastro # tempo decorrido
                segundos_ate_o_momento = delta.total_seconds() # em segundos
                segundos_que_restam = (segundos_ate_o_momento*(100-tarefa.progresso))/tarefa.progresso
                tarefa.previsao_termino = now + datetime.timedelta(seconds=segundos_que_restam)
        else:
            tarefa.progresso = 100
        tarefas.append(tarefa)

    # Dados sobre desenvolvimento do sistema
    num_tickets = None

    github_api_url = 'https://api.github.com/'

    url = github_api_url + 'repos/regiov/voluntarios'

    j = None
    try:
        resp = urllib.request.urlopen(url)
        j = json.loads(resp.read().decode('utf-8'))
        if j and 'open_issues' in j:
            num_tickets = j['open_issues']
    except Exception as e:
        motivo = type(e).__name__ + str(e.args)
        notify_support(u'Erro na api do github', motivo, request)

    ultimos_commits = None

    params = urllib.parse.urlencode({'sha': 'master', 'page': 1, 'per_page': 5})
    url = github_api_url + 'repos/regiov/voluntarios/commits' + '?%s' % params

    try:
        resp = urllib.request.urlopen(url)
        ultimos_commits = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        motivo = type(e).__name__ + str(e.args)
        notify_support(u'Erro na api do github', motivo, request)
    
    context = {'total_vol': total_vol,
               'tempo_vol': tempo_vol,
               'tempo_vol_max': tempo_vol_max,
               'tempo_vol_recente': tempo_vol_recente,
               'tempo_vol_max_recente': tempo_vol_max_recente,
               'total_vol_dia': total_vol_dia,
               'total_vol_pessoal': total_vol_pessoal,
               'indice_revisao_vol_pessoal': indice_revisao_vol_pessoal,
               'total_ents': total_ents,
               'total_ents_dia': total_ents_dia,
               'total_onboarding': total_onboarding,
               'total_pendencias_ents': total_pendencias_ents,
               'total_problemas_cnpj': total_problemas_cnpj,
               'total_ents_pessoal': total_ents_pessoal,
               'total_emails_descobertos': total_emails_descobertos,
               'total_procs_revisao': total_procs_revisao,
               'total_procs': total_procs,
               'tarefas': tarefas,
               'num_tickets': num_tickets,
               'ultimos_commits': ultimos_commits }
    template = loader.get_template('vol/painel.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def revisao_processos_seletivos(request):
    '''Página para revisar novos processos seletivos'''

    processos = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.AGUARDANDO_APROVACAO).order_by('inicio_inscricoes')

    if len(processos) == 0:
        # Um usuário só entrará aqui nessa condição se tiver armazenado o link da página (pouco provável)
        # ou se tiver acabado de aprovar o último processo seletivo, situação em que faz mais sentido
        # já redirecionar para o painel de controle.
        return painel(request)

    context = {'processos': processos}

    template = loader.get_template('vol/revisao_processos_seletivos.html')
    
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def revisao_processo_seletivo(request, codigo_processo):
    '''Página para revisar um processo seletivo'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    try:

        if request.method == 'POST':
            if 'aprovar' in request.POST:
                qs = ProcessoSeletivo.objects.select_for_update().filter(codigo=codigo_processo, status=StatusProcessoSeletivo.AGUARDANDO_APROVACAO)
                with transaction.atomic():
                    for processo in qs:
                        if processo.inscricoes_encerradas():
                            messages.error(request, u'As inscrições para este processo já estão encerradas! Entre em contato com a entidade para atualizar as datas.')
                        else:
                            processo.aprovar(by=request.user)
                            processo.save()
                            return revisao_processos_seletivos(request)
            else:
                return redirect(reverse('painel'))
        else:
            processo = ProcessoSeletivo.objects.get(codigo=codigo_processo, status=StatusProcessoSeletivo.AGUARDANDO_APROVACAO)
                
    except ProcessoSeletivo.DoesNotExist:
        messages.error(request, u'Este processo não existe ou já foi revisado...')
        return redirect(reverse('painel'))

    # Em princípio, vamos deixar tudo desabilitado. Se houver algum problema será preciso
    # entrar em contato com a entidade para que ela faça a alteração. Futuramente podemos pensar
    # em permitir alterações na revisão ou então em criar um status novo "aguardando revisão", mas
    # antes de complicar vamos tentar a solução mais simples.
    form = FormProcessoSeletivo(instance=processo, disabled=True)

    FormSetAreaTrabalho = formset_factory(FormAreaTrabalho, formset=BaseFormSet, extra=0, min_num=1, validate_min=True, can_delete=False)
    area_trabalho_formset = FormSetAreaTrabalho(initial=AreaTrabalhoEmProcessoSeletivo.objects.filter(processo_seletivo=processo).order_by('area_trabalho__nome').values('area_trabalho'))
    for subform in area_trabalho_formset:
        subform.disable()
        
    context = {'form': form,
               'area_trabalho_formset': area_trabalho_formset,
               'processo': processo}

    template = loader.get_template('vol/revisao_processo_seletivo.html')
    
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def monitoramento_processos_seletivos(request):
    '''Página para monitorar todos os processos seletivos cadastrados'''

    processos = ProcessoSeletivo.objects.filter().order_by('-cadastrado_em')

    context = {'processos': processos}

    template = loader.get_template('vol/monitoramento_processos_seletivos.html')
    
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def panorama_revisao_voluntarios(request):
    '''Panorama da dinâmica de trabalho de revisão de cadastros de voluntários'''

    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)
    # Período considerado: últimas duas semanas
    num_days = 14
    # Estrutura padrão de dados das horas no dia
    hours = {}
    for i in range(24): # de 0 a 23
        hours[i] = [] # lista com ids de pessoas que trabalharam nesse horário
    # Estrutura padrão de dados para cada dia do período e as respectivas datas
    days = {}
    for i in range(num_days):
        # date: objeto data correspondente
        # hours: cópia da estrutura de dados de horas
        # ok: indica se alguém trabalhou no dia
        days[i] = {'date': now-datetime.timedelta(days=i), 'hours': deepcopy(hours), 'ok': False}
    # Seleção das revisões no período
    delta = datetime.timedelta(days=num_days)
    revs = Voluntario.objects.filter(data_analise__date__gt=now-delta).values('data_analise', 'resp_analise')
    # Preenche a estrutura de dados
    for rev in revs:
        data_analise = rev['data_analise'].astimezone(current_tz)
        days_before = (now.date()-data_analise.date()).days
        hour = data_analise.hour
        days[days_before]['ok'] = True
        if rev['resp_analise'] not in days[days_before]['hours'][hour]:
            days[days_before]['hours'][hour].append(rev['resp_analise'])

    context = {'hours': hours,
               'main_hours': [8, 12, 18],
               'days': days}
    template = loader.get_template('vol/panorama_revisao_voluntarios.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def carga_revisao_voluntarios(request):
    '''Distribuição da carga de trabalho na revisão de cadastros de voluntários'''

    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)
    # Período considerado: últimos 3 meses
    num_days = 90
    delta = datetime.timedelta(days=num_days)
    revisoes = Voluntario.objects.filter(data_analise__date__gt=now-delta).annotate(semana=TruncWeek('data_analise')).values('semana', 'resp_analise').annotate(cnt=Count('id'))

    # Lista de ids de revisores sem repetição
    revisores = []
    # Estrutura de dados para facilitar a localização de quantidades de revisões por semana e revisor:
    # semana_em_que_houve_trabalho -> revisor 1 -> qtde revisões
    #                              -> revisor 2 -> qtde revisões
    dados = {}

    for r in revisoes:
        if r['resp_analise'] not in revisores:
            revisores.append(r['resp_analise'])
        if r['semana'] not in dados:
            dados[r['semana']] = {}
        dados[r['semana']][r['resp_analise']] = r['cnt']

    # Eixo x: semanas trabalhadas em ordem ascendente
    x = sorted(dados.keys())

    # Eixos y: lista (por revisor) de listas de valores (quantidades de revisões a cada semana trabalhada)
    ys = []

    for revisor in sorted(revisores):
        y = []
        for semana in x: # já está ordenado
            qtde = 0
            if revisor in dados[semana]:
                qtde = dados[semana][revisor]
            y.append(qtde)
        ys.append(y)
    
    context = {'meses': num_days/30,
               'x': x,
               'ys': ys}
    template = loader.get_template('vol/carga_revisao_voluntarios.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
@transaction.atomic
def exibe_conteudo(request, conteudo):
    '''Exibe conteúdo controlado'''
    if isinstance(conteudo, str):
        try:
            conteudo = Conteudo.objects.get(codigo=conteudo)
        except Conteudo.DoesNotExist:
            notify_support(u'Código de conteúdo inexistente', u'Código: ' + conteudo, request)
            raise Http404
    acesso = AcessoAConteudo(conteudo=conteudo, usuario=request.user)
    acesso.save()
    return redirect(conteudo.get_url())

@login_required
@staff_member_required
def exibe_orientacoes_tarefa(request, codigo_tarefa):
    '''Exibe orientações sobre força tarefa. View criada apenas para faciliar a criação de link.'''
    try:
        tarefa = ForcaTarefa.objects.get(codigo=codigo_tarefa)
    except ForcaTarefa.DoesNotExist:
        raise Http404

    if not tarefa.orientacoes:
        raise Http404

    return exibe_conteudo(request, tarefa.orientacoes)

@login_required
@staff_member_required
def exibe_tarefa(request, codigo_tarefa):
    '''Acesso à página de trabalho da força tarefa'''
    try:
        tarefa = ForcaTarefa.objects.get(codigo=codigo_tarefa)
    except ForcaTarefa.DoesNotExist:
        raise Http404

    if tarefa.orientacoes:
        acessos = AcessoAConteudo.objects.filter(conteudo=tarefa.orientacoes, usuario=request.user).count()
        if acessos == 0:
            # Caso não tenha visualizado as orientações, redireciona pra ela
            return exibe_conteudo(request, tarefa.orientacoes)

    # Senão redireciona para o link da tarefa
    return redirect(tarefa.url)

@login_required
@staff_member_required
def progresso_cata_email_por_uf(request):
    '''Exibe andamento da força tarefa de descobrir e-mail por estado'''

    # OBS: não há como saber o total com precisão por estado, pois algumas entidades podem ter sido removidas
    
    # Entidades aprovadas, sem data de cadastro, sem vínculo, sem e-mail e sem anotação
    #q_faltam = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=True, anotacaoentidade_set__isnull=True, data_cadastro__isnull=True).values('estado').order_by('estado').annotate(total=Count('pk', distinct=True))

    # Entidades "aprovadas", sem data de cadastro, sem vínculo e sem e-mail
    q_faltam = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=True, data_cadastro__isnull=True).values('estado').order_by('estado').annotate(total=Count('pk', distinct=True))
    faltam = {}
    for props in q_faltam:
        faltam[props['estado']] = props['total']

    # Entidades aprovadas, sem data de cadastro, sem vínculo, com e-mail sem confirmação ou com anotação
    #q_feitos = Entidade.objects.filter(Q(email_set__confirmado=False) | Q(anotacaoentidade_set__isnull=False), aprovado=True, vinculoentidade__isnull=True, data_cadastro__isnull=True).values('estado').order_by('estado').annotate(total=Count('pk', distinct=True))

    # Entidades aprovadas, sem data de cadastro, sem vínculo, com e-mail
    q_feitos = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=False, data_cadastro__isnull=True).values('estado').order_by('estado').annotate(total=Count('pk', distinct=True))
    feitos = {}
    for props in q_feitos:
        feitos[props['estado']] = props['total']

    estados = []

    for sigla, nome in UFS:
        progresso = total = tot_faltam = tot_feitos = 0
        if sigla in faltam:
            tot_faltam = faltam[sigla]
        if sigla in feitos:
            tot_feitos = feitos[sigla]
        total = tot_faltam + tot_feitos
        if total > 0:
            progresso = round((tot_feitos/total)*100.0, 1)
            if progresso < 100:
                estados.append({'sigla': sigla, 'nome': nome, 'progresso': progresso})
    
    context = {'estados': estados}
    template = loader.get_template('vol/progresso_cata_email_por_uf.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def progresso_cata_email_por_municipio(request, sigla):
    '''Exibe andamento da força tarefa de descobrir e-mail por município'''

    # OBS: não há como saber o total com precisão por município, pois algumas entidades podem ter sido removidas

    cidades_disponiveis = []

    # Entidades aprovadas, sem data de cadastro, sem vínculo, sem e-mail e sem anotação
    #q_faltam = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=True, anotacaoentidade_set__isnull=True, data_cadastro__isnull=True, estado=sigla).values('cidade').order_by('cidade').annotate(total=Count('pk', distinct=True))

    # Entidades "aprovadas", sem data de cadastro, sem vínculo e sem e-mail
    q_faltam = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=True, data_cadastro__isnull=True, estado=sigla).values('cidade').order_by('cidade').annotate(total=Count('pk', distinct=True))
    faltam = {}
    for props in q_faltam:
        faltam[props['cidade']] = props['total']
        cidades_disponiveis.append(props['cidade'])

    # Entidades aprovadas, sem data de cadastro, sem vínculo, com e-mail sem confirmação ou com anotação
    #q_feitos = Entidade.objects.filter(Q(email_set__confirmado=False) | Q(anotacaoentidade_set__isnull=False), aprovado=True, vinculoentidade__isnull=True, data_cadastro__isnull=True, estado=sigla).values('cidade').order_by('cidade').annotate(total=Count('pk', distinct=True))

    # Entidades aprovadas, sem data de cadastro, sem vínculo, com e-mail
    q_feitos = Entidade.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=False, data_cadastro__isnull=True, estado=sigla).values('cidade').order_by('cidade').annotate(total=Count('pk', distinct=True))
    feitos = {}
    for props in q_feitos:
        feitos[props['cidade']] = props['total']
        if props['cidade'] not in cidades_disponiveis:
            cidades_disponiveis.append(props['cidade'])

    cidades = []

    for nome in sorted(cidades_disponiveis):
        progresso = total = tot_faltam = tot_feitos = 0
        if nome in faltam:
            tot_faltam = faltam[nome]
        if nome in feitos:
            tot_feitos = feitos[nome]
        total = tot_faltam + tot_feitos
        if total > 0:
            progresso = round((tot_feitos/total)*100.0, 1)
            if progresso < 100:
                cidades.append({'nome': nome, 'progresso': progresso})
    
    context = {'uf': sigla, 'cidades': cidades}
    template = loader.get_template('vol/progresso_cata_email_por_municipio.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def exibe_pendencias_entidades(request):
    '''Exibe lista de pendências em cadastros de entidades na interface adm.'''
    # Mostra mensagem com orientações
    messages.info(request, u'Para resolver uma pendência, clique no ícone da entidade para editar o cadastro e em seguida volte nesta lista, marque a pendência correspondente, selecione a ação "marcar anotação como revisada" e depois clique no botão "ir".')
    # E ativa filtro para entidades aprovadas
    return redirect(reverse('admin:vol_anotacaoaguardandorevisao_changelist') + '?entidade__aprovado__exact=1')

@login_required
@staff_member_required
def exibe_entidades_com_problema_na_receita(request):
    '''Exibe lista de entidades com problema na receita federal na interface adm.'''
    # E ativa filtro para entidades aprovadas
    return redirect(reverse('admin:vol_entidadecomproblemanareceita_changelist'))

@login_required
@staff_member_required
def onboarding_entidades(request):
    '''Exibe lista de entidades para fins de gerenciamento de onboarding'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    # Controle de exibição das orientações
    codigo_conteudo = 'orientacoes-boas-vindas-entidades'
    acessos = AcessoAConteudo.objects.filter(conteudo__codigo=codigo_conteudo, usuario=request.user).count()
    if acessos == 0:
        # Caso não tenha visualizado as orientações, redireciona pra ela
        return exibe_conteudo(request, codigo_conteudo)
    
    # Somente entidades cadastradas há menos de x dias
    dias = request.session.get('dias', 90)
    if request.method == 'GET':
        if 'dias' in request.GET:
            dias = request.GET['dias']
            request.session['dias'] = dias
    elif request.method == 'POST':
        if 'dias' in request.POST:
            dias = request.POST['dias']
            request.session['dias'] = dias
    now = datetime.datetime.now()
    delta = datetime.timedelta(days=int(dias))
    ref = now-delta
    entidades_aprovadas = Entidade.objects.filter(aprovado=True, data_cadastro__gt=ref.date())
    entidades_inativas_com_onboarding_iniciado = Entidade.objects.filter(aprovado=False, data_cadastro__gt=ref.date(), msg_onboarding__isnull=False)
    entidades = entidades_aprovadas.union(entidades_inativas_com_onboarding_iniciado).order_by('-data_cadastro')
    context = {'dias': dias, 'entidades': entidades}
    template = loader.get_template('vol/onboarding_entidades.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def onboarding_entidade(request, id_entidade):
    '''Exibe página de onboarding de entidade'''
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404

    assunto_msg = None
    msg = None

    # Assunto da mensagem
    if not entidade.assunto_msg_onboarding:
        assunto_msg = entidade.menor_nome() + ' - Bem-vind@!'
    else:
        assunto_msg = entidade.assunto_msg_onboarding

    # Assinatura
    assinatura = entidade.assinatura_onboarding
    if assinatura is None:
        resp = entidade.resp_onboarding
        if resp is None:
            if request.method == 'POST' and 'assumir' in request.POST:
                resp = request.user
        if resp:
            entidades_recepcionadas_pela_pessoa = Entidade.objects.filter(resp_onboarding=resp, assinatura_onboarding__isnull=False).exclude(assinatura_onboarding='').order_by('-data_resp_onboarding')
            if len(entidades_recepcionadas_pela_pessoa) > 0:
                # Pega última assinatura
                assinatura = entidades_recepcionadas_pela_pessoa[0].assinatura_onboarding
            else:
                assinatura = resp.nome

    # Conteúdo da mensagem
    if not entidade.msg_onboarding:
        msg = loader.render_to_string('vol/msg_onboarding.txt',
                                      {'nome_responsavel': request.user.get_short_name(),
                                       'nome_contato': entidade.nome_contato,
                                       'assinatura': assinatura,
                                       'id_entidade': entidade.pk})
    else:
        msg = entidade.msg_onboarding

    form = FormOnboarding(initial={'assunto': assunto_msg, 'mensagem': msg, 'assinatura': assinatura})

    if request.method == 'POST':
        if 'assumir' in request.POST:
            # Assumir uma recepção de entidade envolve gravar o responsável, a data e já direcionar para a página da mensagem
            if entidade.resp_onboarding is not None:
                messages.error(request, u'Já há um responsável pela recepção desta entidade!')
            else:
                entidade.resp_onboarding = request.user
                entidade.data_resp_onboarding = timezone.now()
                entidade.save(update_fields=['resp_onboarding', 'data_resp_onboarding'])
        else:

            form = FormOnboarding(data=request.POST)

            # Todas as outras ações só podem ser feitas pelo responsável pela recepção
            if entidade.resp_onboarding != request.user and not request.user.is_superuser:
                messages.error(request, u'Somente o responsável pela recepção desta entidade pode trabalhar nesta tarefa!')
            else:

                # Gravação pura e simples do assunto e da mensagem, redirecionando para a lista
                if 'gravar' in request.POST:
                        if 'mensagem' in request.POST and 'assunto' in request.POST:
                            entidade.assunto_msg_onboarding = request.POST['assunto']
                            entidade.msg_onboarding = request.POST['mensagem']
                            entidade.assinatura_onboarding = request.POST['assinatura']
                            entidade.save(update_fields=['assunto_msg_onboarding', 'msg_onboarding', 'assinatura_onboarding'])
                            messages.info(request, u'Mensagem gravada para envio posterior')
                            return redirect(reverse('onboarding_entidades'))

                # Envio ou renvio da mensagem
                if 'enviar' in request.POST or 'reenviar' in request.POST:

                    error = False

                    if not hasattr(settings, 'ONBOARDING_EMAIL_HOST_USER') or not hasattr(settings, 'ONBOARDING_EMAIL_HOST_PASSWORD') or not hasattr(settings, 'ONBOARDING_EMAIL_FROM'):

                        messages.error(request, u'Ausência de configuração para envio do e-mail!')
                        error = True

                    if not error and 'enviar' in request.POST:

                        if 'assunto' in request.POST and 'mensagem' in request.POST and 'assinatura' in request.POST:

                            # obs: no caso de reenvio, usa assunto_msg e msg que já foram pegados do banco mais acima
                            assunto_msg = request.POST['assunto']
                            msg = request.POST['mensagem']
                            assinatura = request.POST['assinatura']

                        else:
                            messages.error(request, u'Ausência de parâmetros para envio do e-mail!')
                            error = True

                    if not error and '[[' in msg or ']]' in msg:

                        # obs: não é para cair aqui em caso de reenvio, mas por segurança vamos verificar aqui tb
                        messages.error(request, u'Remova os trechos delimitados por [[ ... ]] na mensagem. Eles foram feitos para incluir conteúdo específico personalizado.')
                        error = True

                    if not assunto_msg:
                        messages.error(request, u'Falta o assunto!')
                        error = True

                    if not msg:
                        messages.error(request, u'Falta a mensagem!')
                        error = True

                    if not assinatura:
                        messages.error(request, u'É preciso colocar sua assinatura para personalizar a mensagem. Por que você removeu??')
                        error = True

                    if not error:

                        msg_com_assinatura = msg + "\n" + assinatura + "\n" + 'Equipe de Apoio' + "\n" + 'voluntarios.com.br' + "\n" + 'protocolo: oe-' + str(entidade.id)

                        html_msg = loader.render_to_string('vol/onboarding_template.html',
                                                           {'mensagem': msg_com_assinatura,
                                                            'assinatura': assinatura,
                                                            'link_logo': request.build_absolute_uri(reverse('logo_rastreado')) + '?' + urlencode({'oe': entidade.hmac_key()})})
                        try:
                            entidade.assunto_msg_onboarding = assunto_msg
                            entidade.msg_onboarding = msg
                            entidade.assinatura_onboarding = assinatura
                            if entidade.data_envio_onboarding is None or entidade.falha_envio_onboarding is not None:
                                entidade.data_envio_onboarding = timezone.now()
                            with mail.get_connection(
                                host=settings.EMAIL_HOST, 
                                port=settings.EMAIL_PORT, 
                                username=settings.ONBOARDING_EMAIL_HOST_USER, 
                                password=settings.ONBOARDING_EMAIL_HOST_PASSWORD, 
                                use_tls=settings.EMAIL_USE_TLS
                                ) as connection:
                                email_msg = mail.EmailMultiAlternatives(assunto_msg,
                                                                        msg_com_assinatura,
                                                                        settings.ONBOARDING_EMAIL_FROM,
                                                                        [entidade.email_principal], #to
                                                                        #[request.user.email], #bcc (melhor evitar detecção de leitura por nós mesmos)
                                                                        reply_to=[settings.ONBOARDING_EMAIL_FROM, request.user.email],
                                                                        connection=connection)
                                email_msg.attach_alternative(html_msg, "text/html")
                                email_msg.send()
                                # Melhor não rastrear por Message-Id, pois pode-se ter que enviar várias vezes
                                # o mesmo e-mail, sendo que a cada vez será um id diferente. O rastreamento
                                # é feito hoje por um protocolo no corpo da mensagem.
                                #msg_id = email_msg.extra_headers.get('Message-Id', None)
                            entidade.falha_envio_onboarding = None
                            entidade.total_envios_onboarding = entidade.total_envios_onboarding + 1
                            messages.info(request, u'Mensagem enviada com sucesso!')
                        except Exception as e:
                            entidade.falha_envio_onboarding = str(e)
                            messages.error(request, u'Ops, falha no envio da mensagem! A equipe de suporte será notificada.')
                            notify_support(u'Falha no envio de msg de onboarding', request.user.nome + "\n\n" + str(e), request)
                        entidade.save(update_fields=['assunto_msg_onboarding', 'msg_onboarding', 'assinatura_onboarding', 'data_envio_onboarding', 'falha_envio_onboarding', 'total_envios_onboarding'])
                        return redirect(reverse('onboarding_entidades'))

                elif 'finalizar' in request.POST:
                    if 'link' not in request.POST or not request.POST['link']:
                        messages.error(request, u'É preciso colar o link da postagem para finalizar!')
                    else:
                        link = request.POST['link']
                        validate = URLValidator()
                        try:
                            validate(link)
                            entidade.link_divulgacao_onboarding = link
                            entidade.save(update_fields=['link_divulgacao_onboarding'])
                        except ValidationError as e:
                            messages.error(request, u'O link fornecido não é válido!')

                    return redirect(reverse('onboarding_entidades'))
 
    context = {'entidade': entidade, 'form': form}
    template = loader.get_template('vol/onboarding_entidade.html')
    return HttpResponse(template.render(context, request))

@login_required
@staff_member_required
def exibe_funcao(request, id_funcao):
    '''Exibe função, com toda eventual hierarquia abaixo dela.'''
    try:
        funcao = Funcao.objects.get(id=id_funcao)
    except Funcao.DoesNotExist:
        raise Http404

    # Garante que apenas usuários vinculados à entidade editem seus dados
    entidades = request.user.entidades() # Entidades vinculadas ao usuário
    if funcao.entidade.pk not in entidades.values_list('pk', flat=True):
        raise PermissionDenied

    context = {'funcao': funcao}
    template = loader.get_template('vol/funcao.html')
    return HttpResponse(template.render(context, request))

def logo_rastreado(request):
    '''Retorna o logotipo, rastreando a origem da requisição'''
    if request.method == 'GET':
        if 'oe' in request.GET:
            # imagem na mensagem de onboarding de entidade
            entidade = Entidade.objects.from_hmac_key(request.GET['oe'])
            if entidade and entidade.data_visualiza_onboarding is None:
                entidade.data_visualiza_onboarding = timezone.now()
                entidade.save(update_fields=['data_visualiza_onboarding'])
    logo_path = settings.STATIC_ROOT + os.sep + 'images' + os.sep + 'logo.png'
    try:
        with open(logo_path, "rb") as f:
            return HttpResponse(f.read(), content_type="image/png")
    except IOError:
        return redirect(settings.STATIC_URL + 'images/logo.png')

class ListaDePostagensNoBlog(generic.ListView):
    template_name = 'vol/lista_postagens_blog.html'

    def get_queryset(self):
        status_list = [1]
        if self.request.user.is_authenticated and self.request.user.is_staff:
            status_list.append(0)
        return PostagemBlog.objects.filter(status__in=status_list).order_by('-data_criacao')

class PostagemNoBlog(generic.DetailView):
    model = PostagemBlog
    template_name = 'vol/postagem_blog.html'

def retorna_cidades(request):
    '''Retorna lista de cidades (nomes) em JSON do estado passado como parâmetro (sigla do estado)'''
    try:
        estado = request.GET.get('estado')
        UF = Estado.objects.get(sigla=estado)
        cidades = Cidade.objects.filter(uf=UF).values('nome').order_by('nome')
        lista_cidades = list(cidades)
        return JsonResponse(lista_cidades, safe = False)
    except Estado.DoesNotExist:
        raise Http404
        
@login_required 
def alternar_entidade_favorita(request):
    if not request.user.is_voluntario:
        raise PermissionDenied
    entidade_id = request.GET.get("entidade_id")
    if not entidade_id:
        raise SuspiciousOperation
    try:
        favorita = EntidadeFavorita.objects.get(entidade_id=entidade_id, voluntario=request.user.voluntario, fim__isnull=True)
        favorita.fim = timezone.now()
        favorita.save()
    except EntidadeFavorita.DoesNotExist:
        favorita = EntidadeFavorita(entidade_id=entidade_id, voluntario=request.user.voluntario)
        favorita.save()
    return HttpResponse(200)

@login_required 
def entidades_favoritas(request):
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if not request.user.is_voluntario:
        raise PermissionDenied
    favoritas = Entidade.objects.filter(entidadefavorita__voluntario=request.user.voluntario, entidadefavorita__fim__isnull=True)
    context = {'favoritas': favoritas }
    template = loader.get_template('vol/exibe_entidades_favoritas.html')
    return HttpResponse(template.render(context, request))

def numeros(request):
    '''Página com números do site'''
    current_tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(current_tz)
    um_mes = datetime.timedelta(days=31)
    ref = now-um_mes
    num_voluntarios = Voluntario.objects.filter(aprovado=True).count()
    num_novos_voluntarios_por_mes = Voluntario.objects.filter(aprovado=True, data_cadastro__gt=ref).count()
    num_entidades = Entidade.objects.filter(aprovado=True).count()
    num_novas_entidades_por_mes = Entidade.objects.filter(aprovado=True, data_cadastro__gt=ref).count()
    context = {'num_voluntarios': num_voluntarios,
               'num_novos_voluntarios_por_mes': num_novos_voluntarios_por_mes,
               'num_entidades': num_entidades,
               'num_novas_entidades_por_mes': num_novas_entidades_por_mes}
    template = loader.get_template('vol/numeros.html')
    return HttpResponse(template.render(context, request))

@login_required
def processos_seletivos_entidade(request, id_entidade):
    '''Página listando processos seletivos na interface da entidade'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404

    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    processos = ProcessoSeletivo.objects.filter(entidade_id=id_entidade).annotate(num_inscricoes=Count('participacaoemprocessoseletivo'))

    context = {'entidade': entidade, # este parâmetro é importante, pois é usado no template pai
               'processos': processos}
    template = loader.get_template('vol/processos_seletivos_entidade.html')
    return HttpResponse(template.render(context, request))

@login_required
def processos_seletivos_voluntario(request):
    '''Página listando processos seletivos na interface do voluntário'''
    inscricoes = ParticipacaoEmProcessoSeletivo.objects.none()
    if request.user.is_voluntario:
        inscricoes = ParticipacaoEmProcessoSeletivo.objects.select_related('processo_seletivo', 'processo_seletivo__entidade').filter(voluntario=request.user.voluntario)
    context = {'inscricoes': inscricoes}
    template = loader.get_template('vol/processos_seletivos_voluntario.html')
    return HttpResponse(template.render(context,request))

def busca_vagas(request):
    '''Página para busca de vagas'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    profissoes = AreaTrabalho.objects.all().order_by('nome')
    causas = AreaAtuacao.objects.all().order_by('indice')
    estados = Estado.objects.all().order_by('nome')
    vagas = None
    get_params = ''
    pagina_inicial = pagina_final = None

    if 'Envia' in request.GET:

        # Apenas voluntários cujo cadastro já tenha sido revisado e aprovado, e sejam visíveis nas buscas
        vagas = ProcessoSeletivo.objects.select_related('entidade', 'entidade__area_atuacao', 'estado', 'cidade').filter(status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES)

        # Filtro por modo de trabalho
        modo_trabalho = request.GET.get('modo_trabalho')
        if modo_trabalho:
            vagas = vagas.filter(modo_trabalho=modo_trabalho)

        # Filtro por estado
        estado = request.GET.get('estado')
        if estado:
            vagas = vagas.filter(estado__sigla=estado)
            # Filtro por cidade
            cidade = request.GET.get('cidade')
            if cidade:
                vagas = vagas.filter(cidade__nome=cidade, cidade__uf=estado)

        # Filtro por causa
        fasocial = request.GET.get('fasocial')
        if fasocial.isdigit() and fasocial not in [0, '0']:
            try:
                causa = AreaAtuacao.objects.get(pk=fasocial)
                if '.' in causa.indice:
                    vagas = vagas.filter(entidade__area_atuacao=fasocial)
                else:
                    vagas = vagas.filter(Q(entidade__area_atuacao=fasocial) | Q(entidade__area_atuacao__indice__startswith=str(causa.indice)+'.'))
            except AreaAtuacao.DoesNotExist:
                raise SuspiciousOperation(u'Causa inexistente')

        # Filtro por profissão
        fareatrabalho = request.GET.get('fareatrabalho')
        if fareatrabalho.isdigit() and fareatrabalho not in [0, '0']:
            vagas = vagas.filter(areatrabalhoemprocessoseletivo__area_trabalho=fareatrabalho)

        # Filtro por palavras-chave
        fpalavras = request.GET.get('fpalavras')
        if fpalavras is not None and len(fpalavras) > 0:
            # Aqui utilizamos outro queryset para evitar duplicidade de registros devido ao uso de distinct com order_by mais pra frente 
            ids = ProcessoSeletivo.objects.annotate(search=SearchVector('titulo', 'atividades', 'requisitos')).filter(search=fpalavras).distinct('pk')
            vagas = vagas.filter(pk__in=ids)

        # Já inclui áreas de interesse para otimizar
        # obs: essa abordagem não funciona junto com paginação! (django 1.10.7)
        #vagas = vagas.prefetch_related('entidade__area_atuacao')

        # Ordem dos resultados
        ordem = request.GET.get('ordem', '')
        if ordem == 'titulo':
            vagas = vagas.order_by('titulo')
        elif ordem == 'entidade':
            vagas = vagas.order_by('entidade__razao_social')
        else: # início das inscrições
            vagas = vagas.order_by('-inicio_inscricoes')

        # Paginação
        paginador = Paginator(vagas, 20) # 20 vagas por página
        pagina = request.GET.get('page')
        try:
            vagas = paginador.page(pagina)
        except PageNotAnInteger:
            # Se a página não é um número inteiro, exibe a primeira
            vagas = paginador.page(1)
        except EmptyPage:
            # Se a página está fora dos limites (ex 9999), exibe a última
            vagas = paginador.page(paginador.num_pages)
        pagina_atual = vagas.number
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

    context = {'modos_de_trabalho': MODO_TRABALHO,
               'profissoes': profissoes,
               'causas': causas,
               'estados': estados,
               'vagas': vagas,
               'get_params': get_params,
               'pagina_inicial': pagina_inicial,
               'pagina_final': pagina_final}
    
    template = loader.get_template('vol/busca_vagas.html')
    return HttpResponse(template.render(context, request))

@login_required
@transaction.atomic
def novo_processo_seletivo(request, id_entidade):
    '''Cadastro de novo processo seletivo via interface da entidade'''
    try:
        entidade = Entidade.objects.get(pk=id_entidade)
    except Entidade.DoesNotExist:
        raise Http404
    if int(id_entidade) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    FormSetAreaTrabalho = formset_factory(FormAreaTrabalho, formset=BaseFormSet, extra=1, max_num=10, min_num=1, validate_min=True, can_delete=True)

    if request.method == 'POST':

        form = FormProcessoSeletivo(request.POST)

        area_trabalho_formset = FormSetAreaTrabalho(request.POST, request.FILES)
        
        if form.is_valid() and area_trabalho_formset.is_valid():

            status = StatusProcessoSeletivo.EM_ELABORACAO

            if 'solicitar_aprovacao' in request.POST:
                status = StatusProcessoSeletivo.AGUARDANDO_APROVACAO
            
            processo_seletivo = ProcessoSeletivo(entidade=entidade,
                                                 cadastrado_por=request.user,
                                                 status=status,
                                                 titulo=form.cleaned_data['titulo'],
                                                 resumo_entidade=form.cleaned_data['resumo_entidade'],
                                                 modo_trabalho=form.cleaned_data['modo_trabalho'],
                                                 estado=form.cleaned_data['estado'],
                                                 cidade=form.cleaned_data['cidade'],
                                                 atividades=form.cleaned_data['atividades'],
                                                 carga_horaria=form.cleaned_data['carga_horaria'],
                                                 requisitos=form.cleaned_data['requisitos'],
                                                 inicio_inscricoes=form.cleaned_data['inicio_inscricoes'],
                                                 limite_inscricoes=form.cleaned_data['limite_inscricoes'],
                                                 previsao_resultado=form.cleaned_data['previsao_resultado'])
            processo_seletivo.save()

            # áreas de trabalho
            areas_incluidas = []
            for area_trabalho_form in area_trabalho_formset:
                area_trabalho = area_trabalho_form.cleaned_data.get('area_trabalho')
                if area_trabalho:
                    if area_trabalho.id not in areas_incluidas:
                        areas_incluidas.append(area_trabalho.id)
                        area = AreaTrabalhoEmProcessoSeletivo(area_trabalho=area_trabalho,
                                                              processo_seletivo=processo_seletivo)
                        area.save()
                    else:
                        # Ignora duplicidades
                        pass
                else:
                    # Ignora combos vazios
                    pass
            
            return redirect(reverse('processos_seletivos_entidade', kwargs={'id_entidade': entidade.id}))
    else:

        # Copia alguns dados do último processo cadastrado para agilizar
        initial = {}
        ultimo_processo = ProcessoSeletivo.objects.all().last()
        if ultimo_processo is not None:
            initial['resumo_entidade'] = ultimo_processo.resumo_entidade
            initial['modo_trabalho'] = ultimo_processo.modo_trabalho
            initial['estado'] = ultimo_processo.estado
            initial['cidade'] = ultimo_processo.cidade
        
        form = FormProcessoSeletivo(initial=initial)

        area_trabalho_formset = FormSetAreaTrabalho()

    context = {'form': form,
               'area_trabalho_formset': area_trabalho_formset,
               'entidade': entidade}
    template = loader.get_template('vol/formulario_processo_seletivo.html')
    
    return HttpResponse(template.render(context, request))

@login_required
@transaction.atomic
def editar_processo_seletivo(request, id_entidade, codigo_processo):
    '''Edição de processo seletivo via interface da entidade'''
    try:
        processo = ProcessoSeletivo.objects.get(codigo=codigo_processo)
    except ProcessoSeletivo.DoesNotExist:
        raise Http404
    if int(processo.entidade_id) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    num_inscricoes = processo.inscricoes().count()

    FormSetAreaTrabalho = formset_factory(FormAreaTrabalho, formset=BaseFormSet, extra=0, max_num=10, min_num=1, validate_min=True, can_delete=True)

    if request.method == 'POST':

        if processo.editavel():

            form = FormProcessoSeletivo(request.POST, instance=processo)
            area_trabalho_formset = FormSetAreaTrabalho(request.POST, request.FILES)

            areas_preexistentes = list(AreaTrabalhoEmProcessoSeletivo.objects.filter(processo_seletivo=processo).values_list('area_trabalho', flat=True))

            if form.is_valid() and area_trabalho_formset.is_valid():

                proc = form.save()

                areas_incluidas = []
                areas_selecionadas = []
                for area_trabalho_form in area_trabalho_formset:
                    area_trabalho = area_trabalho_form.cleaned_data.get('area_trabalho')
                    if area_trabalho:
                        areas_selecionadas.append(area_trabalho.id)
                        if area_trabalho.id not in areas_preexistentes and area_trabalho.id not in areas_incluidas:
                            areas_incluidas.append(area_trabalho.id)
                            area = AreaTrabalhoEmProcessoSeletivo(area_trabalho=area_trabalho,
                                                                  processo_seletivo=processo)
                            area.save()
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
                            r_area = AreaTrabalhoEmProcessoSeletivo.objects.get(area_trabalho=area_preexistente, processo_seletivo=processo)
                            r_area.delete()
                        except AreaTrabalhoEmProcessoSeletivo.DoesNotExist:
                            pass

                if 'solicitar_aprovacao' in request.POST:
                    proc.solicitar_aprovacao(by=request.user)
                    proc.save()
                    return redirect(reverse('processos_seletivos_entidade', kwargs={'id_entidade': proc.entidade_id}))

                messages.info(request, u'Alterações salvas com sucesso!')

        else:

            # Processo não é editável aqui
            area_trabalho_formset = FormSetAreaTrabalho(initial=AreaTrabalhoEmProcessoSeletivo.objects.filter(processo_seletivo=processo).order_by('area_trabalho__nome').values('area_trabalho'))
            for subform in area_trabalho_formset:
                subform.disable()
            
            if processo.passivel_de_antecipar_inscricoes() or processo.passivel_de_estender_inscricoes():

                # Faz uma cópia do processo, pois a chanada ao is_valid abaixo já
                # irá alterar os dados da instância
                processo_original = deepcopy(processo)

                # Estrutura customizada de dados preenchendo campos desabilitados com conteúdo do registro
                data = request.POST.dict()
                data['titulo'] = processo.titulo
                data['resumo_entidade'] = processo.resumo_entidade
                data['modo_trabalho'] = str(processo.modo_trabalho)
                data['estado'] = processo.estado
                data['cidade'] = processo.cidade
                data['atividades'] = processo.atividades
                data['carga_horaria'] = processo.carga_horaria
                data['requisitos'] = processo.requisitos
                if not processo.passivel_de_antecipar_inscricoes():
                    data['inicio_inscricoes'] = processo.inicio_inscricoes

                form = FormProcessoSeletivo(data, instance=processo)

                if form.is_valid(): # atenção, este método altera a instância do processo seletivo

                    if processo_original.passivel_de_antecipar_inscricoes():

                        if processo_original.inicio_inscricoes != processo.inicio_inscricoes:
                            processo.save(update_fields=['inicio_inscricoes'])
                            messages.info(request, u'Início de inscrições alterado com sucesso!')

                            if processo.aguardando_publicacao() and processo.inscricoes_abertas():
                                processo.publicar(by=request.user)
                                processo.save()

                    if processo_original.passivel_de_estender_inscricoes():

                        update_fields = []

                        if processo_original.limite_inscricoes != processo.limite_inscricoes:
                            update_fields.append('limite_inscricoes')
                        if processo_original.previsao_resultado != processo.previsao_resultado:
                            update_fields.append('previsao_resultado')

                        if update_fields: 
                            processo.save(update_fields=update_fields)

                        if 'limite_inscricoes' in update_fields:

                            if processo.aguardando_selecao() and processo.inscricoes_abertas():
                                obs = None
                                if processo_original.limite_inscricoes:
                                    limite_anterior = processo_original.limite_inscricoes.strftime('%d/%m/%Y %H:%M:%S')
                                    obs = u'Limite anterior para inscrições: ' + limite_anterior
                                processo.reabrir_inscricoes(by=request.user, description=obs)
                                processo.save()
                            messages.info(request, u'Limite de inscrições alterado com sucesso!')

                    return redirect(reverse('processos_seletivos_entidade', kwargs={'id_entidade': processo.entidade_id}))
    else:

        form = FormProcessoSeletivo(instance=processo)

        area_trabalho_formset = FormSetAreaTrabalho(initial=AreaTrabalhoEmProcessoSeletivo.objects.filter(processo_seletivo=processo).order_by('area_trabalho__nome').values('area_trabalho'))

        if not processo.editavel():

            for subform in area_trabalho_formset:
                subform.disable()

    context = {'form': form,
               'area_trabalho_formset': area_trabalho_formset,
               'entidade': processo.entidade, # este parâmetro é importante, pois é usado no template pai
               'processo': processo,
               'num_inscricoes': num_inscricoes}

    template = loader.get_template('vol/formulario_processo_seletivo.html')
    
    return HttpResponse(template.render(context, request))

@login_required
@transaction.atomic
def inscricoes_processo_seletivo(request, id_entidade, codigo_processo):
    '''Visualização e gerenciamento das inscrições de um processo seletivo'''
    try:
        processo = ProcessoSeletivo.objects.select_related('entidade').get(codigo=codigo_processo)
    except ProcessoSeletivo.DoesNotExist:
        raise Http404
    if int(processo.entidade_id) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    if request.method == 'POST' and 'encerrar' in request.POST:
        if processo.aguardando_selecao():
            if (processo.inscricoes_encerradas() or processo.limite_inscricoes is None):
                num_inscricoes_aguardando_selecao = processo.inscricoes(status=StatusParticipacaoEmProcessoSeletivo.AGUARDANDO_SELECAO).count()
                if num_inscricoes_aguardando_selecao == 0:
                    processo.concluir(by=request.user)
                    processo.save()
                    messages.info(request, u'Processo seletivo encerrado!')
                    return redirect(reverse('processos_seletivos_entidade',
                                            kwargs={'id_entidade': processo.entidade_id}))
                else:
                    messages.error(request, u'Ainda existem candidatos aguardando seleção.')
            else:
                messages.error(request, u'Só é possível encerrar um processo seletivo quando as inscrições estiverem encerradas ou quando não houver data limite para as inscrições.')
        else:
            messages.error(request, u'Só é possível encerrar um processo seletivo quando o mesmo estiver na situação "aguardando seleção".')
            
    inscricoes = processo.inscricoes()

    context = {'entidade': processo.entidade, # este parâmetro é importante, pois é usado no template pai
               'processo': processo,
               'inscricoes': inscricoes}

    template = loader.get_template('vol/inscricoes_processo_seletivo.html')
    
    return HttpResponse(template.render(context, request))

def exibe_processo_seletivo(request, codigo_processo):
    '''Página pública de processo seletivo'''
    try:
        processo = ProcessoSeletivo.objects.get(codigo=codigo_processo)
    except ProcessoSeletivo.DoesNotExist:
        raise Http404

    inscricao = None

    if request.user.is_authenticated and request.user.is_voluntario:

        try:
            inscricao = ParticipacaoEmProcessoSeletivo.objects.get(processo_seletivo=processo, voluntario=request.user.voluntario)
        except ParticipacaoEmProcessoSeletivo.DoesNotExist:
            pass

    context = {'processo': processo,
               'inscricao': inscricao}

    template = loader.get_template('vol/exibe_processo_seletivo.html')
    
    return HttpResponse(template.render(context, request))

@transaction.atomic
def inscricao_processo_seletivo(request, codigo_processo):
    '''Método para lidar com inscrição / desistência de processo seletivo'''

    try:
        processo = ProcessoSeletivo.objects.get(codigo=codigo_processo)
    except ProcessoSeletivo.DoesNotExist:
        messages.warning(request, u'Não encontramos a vaga especificada. Será que o código está correto? Em caso de dúvida, entre em <a href="mailto:' + settings.CONTACT_EMAIL + '">contato</a> conosco para verificarmos o que houve.')
        # Redireciona para página de exibição de mensagem
        return mensagem(request, u'Inscrição em vaga')

    # Condições para inscrição:
    if not request.user.is_authenticated:
        # Indica que usuário quer se inscrever numa vaga e redireciona para o cadastro básico de usuário
        request.session['link'] = 'vaga_' + codigo_processo
        messages.info(request, u'<strong>Para se inscrever numa vaga, faça antes um cadastro de voluntário com a gente. Comece pelo cadastro de usuário preenchendo o formulário abaixo. Se já possuir cadastro, clique no link para fazer login.</strong>')
        return redirect(reverse('account_signup'))
    if not request.user.is_voluntario:
        # Avisa que é preciso ter perfil cadastrado de voluntário para se inscrever
        if request.user.link and 'vaga_' in request.user.link:
            messages.info(request, u'<strong>Agora só falta preencher seu perfil de voluntário. Utilize o formulário abaixo e depois só aguarde a aprovação do cadastro. Assim que seu cadastro for aprovado, você vai receber uma notificação por e-mail.</strong>')
        else:
            messages.info(request, u'<strong>Para poder se inscrever numa vaga só falta preencher seu perfil de voluntário. Utilize o formulário abaixo e depois aguarde a aprovação do cadastro. Assim que seu cadastro for aprovado, você vai receber uma notificação por e-mail.</strong>')
        # Redireciona para página de cadastro de perfil de voluntário
        return redirect(reverse('cadastro_voluntario'))
    if request.user.voluntario.aprovado is None:
        # Avisa que é preciso aguardar a aprovação do cadastro
        messages.info(request, u'<strong>Aguarde a aprovação do seu cadastro para fazer a inscrição. Normalmente isso leva 1 dia útil. Você receberá uma notificação por e-mail assim que seu cadastro for aprovado.</strong>')
        return exibe_processo_seletivo(request, processo.codigo)
    if request.user.voluntario.aprovado == False:
        # Avisa que o cadastro não foi aprovado
        messages.error(request, u'<strong>Seu cadastro de voluntário não foi aprovado. Entre em <a href="mailto:' + settings.CONTACT_EMAIL + '">contato</a></strong> conosco em caso de dúvidas.')
        return exibe_processo_seletivo(request, processo.codigo)

    if not processo.inscricoes_abertas():
        messages.error(request, u'As inscrições para este processo seletivo já foram encerradas.')
        return exibe_processo_seletivo(request, processo.codigo)

    # Gerenciamento da inscrição
    if request.method == 'POST':

        inscricao = processo.busca_inscricao_de_voluntario(request.user.voluntario.pk)

        if 'inscrever' in request.POST:

            if inscricao:
                if inscricao.desistiu():
                    inscricao.reinscrever(by=request.user)
                    inscricao.save()
                    messages.info(request, u'Inscrição reativada com sucesso!')
                else:
                    messages.warning(request, u'Você já se inscreveu neste processo seletivo. Não há necesidade de se inscrever novamente.')
            else:
                inscricao = ParticipacaoEmProcessoSeletivo(processo_seletivo=processo, voluntario=request.user.voluntario)
                inscricao.save()
                messages.info(request, u'Inscrição realizada com sucesso! Aguarde as instruções do processo seletivo.')

        elif 'desistir' in request.POST:

            if inscricao:
                if inscricao.passivel_de_desistencia():
                    inscricao.desistir(by=request.user)
                    inscricao.save()
                    messages.info(request, u'Inscrição cancelada!')
                else:
                    messages.error(request, u'Não há como cancelar a inscrição nas condições em que este processo seletivo se encontra. Em caso de dúvida entre em contato conosco.')
            else:
                messages.error(request, u'Não faz sentido cancelar uma inscrição que sequer foi efetuada.')
        else:
            pass

    return exibe_processo_seletivo(request, processo.codigo)

@login_required
@transaction.atomic
def classificar_inscricao(request):
    '''Classifica uma inscrição de processo seletivo.
    Parâmetros POST:
    id (id da inscrição),
    value (status da inscrição: aguardando_selecao, selecionado, nao_selecionado)
    OBS: também requer o header X-CSRFToken'''

    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    inscricao_id = request.POST.get('id')
    value = request.POST.get('value')

    if inscricao_id is None or value is None or value not in ('aguardando_selecao', 'selecionado', 'nao_selecionado') or not inscricao_id.isdigit():
        return HttpResponseBadRequest('Parâmetros incorretos')

    try:
        inscricao = ParticipacaoEmProcessoSeletivo.objects.select_related('processo_seletivo', 'processo_seletivo__entidade').get(pk=inscricao_id)
    except ParticipacaoEmProcessoSeletivo.DoesNotExist:
        raise Http404

    if int(inscricao.processo_seletivo.entidade_id) not in request.user.entidades().values_list('pk', flat=True):
        raise PermissionDenied

    if not inscricao.passivel_de_selecao():
        raise PermissionDenied

    if value == 'aguardando_selecao':
        if inscricao.selecionado() or inscricao.nao_selecionado():
            inscricao.desfazer_selecao(by=request.user)
            inscricao.save()
    elif value == 'selecionado':
        if inscricao.aguardando_selecao() or inscricao.nao_selecionado():
            inscricao.selecionar(by=request.user)
            inscricao.save()
    elif value == 'nao_selecionado':
        if inscricao.aguardando_selecao() or inscricao.selecionado():
            inscricao.rejeitar(by=request.user)
            inscricao.save()

    return HttpResponse(status=200)
