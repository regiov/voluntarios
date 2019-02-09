# coding=UTF-8

import datetime
import os
import random

from django.shortcuts import render, redirect
from django.template import loader
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseNotAllowed, HttpResponseBadRequest
from django.core.exceptions import ValidationError, SuspiciousOperation, PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.forms.formsets import BaseFormSet, formset_factory
from django.conf import settings
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.postgres.search import SearchVector

from vol.models import Voluntario, AreaTrabalho, AreaAtuacao, Entidade, VinculoEntidade, Necessidade, AreaInteresse

from allauth.account.models import EmailAddress

from vol.forms import FormVoluntario, FormEntidade, FormAreaInteresse
from vol.util import ChangeUserProfileForm

from notification.utils import notify_support, notify_email

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

@login_required
@transaction.atomic
def cadastro_usuario(request):
    template = loader.get_template('vol/formulario_usuario.html')
    if request.method == 'POST':

        if 'delete' in request.POST:
            user_email = request.user.email
            notify_support(u'Remoção de usuário', user_email, request)
            user = request.user
            logout(request)
            try:
                user.delete()
                messages.info(request, u'Seu cadastro foi totalmente removido. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.NOTIFY_USER_FROM + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
                try:
                    notify_email(user_email, u'Remoção de cadastro :-(', 'vol/msg_remocao_usuario.txt', from_email=settings.NOTIFY_USER_FROM)
                except Exception as e:
                    # Se houver erro o próprio notify_email já tenta notificar o suporte,
                    # portanto só cairá aqui se houver erro na notificação ao suporte
                    pass
            except Exception as e:
                messages.warning(request, u'Não foi possível remover o seu cadastro. Caso em algum momento você tenha auxiliado na parte administrativa do site, é possível que haja referências importantes a você no histórico de nosso banco de dados. Neste caso entre em contato conosco se realmente deseja remover seu cadastro. Caso nunca tenha trabalhado na parte administrativa do site, por favor <a href="mailto:' + settings.NOTIFY_USER_FROM + '">entre em contato conosco</a> para verificarmos o que houve.')

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
                return redirect('/aut/signin')
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

            if msg is None:
                msg = u'Estamos cadastrando profissionais que queiram dedicar parte de seu tempo para ajudar como voluntários a quem precisa. Preencha o formulário abaixo para participar:'

            form = FormVoluntario()
            area_interesse_formset = FormSetAreaInteresse()

        if msg:
            messages.info(request, msg)
        
    if request.method == 'POST':
        agradece_cadastro = False
        if request.user.is_voluntario:

            if 'delete' in request.POST:
                notify_support(u'Remoção de perfil de voluntário', request.user.email, request)
                request.user.voluntario.delete()
                # Redireciona para página de exibição de mensagem
                messages.info(request, u'Seu perfil de voluntário foi removido. Note que isto não remove seu cadastro de usuário, ou seja, você continuará podendo entrar no site, podendo inclusive cadastrar um novo perfil de voluntário quando desejar. Se a intenção for remover também seu cadastro de usuário, basta acessar sua <a href="' + reverse('cadastro_usuario') + '">página de dados pessoais</a>. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.NOTIFY_USER_FROM + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
                return mensagem(request, u'Remoção de Perfil de Voluntário')
            
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

    if not request.user.is_authenticated:
        messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar cadastrado no sistema como usuário, além de estar vinculado a pelo menos uma entidade com cadastro aprovado. Clique <a href="' + reverse('link_entidade_nova') + '">aqui</a> para dar início a este procedimento.')
        return mensagem(request, u'Busca de voluntários')

    # Permite que membros da equipe façam consultas
    if not (request.user.is_staff or request.user.has_perm('vol.search_volunteers')):

        # Do contrário apenas usuários com entidades aprovadas
        if not request.user.has_entidade:
            messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar vinculado a pelo menos uma entidade com cadastro aprovado. Clique <a href="' + reverse('link_entidade_nova') + '">aqui</a> para dar início a este procedimento.')
            return mensagem(request, u'Busca de voluntários')

        if not request.user.has_entidade_aprovada:
            messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar vinculado a pelo menos uma entidade com cadastro aprovado. Pedimos que aguarde a aprovação da entidade cadastrada.')
            return mensagem(request, u'Busca de voluntários')

    areas_de_trabalho = AreaTrabalho.objects.all().order_by('nome')
    areas_de_interesse = AreaAtuacao.objects.all().order_by('indice')
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

        # Filtro por palavras-chave
        fpalavras = request.GET.get('fpalavras')
        if fpalavras is not None and len(fpalavras) > 0:
            voluntarios = voluntarios.annotate(search=SearchVector('profissao', 'descricao')).filter(search=fpalavras).distinct()

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
        ordem = request.GET.get('ordem', 'interesse')
        if ordem == 'trabalho':
            voluntarios = voluntarios.order_by('area_trabalho__nome', 'usuario__nome')
        elif ordem == 'nome':
            voluntarios = voluntarios.order_by('usuario__nome', 'area_trabalho__nome')
        else: # interesse
            voluntarios = voluntarios.order_by('areainteresse__area_atuacao__nome', 'usuario__nome')

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

def envia_confirmacao_email_entidade(request, entidade):
    context = {'nome': entidade.menor_nome(),
               'scheme': 'https' if request.is_secure() else 'http',
               'host': request.get_host(),
               'key': entidade.hmac_key()}
    try:
        notify_email(entidade.email, u'Confirmação de e-mail de entidade', 'vol/msg_confirmacao_email_entidade.txt', from_email=settings.NOREPLY_EMAIL, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

@login_required
def lista_entidades_vinculadas(request):
    '''Lista entidades gerenciadas pelo usuário'''
    context = {'entidades': request.user.entidades()}
    template = loader.get_template('vol/lista_entidades.html')
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
    envia_confirmacao_email_entidade(request, entidade)
    messages.info(request, u'Mensagem de confirmação reenviada. Verifique a caixa postal do e-mail da entidade e clique no link fornecido na mensagem.')
    # Melhor redirecionar para evitar link recarregável indesejado
    return redirect('/entidade/cadastro')

def valida_email_entidade(request):
    '''Valida e-mail de uma entidade com base no parâmetro t que deverá conter a chave HMAC da entidade.
    OBS: esta função também pode ser chamada pela interface administrativa.'''
    metodos = ['GET']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)
    if 't' not in request.GET:
        return HttpResponseBadRequest('Ausência do parâmetro t')
    entidade = Entidade.objects.from_hmac_key(request.GET['t'])
    if entidade is None:
        messages.error(request, u'Não foi possível validar o e-mail. Certifique-se de ter usado corretamente o link fornecido na mensagem. Na dúvida, copie o link manualmente e cole no campo de endereço do seu navegador. Se o problema persistir, entre em contato conosco.')
        return mensagem(request, u'Validação de e-mail de entidade')
    entidade.confirmado = True
    entidade.confirmado_em = datetime.datetime.now()
    entidade.save(update_fields=['confirmado', 'confirmado_em'])
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
    if not entidade.email:
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
        notify_email(entidade.email, u'Confirmação de vínculo com entidade', 'vol/msg_confirmacao_vinculo.txt', from_email=settings.NOREPLY_EMAIL, context=context)
    except Exception as e:
        # Se houver erro o próprio notify_email já tenta notificar o suporte,
        # portanto só cairá aqui se houver erro na notificação ao suporte
        pass

    messages.info(request, u'Acabamos de enviar uma mensagem para o e-mail ' + entidade.email + '. Alguém com acesso à caixa postal da entidade deverá clicar no link fornecido na mensagem para confirmar a existência do seu vínculo com a entidade, permitindo que você possa editar os dados cadastrais da mesma. Entre em contato com a pessoa se necessário.')
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
    # Se houver outras entidades com o mesmo e-mail sem ninguém vinculado a elas, já cria outros vínculos com o mesmo usuário
    entidades_com_mesmo_email = Entidade.objects.filter(email=vinculo.entidade.email).exclude(pk=vinculo.entidade.pk)
    for entidade_irma in entidades_com_mesmo_email:
        if VinculoEntidade.objects.filter(entidade=entidade_irma).count() == 0:
            novo_vinculo = VinculoEntidade(entidade=entidade_irma, usuario=request.user, confirmado=True)
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
        else:
            
            if 'nova' in request.GET:
                
                form = FormEntidade()
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
            email_anterior = entidade.email.lower()
            nome_fantasia_anterior = entidade.nome_fantasia.lower()
            razao_social_anterior = entidade.razao_social.lower()
            endereco_original = entidade.endereco()

            form = FormEntidade(request.POST, instance=entidade)
        else:
            form = FormEntidade(request.POST)
        
        if form.is_valid():

            # Entidade já cadastrada no banco
            if entidade is not None:

                entidade = form.save(commit=False)
                entidade.ultima_atualizacao = datetime.datetime.now()
                entidade.save()
                messages.info(request, u'Alterações gravadas com sucesso!')

                if email_anterior != request.POST['email'].lower():
                    # Se alterou o email, força nova confirmação
                    entidade.confirmado = False
                    entidade.save(update_fields=['confirmado'])
                    # Envia mensagem com link de confirmação
                    envia_confirmacao_email_entidade(request, entidade)
                    messages.info(request, u'Verifique a caixa postal da entidade para efetuar a validação do novo e-mail.')

                # Força reaprovação de cadastro caso dados importantes tenham mudado
                if entidade.aprovado and (nome_fantasia_anterior != request.POST['nome_fantasia'].lower() or razao_social_anterior != request.POST['razao_social'].lower()):
                    entidade.aprovado = None
                    entidade.save(update_fields=['aprovado'])
                    messages.warning(request, u'Atenção: a alteração no nome dá início a uma nova etapa de revisão/aprovação do cadastro da entidade. Aguarde a aprovação para que a entidade volte a aparecer nas buscas.')

                # Caso tenha alterado o endereço, tenta georreferenciar novamente
                if endereco_original != entidade.endereco():
                    entidade.geocode()

            # Nova entidade
            else:

                entidade = form.save(commit=True)

                msg = u'Entidade cadastrada com sucesso!'

                # Se o email já existe no sistema e já foi confirmado por alguém anteriormente
                if EmailAddress.objects.filter(email__iexact=entidade.email, verified=True).count() > 0 or Entidade.objects.filter(email__iexact=entidade.email, confirmado=True).count() > 0:

                    entidade.confirmado = True
                    entidade.save(update_fields=['confirmado'])
                    msg = msg + u' Aguarde a aprovação do cadastro para que ela comece a aparecer nas buscas.'
                    
                else:
                
                    # Do contrário dispara nova confirmação de e-mail
                    envia_confirmacao_email_entidade(request, entidade)
                    msg = msg + u' Como o e-mail da entidade é novo, acesse a caixa postal dele para validá-lo. Caso não tenha recebido, verifique a pasta de spam ou clique no botão "reenviar" abaixo.'

                messages.info(request, msg)

                # Tenta georeferenciar
                entidade.geocode()
                
                # Vincula usuário à entidade
                vinculo = VinculoEntidade(usuario=request.user, entidade=entidade, confirmado=True)
                vinculo.save()

            # Exibe lista de entidades
            return redirect('/entidade/cadastro')

    # Exibe formulário de cadastro de entidade
    context = {'form': form}
    template = loader.get_template('vol/formulario_entidade.html')
    return HttpResponse(template.render(context, request))

def busca_entidades(request):
    '''Página de busca de entidades'''
    # Obs: Existe pelo menos um site externo que faz buscas com POST
    metodos = ['GET', 'POST']
    if request.method not in (metodos):
        return HttpResponseNotAllowed(metodos)

    areas_de_atuacao = AreaAtuacao.objects.all().order_by('indice')

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
                entidades = entidades.filter(Q(nome_fantasia__icontains=fentidade) | Q(razao_social__icontains=fentidade))

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
        #raise SuspiciousOperation('Entidade inexistente')
        raise Http404
    entidade.hit()
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
        return HttpResponseBadRequest('Ausência do parâmetro colocweb')
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

        doacoes = Necessidade.objects.select_related('entidade').filter(entidade__isnull=False)

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
                         'idade': vol.idade(),
                         'cidade': vol.cidade.title(),
                         'estado': vol.estado.upper()})

@login_required
def redirect_login(request):
    "Redireciona usuário após login bem sucedido"
    # Se o link original de cadastro era para voluntário
    if request.user.link == 'voluntario_novo':
        if request.user.is_voluntario:
            # Se já é voluntário, busca entidades
            return redirect(reverse('busca_entidades'))
        # Caso contrário exibe página de cadastro
        return cadastro_voluntario(request, msg=u'Para finalizar o cadatro de voluntário, complete o formulário abaixo:')
    elif request.user.link == 'entidade_nova':
        # Exibe página de cadastro de entidade
        return cadastro_entidade(request)

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
