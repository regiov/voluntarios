# coding=UTF-8

# IMPORTANTE:
#
# Como as rotinas aqui são usadas pelo models.py, não se pode importar modelos em novas rotinas pois dá erro.
#

import urllib.parse

from django.db.models.signals import post_init
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from notification.utils import notify_user_msg, notify_email_msg, notify_email
from notification.models import Message, Event

def track_data(*fields):
    """
    Source: https://gist.github.com/dcramer/730765
    
    Tracks property changes on a model instance.
    
    The changed list of properties is refreshed on model initialization
    and save.
    
    >>> @track_data('name')
    >>> class Post(models.Model):
    >>>     name = models.CharField(...)
    >>> 
    >>>     @classmethod
    >>>     def post_save(cls, sender, instance, created, **kwargs):
    >>>         if instance.has_changed('name'):
    >>>             print("Hooray!")
    """
    
    UNSAVED = dict()

    def _store(self):
        "Updates a local copy of attributes values"
        if self.id:
            self.__data = dict((f, getattr(self, f)) for f in fields)
        else:
            self.__data = UNSAVED

    def inner(cls):
        # contains a local copy of the previous values of attributes
        cls.__data = {}

        def has_changed(self, field):
            "Returns ``True`` if ``field`` has changed since initialization."
            if self.__data is UNSAVED:
                return False
            return self.__data.get(field) != getattr(self, field)
        cls.has_changed = has_changed

        def old_value(self, field):
            "Returns the previous value of ``field``"
            return self.__data.get(field)
        cls.old_value = old_value

        def whats_changed(self):
            "Returns a list of changed attributes."
            changed = {}
            if self.__data is UNSAVED:
                return changed
            for k, v in iter(self.__data.items()):
                if v != getattr(self, k):
                    changed[k] = v
            return changed
        cls.whats_changed = whats_changed

        # Ensure we are updating local attributes on model init
        def _post_init(sender, instance, **kwargs):
            _store(instance)
        post_init.connect(_post_init, sender=cls, weak=False)

        # Ensure we are updating local attributes on model save
        def save(self, *args, **kwargs):
            save._original(self, *args, **kwargs)
            _store(self)
        save._original = cls.save
        cls.save = save
        return cls
    return inner

def detecta_alteracoes(campos_rastreados, obj1, obj2, atualiza=False):
    '''Detecta alterações entre obj1 e obj2 considerando os atributos passados como parâmetro.
    obj1 é sempre a instância de um modelo. obj2 pode ser outra instância do mesmo modelo ou
    request com dicionário POST. O parâmetro "atualiza" pode ser usado para atualizar os
    campos em obj1 de acordo com os valores em obj2.'''
    
    alteracoes = {} # {campo: {'antes': val1, 'depois': val2}}

    for campo in campos_rastreados:
        if not hasattr(obj2, 'POST') or campo in obj2.POST:
            antes = getattr(obj1, campo)
            if hasattr(obj2, 'POST'):
                depois = obj2.POST.get(campo)
            else:
                depois = getattr(obj2, campo)
            # Comparação por string para evitar diferenças do tipo 0 x "0" em atributos
            # numéricos passados como parâmetro POST
            if str(antes) != str(depois):
                alteracoes[campo] = {'antes': antes, 'depois': depois}
                if atualiza:
                    setattr(obj1, campo, depois)

    return alteracoes

def resume_alteracoes(alteracoes):
    '''Retorna uma string representando as alteracoes retornadas pela função "detecta_alteracoes"
    no formato: campo1: valor original -> valor novo\ncampo2: valor original -> valor novo'''
    dif = ''
    for campo, alteracao in alteracoes.items():
        if len(dif) > 0:
            dif = dif + "\n"
        dif = dif + campo + ': ' + str(alteracao['antes']) + ' -> ' + str(alteracao['depois'])
    return dif

def notifica_aprovacao_voluntario(usuario):
    '''Envia e-mail comunicando ao usuário a aprovação do seu perfil'''
    # Se o usuário nunca recebeu o aviso de aprovação
    msg = Message.objects.get(code='AVISO_APROVACAO_VOLUNTARIO_V5')
    if Event.objects.filter(user=usuario, message=msg).count() == 0:
        # Envia notificação
        notify_user_msg(usuario, msg, context={'usuario': usuario})

def notifica_aprovacao_entidade(entidade):
    '''Envia e-mail comunicando à entidade a aprovação do seu cadastro'''
    # Se a entidade nunca recebeu o aviso de aprovação
    msg = Message.objects.get(code='AVISO_APROVACAO_ENTIDADE')
    if Event.objects.filter(object_id=entidade.id, content_type=ContentType.objects.get_for_model(entidade).id, message=msg).count() == 0:
        # Envia notificação para a entidade
        notify_email_msg(entidade.email_principal, msg, content_obj=entidade)
        # Envia notificação para responsáveis pelo onboarding
        if hasattr(settings, 'ONBOARDING_TEAM_EMAIL'):
             notify_email(settings.ONBOARDING_TEAM_EMAIL, '\o/ Nova entidade aprovada!', 'Ei! O cadastro da entidade ' + entidade.menor_nome() + ' acaba de ser aprovado no Voluntários. Você está recebendo esse e-mail porque faz parte da equipe de boas-vindas. Use esse link para recepcionar a entidade: https://voluntarios.com.br' + reverse('onboarding_entidades'))

def notifica_processo_seletivo_aguardando_aprovacao(processo_seletivo):
    '''Envia e-mail comunicando ao RH a existência de processo seletivo aguardando aprovação'''
    if hasattr(settings, 'RH_TEAM_EMAIL'):
        notify_email(settings.RH_TEAM_EMAIL, '\o/ Novo processo seletivo!', "Ei! Tem um novo processo seletivo aguardando aprovação:\n\nEntidade: " + processo_seletivo.entidade.menor_nome() + "\nVaga: " + processo_seletivo.titulo + "\n\nVocê está recebendo este e-mail porque faz parte da equipe de RH. Assim que puder, acesse o painel de controle para fazer a revisão: https://voluntarios.com.br" + reverse('revisao_processos_seletivos'))

def monta_query_string(request, excluir=['page', 'csrfmiddlewaretoken']):
    '''Monta query string para ser usada em URLs a partir dos parâmetros GET,
    excluindo parâmetros especificados'''
    params = request.GET.copy()
    for key in excluir:
        if key in params:
            del params[key]
    return urllib.parse.urlencode(params)

def elabora_paginacao(request, qs, registros_por_pagina=20, paginas_visiveis=10):
    '''Determina variáveis de paginação para poder usar o template paginador.html'''
    get_params = monta_query_string(request)
    pagina_inicial = pagina_final = None
    paginador = Paginator(qs, registros_por_pagina)
    pagina = request.GET.get('page')
    try:
        new_qs = paginador.page(pagina)
    except PageNotAnInteger:
        # Se a página não é um número inteiro, exibe a primeira
        new_qs = paginador.page(1)
    except EmptyPage:
        # Se a página está fora dos limites (ex 9999), exibe a última
        new_qs = paginador.page(paginador.num_pages)
    pagina_atual = new_qs.number
    intervalo = paginas_visiveis/2
    pagina_inicial = pagina_atual - intervalo
    pagina_final = pagina_atual + intervalo -1
    if pagina_inicial <= 0:
        pagina_final = pagina_final - pagina_inicial + 1
        pagina_inicial = 1
    if pagina_final > paginador.num_pages:
        pagina_final = paginador.num_pages
        pagina_inicial = max(pagina_final - (2*intervalo) + 1, 1)

    return (new_qs, get_params, pagina_inicial, pagina_final)
