# coding=UTF-8

import datetime
import os
import random
from math import ceil, log10
from copy import deepcopy

from django.shortcuts import render, redirect
from django.template import loader
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseNotAllowed, HttpResponseBadRequest
from django.core.exceptions import ValidationError, SuspiciousOperation, PermissionDenied, ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, F, Count, Avg, Max
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.forms.formsets import BaseFormSet, formset_factory
from django.forms import inlineformset_factory
from django.conf import settings
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.postgres.search import SearchVector
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.apps import apps

from .models import Voluntario, AreaTrabalho, AreaAtuacao, Entidade, VinculoEntidade, Necessidade, AreaInteresse, Telefone, Email, RemocaoUsuario, AtividadeAdmin, Usuario, ForcaTarefa, Conteudo, AcessoAConteudo, FraseMotivacional

from allauth.account.models import EmailAddress

from .forms import FormVoluntario, FormEntidade, FormAreaInteresse, FormTelefone, FormEmail
from .auth import ChangeUserProfileForm

from .utils import notifica_aprovacao_voluntario, notifica_aprovacao_entidade

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
                messages.info(request, u'Seu cadastro foi totalmente removido. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.NOTIFY_USER_FROM + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
                try:
                    registro_remocao = RemocaoUsuario()
                    registro_remocao.save()
                    notify_email_template(user_email, u'Remoção de cadastro :-(', 'vol/msg_remocao_usuario.txt', from_email=settings.NOTIFY_USER_FROM)
                except Exception as e:
                    # Se houver erro no envio da notificação, o próprio notify_email_template já tenta avisar o suporte,
                    # portanto só cairá aqui se houver erro nas outras ações
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
                msg = u'Estamos cadastrando pessoas que queiram dedicar parte de seu tempo para ajudar como voluntários a quem precisa. Preencha o formulário abaixo para participar:'

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
                messages.info(request, u'Seu perfil de voluntário foi removido. Note que isto não remove seu cadastro de usuário, ou seja, você continuará podendo entrar no site, podendo inclusive cadastrar um novo perfil de voluntário quando desejar. Se a intenção for remover também seu cadastro de usuário, basta acessar sua <a href="' + reverse('cadastro_usuario') + '">página de dados pessoais</a>. Caso tenha havido algum problema ou insatisfação em decorrência de seu cadastramento no site, por favor <a href="mailto:' + settings.NOTIFY_USER_FROM + '">entre em contato conosco</a> relatando o ocorrido para que possamos melhorar os serviços oferecidos.')
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
                    # Redireciona para página de exibição de mensagem
                    messages.info(request, u'Obrigado! Assim que o seu cadastro for validado ele estará disponível para as entidades. Enquanto isso, você já pode procurar por entidades <a href="' + reverse('mapa_entidades') + '">próximas a você</a> ou que atendam a <a href="' + reverse('busca_entidades') + '">outros critérios de busca</a>.')
                    return mensagem(request, u'Cadastro de Voluntário')
                messages.info(request, u'Alterações gravadas com sucesso!')
        else:
            area_interesse_formset = FormSetAreaInteresse(request.POST, request.FILES)
            
    context = {'form': form, 'area_interesse_formset': area_interesse_formset}
    template = loader.get_template('vol/formulario_voluntario.html')
    return HttpResponse(template.render(context, request))

def tem_acesso_a_voluntarios(request):
    '''Lógica de controle de acesso a busca e visualização de voluntários'''
    if not request.user.is_authenticated:
        messages.info(request, u'Para realizar buscas na base de dados de voluntários é preciso estar cadastrado no sistema como usuário, além de estar vinculado a pelo menos uma entidade com cadastro aprovado. Clique <a href="' + reverse('link_entidade_nova') + '">aqui</a> para dar início a este procedimento.')
        return False

    # Permite que membros da equipe façam consultas
    if not (request.user.is_staff or request.user.has_perm('vol.search_volunteers')):

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
        notify_email_template(email.endereco, u'Confirmação de e-mail de entidade', 'vol/msg_confirmacao_email_entidade.txt', from_email=settings.NOREPLY_EMAIL, context=context)
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
        notify_email_template(entidade.email_principal, u'Confirmação de vínculo com entidade', 'vol/msg_confirmacao_vinculo.txt', from_email=settings.NOREPLY_EMAIL, context=context)
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
                if entidade.aprovado and (nome_fantasia_anterior != request.POST['nome_fantasia'].lower() or razao_social_anterior != request.POST['razao_social'].lower()):
                    entidade.aprovado = None
                    entidade.save(update_fields=['aprovado'])
                    messages.warning(request, u'Atenção: a alteração no nome dá início a uma nova etapa de revisão/aprovação do cadastro da entidade. Aguarde a aprovação para que a entidade volte a aparecer nas buscas.')

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
                    notify_email_template(settings.NOTIFY_USER_FROM, u'Alteração de telefone', 'vol/msg_alteracao_telefone.txt', from_email=settings.NOREPLY_EMAIL, context={'entidade': entidade, 'telefones_anteriores': telefones_anteriores, 'telefones_atuais': telefones_atuais})

            # Nova entidade
            else:

                entidade = form.save(commit=True)
                telformset.instance = entidade
                telformset.save()
                emailformset.instance = entidade
                emailformset.save()

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
               'emailformset': emailformset}
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

            campos_editaveis = ['profissao', 'ddd', 'telefone', 'cidade', 'estado', 'empresa',  'entidade_que_ajudou',  'descricao']

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
                    notifica_aprovacao_voluntario(myvol.usuario)

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

    # Total de voluntários aprovados pelo usuário
    total_vol_pessoal_aprovado = Voluntario.objects.filter(aprovado=True, resp_analise=request.user).count()

    # Percentual de aprovção
    indice_aprovacao_vol_pessoal = None
    if total_vol_pessoal > 0:
        indice_aprovacao_vol_pessoal = round(100*(total_vol_pessoal_aprovado/total_vol_pessoal), 1)

    # Total de entidades que confirmaram o email e estão aguardando aprovação
    total_ents = Email.objects.filter(entidade__aprovado__isnull=True, principal=True, confirmado=True).count()

    # Total de e-mails de entidades descobertos pelo usuário
    total_emails_descobertos = Email.objects.filter(entidade__isnull=False, entidade__aprovado=True, resp_cadastro=request.user).count()

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

    context = {'total_vol': total_vol,
               'tempo_vol': tempo_vol,
               'tempo_vol_max': tempo_vol_max,
               'tempo_vol_recente': tempo_vol_recente,
               'tempo_vol_max_recente': tempo_vol_max_recente,
               'total_vol_dia': total_vol_dia,
               'total_ents': total_ents,
               'total_vol_pessoal': total_vol_pessoal,
               'indice_aprovacao_vol_pessoal': indice_aprovacao_vol_pessoal,
               'total_emails_descobertos': total_emails_descobertos,
               'tarefas': tarefas}
    template = loader.get_template('vol/painel.html')
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
    if conteudo.parametros_url:
        return redirect(reverse(conteudo.nome_url, kwargs=eval(conteudo.parametros_url)))
    return redirect(reverse(conteudo.nome_url))

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
