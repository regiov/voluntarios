# coding=UTF-8

from django.contrib import admin, messages
from django.contrib.gis.admin import GeoModelAdmin
from django.templatetags.static import static
from django.db import transaction, DatabaseError
from django.utils.translation import gettext, gettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Count, Q, TextField, CharField
from django import forms
from django.urls import reverse
from django.shortcuts import redirect
from django.utils.safestring import mark_safe

from datetime import datetime

from django.contrib.flatpages.admin import FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from tinymce.widgets import TinyMCE

from mptt.admin import DraggableMPTTAdmin, TreeRelatedFieldListFilter

from vol.models import Usuario, AreaTrabalho, AreaAtuacao, Voluntario, Entidade, VinculoEntidade, Necessidade, AreaInteresse, AnotacaoEntidade, TipoDocumento, Documento, Telefone, Email, FraseMotivacional, ForcaTarefa, Conteudo, AcessoAConteudo, TipoArtigo, NecessidadeArtigo, Funcao, PostagemBlog

from notification.models import Message
from notification.utils import notify_user_msg

from vol.views import envia_confirmacao_email_entidade

from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation

from .utils import notifica_aprovacao_voluntario

# Usuário customizado
from django.contrib.auth.admin import UserAdmin

class MyUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('nome',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'nome', 'date_joined', 'email_confirmado')
    search_fields = ('nome', 'email')
    ordering = ('-date_joined',)
    actions = ['reenviar_confirmacao', 'reenviar_lembrete_voluntario']

    # Desabilita inclusão, forçando novos cadastros a serem feitos todos pelo site normal,
    # do contrário será necessário fazer uma série de customizações aqui para incluir
    # o campo nome, incluir o e-mail em account_emailaddress, além da questão de não ser
    # possível terceirizar a aceitação dos termos de uso.
    def has_add_permission(self, request):
        return False

    def email_confirmado(self, instance):
        return EmailAddress.objects.filter(user=instance, email=instance.email, verified=True).exists()
    email_confirmado.boolean = True
    email_confirmado.short_description = u'E-mail confirmado'

    def reenviar_confirmacao(self, request, queryset):
        num_messages = 0
        for obj in queryset:
            if not self.email_confirmado(obj):
                send_email_confirmation(request, obj)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s usuário(s) notificado(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s usuário(s) não notificado(s) por já possuir(em) e-mail confirmado.' % (total_recs-num_messages)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    reenviar_confirmacao.short_description = "Reenviar mensagem de confirmação de email"

    def reenviar_lembrete_voluntario(self, request, queryset):
        msg = Message.objects.get(code='LEMBRETE_CADASTRO_VOLUNTARIO')
        num_messages = 0
        for obj in queryset:
            if not obj.is_voluntario:
                notify_user_msg(obj, msg)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s usuário(s) notificado(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s usuário(s) não notificado(s) por já ter(em) se cadastrado como voluntário(s).' % (total_recs-num_messages)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    reenviar_lembrete_voluntario.short_description = "Reenviar lembrete de finalização de cadastro de voluntário"

class MyFlatPageAdmin(FlatPageAdmin):

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'content':
            return db_field.formfield(widget=TinyMCE(
                attrs={'cols': 100, 'rows': 20},
                mce_attrs={'external_link_list_url': reverse('tinymce-linklist')},
                ))
        return super(MyFlatPageAdmin, self).formfield_for_dbfield(db_field, **kwargs)

class AreaTrabalhoAdmin(admin.ModelAdmin):
    pass

class AreaAtuacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'indice')
    fields = ['nome', 'categoria', 'indice', 'id_antigo',]
    readonly_fields = ['id_antigo']

class AreaInteresseInline(admin.TabularInline):
    model = AreaInteresse
    fields = ['area_atuacao',]
    extra = 0

class VoluntarioAdmin(admin.ModelAdmin):
    list_select_related = ('usuario',)
    list_display = ('nome_usuario', 'email_usuario', 'data_cadastro', 'email_confirmado', 'aprovado',)
    ordering = ('-data_cadastro',)
    search_fields = ('usuario__nome', 'usuario__email', )
    list_filter = ('aprovado',)
    preserve_filters = True
    readonly_fields = ('usuario', 'data_aniversario_orig', 'ciente_autorizacao', 'site', 'importado', 'invisivel',)
    actions = ['aprovar', 'notificar_aprovacao']
    inlines = [
        AreaInteresseInline,
    ]
    fields = ('usuario', 'data_aniversario_orig', 'data_aniversario', 'ciente_autorizacao', 'profissao', 'ddd', 'telefone', 'cidade', 'estado', 'empregado', 'empresa', 'foi_voluntario', 'entidade_que_ajudou', 'area_trabalho', 'descricao', 'newsletter', 'fonte', 'site', 'importado', 'aprovado', 'invisivel',)

    def get_queryset(self, request):
        qs = super(VoluntarioAdmin, self).get_queryset(request)
        # Inclui campo de confirmação de e-mail
        return qs.annotate(num_emails_confirmados=Count('usuario__emailaddress', filter=Q(usuario__emailaddress__verified=True)))

    def nome_usuario(self, instance):
        if instance.usuario:
            return instance.usuario.nome
        return '(vazio)'
    nome_usuario.short_description = u'Nome'
    nome_usuario.admin_order_field = 'usuario__nome'

    def email_usuario(self, instance):
        if instance.usuario:
            return format_html('<a href="../usuario/' + str(instance.usuario.id) + '/change/">' + instance.usuario.email + '</a>')
        return '(vazio)'
    email_usuario.short_description = u'E-mail'
    email_usuario.admin_order_field = 'usuario__email'

    def email_confirmado(self, instance):
        return instance.num_emails_confirmados > 0
    email_confirmado.boolean = True
    email_confirmado.short_description = u'E-mail confirmado'
    email_confirmado.admin_order_field = 'num_emails_confirmados'

    @transaction.atomic
    def aprovar(self, request, queryset):
        num_updates = 0
        for obj in queryset:
            if not obj.aprovado:
                obj.aprovado = True
                obj.save(update_fields=['aprovado'])
                num_updates = num_updates + 1
        main_msg = ''
        if num_updates > 0:
            main_msg = u'%s voluntário(s) aprovado(s). ' % num_updates
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_updates:
            extra_msg = u'%s não modificado(s) por já estar(em) aprovado(s).' % (total_recs-num_updates)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    aprovar.short_description = "Aprovar Voluntários selecionados"

    def notificar_aprovacao(self, request, queryset):
        num_messages = 0
        for obj in queryset:
            if obj.aprovado:
                notifica_aprovacao_voluntario(obj.usuario)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s voluntário(s) notificado(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s voluntário(s) não notificado(s) por ainda não terem sido aprovados.' % (total_recs-num_messages)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    notificar_aprovacao.short_description = "Reenviar notificação de aprovação de cadastro"

class RevisaoVoluntario(Voluntario):
    """Modelo criado para avaliar as análises de cadastro de voluntários via interface administrativa"""
    class Meta:
        proxy = True
        verbose_name = u'Revisão de voluntário'
        verbose_name_plural = u'Revisões de voluntários'

class RevisaoVoluntarioAdmin(admin.ModelAdmin):
    list_select_related = ('usuario', 'resp_analise',)
    list_display = ('data_analise', 'nome_responsavel', 'nome_voluntario', 'aprovado',)
    ordering = ('-data_analise',)
    search_fields = ('usuario__nome', 'usuario__email', )
    list_filter = ('aprovado', ('resp_analise', admin.RelatedOnlyFieldListFilter),)
    preserve_filters = True
    readonly_fields = ('usuario', 'resp_analise', 'data_analise', 'aprovado', 'dif_analise',)
    fields = ('usuario', 'resp_analise', 'data_analise', 'aprovado', 'dif_analise',)

    # Exibe apenas cadastros em que há um responsável pela análise
    def get_queryset(self, request):
        qs = super(RevisaoVoluntarioAdmin, self).get_queryset(request)
        return qs.filter(resp_analise__isnull=False)

    def nome_voluntario(self, instance):
        if instance.usuario:
            return format_html('<a href="../usuario/' + str(instance.usuario.id) + '/change/"><img src="' + static('images/misc/user.svg') + '" alt="True" title="editar usuário" style="margin-right:5px;"></a>' + '<a href="../voluntario/' + str(instance.id) + '/change/"><img src="' + static('images/misc/profile.svg') + '" alt="True" title="editar voluntário" style="margin-right:5px;"></a>' + instance.usuario.nome)
        return '(vazio)'
    nome_voluntario.short_description = u'Nome do voluntário'
    nome_voluntario.admin_order_field = 'usuario__nome'

    def nome_responsavel(self, instance):
        if instance.resp_analise:
            return instance.resp_analise.nome
        return '(vazio)'
    nome_responsavel.short_description = u'Responsável pela análise'
    nome_responsavel.admin_order_field = 'resp_analise__nome'

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(RevisaoVoluntarioAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

class EmailEntidadeInline(admin.TabularInline):
    model = Email
    fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao', 'resp_cadastro', 'data_cadastro', 'com_problema']
    readonly_fields = ['confirmado', 'data_confirmacao', 'resp_cadastro', 'data_cadastro']
    extra = 0

class EmailNovoEntidadeInline(admin.TabularInline):
    model = Email
    fields = ['endereco', 'principal']
    extra = 0

class ReadOnlyEmailEntidadeInline(admin.TabularInline):
    model = Email
    fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao', 'com_problema']
    readonly_fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao', 'com_problema']
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class TelEntidadeInline(admin.TabularInline):
    model = Telefone
    fields = ['tipo', 'prefixo', 'numero', 'contato', 'confirmado', 'data_confirmacao', 'confirmado_por']
    readonly_fields = ['data_confirmacao', 'confirmado_por']
    extra = 0
    # Para diminuir o tamanho dos campos
    formfield_overrides = {
        CharField: {'widget': forms.TextInput(attrs={'size':10})},
    }


class ReadOnlyTelEntidadeInline(admin.TabularInline):
    model = Telefone
    fields = ['tipo', 'prefixo', 'numero', 'contato', 'confirmado', 'data_confirmacao', 'confirmado_por']
    readonly_fields = ['tipo', 'prefixo', 'numero', 'contato', 'data_confirmacao', 'confirmado_por']
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class VinculoEntidadeInline(admin.TabularInline):
    model = VinculoEntidade
    fields = ['usuario', 'data_inicio', 'data_fim', 'confirmado']
    raw_id_fields = ('usuario',)
    readonly_fields = ['data_inicio']
    extra = 0

class ReadOnlyVinculoEntidadeInline(admin.TabularInline):
    model = VinculoEntidade
    fields = ['usuario', 'data_inicio', 'data_fim', 'confirmado']
    readonly_fields = ['usuario', 'data_inicio', 'data_fim', 'confirmado']
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class NecessidadeInline(admin.TabularInline):
    model = Necessidade
    fields = ['qtde_orig', 'descricao', 'valor_orig', 'data_solicitacao',]
    readonly_fields = ['data_solicitacao']
    extra = 0

class NecessidadeArtigoInline(admin.TabularInline):
    model = NecessidadeArtigo
    fields = ['tipoartigo',]
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super(NecessidadeArtigoInline, self).formfield_for_dbfield(db_field, **kwargs)
        # Remove opções de editar tipos de artigos
        if db_field.name == 'tipoartigo':
            formfield.widget.can_add_related = False
            formfield.widget.can_change_related = False
            formfield.widget.can_delete_related = False
        return formfield

class DocumentoInline(admin.TabularInline):
    model = Documento
    fields = ['tipodoc', 'doc', 'data_cadastro', 'usuario']
    readonly_fields = ['data_cadastro', 'usuario']
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super(DocumentoInline, self).formfield_for_dbfield(db_field, **kwargs)
        # Remove opções de editar tipos de artigos
        if db_field.name == 'tipodoc':
            formfield.widget.can_add_related = False
            formfield.widget.can_change_related = False
            formfield.widget.can_delete_related = False
        return formfield

class AnotacaoEntidadeInline(admin.TabularInline):
    model = AnotacaoEntidade
    fields = ['anotacao', 'req_acao', 'usuario', 'momento']
    readonly_fields = ['usuario', 'momento']
    extra = 0
    formfield_overrides = {
        TextField: {'widget': forms.Textarea(attrs={'rows':2, 'cols':75})},
    } 

class AntigaAnotacaoEntidadeInline(admin.TabularInline):
    model = AnotacaoEntidade
    verbose_name = "Anotação anterior"
    verbose_name_plural = "Anotações anteriores"
    fields = ['anotacao', 'req_acao', 'usuario', 'momento']
    readonly_fields = ['anotacao', 'req_acao', 'usuario', 'momento']
    extra = 0

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class NovaAnotacaoEntidadeInline(admin.TabularInline):
    model = AnotacaoEntidade
    verbose_name = "Nova anotação"
    verbose_name_plural = "Novas anotações"
    fields = ['anotacao', 'req_acao']
    extra = 0
    formfield_overrides = {
        TextField: {'widget': forms.Textarea(attrs={'rows':2, 'cols':75})},
    } 

    # Esta configuração esconde anotações existentes!
    def has_change_permission(self, request, obj=None):
        return False

    # Para Django > 2.1 deve-se desabilitar a "view permission" também
    # (https://docs.djangoproject.com/en/2.2/releases/2.1/#what-s-new-in-django-2-1)
    def has_view_permission(self, request, obj=None):
        return False

class BaseEntidadeAdmin(admin.ModelAdmin):
    exclude = ('coordenadas', 'voluntarios', 'qtde_visualiza', 'ultima_visualiza', 'ultima_revisao', 'data_analise', 'resp_analise', 'data_bloqueio', 'resp_bloqueio', 'confirmado', 'confirmado_em', 'situacao_cnpj', 'motivo_situacao_cnpj', 'data_situacao_cnpj', 'situacao_especial_cnpj', 'data_situacao_especial_cnpj', 'ultima_atualizacao_cnpj', 'data_consulta_cnpj', 'erro_consulta_cnpj', 'resp_onboarding', 'data_resp_onboarding', 'assunto_msg_onboarding', 'msg_onboarding', 'assinatura_onboarding', 'data_envio_onboarding', 'total_envios_onboarding', 'falha_envio_onboarding', 'data_visualiza_onboarding', 'data_ret_envio_onboarding', 'link_divulgacao_onboarding', 'cancelamento_onboarding',)

    # Gravações automáticas na Entidade
    def save_model(self, request, obj, form, change):
        # Como o track_data não funciona aqui, temos que pegar o valor do banco
        old_aprovado = None
        if obj.id:
            old_aprovado = Entidade.objects.get(pk=obj.id).aprovado
        # Se aprovou ou rejeitou cadastro
        if old_aprovado is None and obj.aprovado is not None and obj.resp_analise is None:
            # Grava o responsável pela análise
            obj.resp_analise = request.user
            obj.data_analise = timezone.now()
        super().save_model(request, obj, form, change)

    # Gravações automáticas nos modelos relacionados
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            # Alterações em Anotações ou Documentos
            if isinstance(instance, AnotacaoEntidade) or isinstance(instance, Documento):
                if instance.usuario_id is None:
                    # Grava usuário corrente em anotações e documentos
                    instance.usuario = request.user
            # Alterações em Telefones
            if isinstance(instance, Telefone):
                # Atualiza dados de confirmação se necessário
                if instance.confirmado:
                    if instance.confirmado_por is None:
                        instance.confirmado_por = request.user
                    if instance.data_confirmacao is None:
                        instance.data_confirmacao = timezone.now()
                else:
                    if instance.confirmado_por is not None:
                        instance.confirmado_por = None
                    instance.data_confirmacao = None
                # Apenas para novos telefones
                if instance.id is None:
                    instance.resp_cadastro = request.user
                    instance.data_cadastro = timezone.now()
            # Alterações em Emails
            if isinstance(instance, Email):
                # Apenas para novos emails
                if instance.id is None:
                    instance.resp_cadastro = request.user
                    instance.data_cadastro = timezone.now()
            # Alterações em artigos aceitos como doação
            if isinstance(instance, NecessidadeArtigo):
                # Apenas para novos itens
                if instance.id is None:
                    instance.resp_cadastro = request.user
                    instance.data_cadastro = timezone.now()
            instance.save()
        formset.save_m2m()
        # Neste ponto já gravou alterações nos e-mails, então pode verificar unicidade do principal
        form.instance.verifica_email_principal()

    def email_confirmado(self, instance):
        return instance.email_principal_confirmado
    email_confirmado.boolean = True
    email_confirmado.short_description = u'E-mail confirmado'

class EntidadeAdmin(GeoModelAdmin, BaseEntidadeAdmin):
    list_display = ('razao_social', 'cnpj', 'email_principal', 'data_cadastro', 'email_confirmado', 'aprovado',)
    ordering = ('-aprovado', '-data_cadastro',)
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj', 'email_set__endereco',)
    list_filter = ('aprovado', 'importado',)
    preserve_filters = True
    readonly_fields = ('geocode_status', 'importado',)
    actions = ['aprovar', 'enviar_confirmacao']
    inlines = [
        EmailEntidadeInline, TelEntidadeInline, VinculoEntidadeInline, DocumentoInline, NecessidadeArtigoInline, NecessidadeInline, AnotacaoEntidadeInline
    ]

    @transaction.atomic
    def aprovar(self, request, queryset):
        num_updates = 0
        for obj in queryset:
            if not obj.aprovado:
                obj.aprovado = True
                obj.save(update_fields=['aprovado'])
                num_updates = num_updates + 1
        main_msg = ''
        if num_updates > 0:
            main_msg = u'%s entidade(s) aprovada(s). ' % num_updates
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_updates:
            extra_msg = u'%s não modificada(s) por já estar(em) aprovada(s).' % (total_recs-num_updates)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    aprovar.short_description = "Aprovar Entidades selecionadas"

    def enviar_confirmacao(self, request, queryset):
        num_messages = 0
        for obj in queryset:
            if not obj.email_principal_confirmado:
                envia_confirmacao_email_entidade(request, obj.email_principal_obj)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s entidade(s) notificada(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s não notificada(s) por já possuir(em) e-mail confirmado.' % (total_recs-num_messages)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    enviar_confirmacao.short_description = "Enviar nova mensagem de confirmação de e-mail"

class EntidadeSemEmail(Entidade):
    """Modelo criado para adicionar e-mail a entidades antigas via interface adm"""
    class Meta:
        proxy = True
        verbose_name = u'Entidade sem e-mail'
        verbose_name_plural = u'Entidades sem e-mail'

class FiltroPorCidade(admin.SimpleListFilter):
    '''Filtro customizado para cidades'''
    title = u'Cidade'

    parameter_name = 'cidade'

    def lookups(self, request, model_admin):
        return (request.GET.get(self.parameter_name), ''),

    def queryset(self, request, queryset):
        if self.parameter_name in request.GET:
            return queryset.filter(cidade__iexact=request.GET.get(self.parameter_name).lower())
        return queryset

class EntidadeSemEmailAdmin(BaseEntidadeAdmin):
    list_display = ('razao_social', 'cnpj', 'estado', 'cidade', 'tem_anotacoes', 'situacao_cnpj',)
    ordering = ('estado', 'cidade', 'razao_social',)
    search_fields = ('razao_social', 'cnpj', 'email_set__endereco', 'cidade',)
    list_filter = ('estado', 'area_atuacao', FiltroPorCidade,)
    fields = ['nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website', 'facebook', 'instagram', 'twitter', 'youtube']
    readonly_fields = ['nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website', 'facebook', 'instagram', 'twitter', 'youtube']
    inlines = [
        EmailNovoEntidadeInline, TelEntidadeInline, DocumentoInline, AntigaAnotacaoEntidadeInline, NovaAnotacaoEntidadeInline,
    ]

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(EntidadeSemEmailAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Exibe apenas entidades aprovadas que não estejam sendo gerenciadas por ninguém e que não possuam e-mail
    def get_queryset(self, request):
        return self.model.objects.filter(aprovado=True, vinculoentidade__isnull=True, email_set__isnull=True).annotate(anotacoes=Count('anotacaoentidade_set'))

    def tem_anotacoes(self, instance):
        return instance.anotacoes > 0
    tem_anotacoes.boolean = True
    tem_anotacoes.short_description = u'Anotações'

class EntidadeDeFranca(Entidade):
    """Modelo criado para revisar entidades de Franca via interface adm"""
    class Meta:
        proxy = True
        verbose_name = u'Entidade de Franca/SP'
        verbose_name_plural = u'Entidades de Franca/SP'

class EntidadeDeFrancaAdmin(EntidadeSemEmailAdmin):

    # Exibe apenas entidades aprovadas da cidade de Franca
    def get_queryset(self, request):
        return self.model.objects.filter(aprovado=True, cidade__iexact="franca", estado="SP").annotate(anotacoes=Count('anotacaoentidade_set'))

class EntidadeAguardandoAprovacao(Entidade):
    """Modelo criado para gerenciar aprovação de entidades na interface adm"""
    class Meta:
        proxy = True
        verbose_name = u'Entidade aguardando aprovação'
        verbose_name_plural = u'Entidades aguardando aprovação'

class EntidadeAguardandoAprovacaoAdmin(BaseEntidadeAdmin):
    list_display = ('razao_social', 'cnpj', 'estado', 'cidade', 'data_cadastro', 'resp_bloqueio', 'data_bloqueio',)
    ordering = ('data_cadastro',)
    actions = ['unlock_selected']
    fields = ['nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website', 'facebook', 'instagram', 'twitter', 'youtube', 'aprovado']
    readonly_fields = ['area_atuacao']
    inlines = [
        EmailNovoEntidadeInline, TelEntidadeInline, ReadOnlyVinculoEntidadeInline, DocumentoInline, AnotacaoEntidadeInline,
    ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Este método é chamado nas duas situações, tanto para abrir o formulário quanto para salvar.
        # Aqui só estamos interessados no bloqueio do registro ao abrir o formulário:
        if request.method == 'GET':
            extra_context = extra_context or {}
            changelist_url = reverse('admin:vol_entidadeaguardandoaprovacao_changelist')
            # Já tenta bloquear o registro, desde que não tenha sido bloqueado ou que o bloqueio atual seja da mesma pessoa
            with transaction.atomic():
                try:
                    obj = Entidade.objects.select_for_update(nowait=True).get(Q(resp_bloqueio__isnull=True) | Q(resp_bloqueio=request.user), pk=object_id, aprovado__isnull=True)
                    obj.resp_bloqueio = request.user
                    obj.data_bloqueio = timezone.now()
                    # Atenção, esta chamada dispara o pre_save!
                    obj.save(update_fields=['resp_bloqueio', 'data_bloqueio'])
                    messages.info(request, mark_safe(u'Para buscar o cartão de CNPJ desta entidade, acesse o <a href="http://servicos.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp" target="_blank">site da receita federal</a>.'))
                except Entidade.DoesNotExist:
                    messages.error(request, u'Esta entidade não pode ser editada - verifique se a edição está bloqueada por outra pessoa ou se o cadastro já foi revisado.')
                    return redirect(changelist_url)
                except DatabaseError:
                    messages.error(request, u'Outra pessoa acabou de começar a editar esta entidade - tente trabalhar em outro cadastro.')
                    return redirect(changelist_url)
        return super().change_view(request, object_id, form_url, extra_context=extra_context,)

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(EntidadeAguardandoAprovacaoAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Ação de desbloqueio de registros
    @transaction.atomic
    def unlock_selected(self, request, queryset):
        num_unlocks = 0
        for obj in queryset:
            # Apenas o usuário que bloqueou pode desbloquear, ou então um superusuário
            if obj.resp_bloqueio is not None and (obj.resp_bloqueio == request.user or request.user.is_superuser):
                obj.resp_bloqueio = None
                obj.data_bloqueio = None
                obj.save(update_fields=['resp_bloqueio', 'data_bloqueio'])
                num_unlocks = num_unlocks + 1
        main_msg = ''
        if num_unlocks > 0:
            main_msg = u'%s entidade(s) desbloqueada(s). ' % num_unlocks
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_unlocks:
            extra_msg = u'%s entidade(s) ignorada(s), ou por não estar(em) bloqueada(s) ou por ter(em) sido bloqueada(s) por outra pessoa.' % (total_recs-num_unlocks)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    unlock_selected.short_description = "Desbloquear registros selecionados"

    # Exibe apenas entidades que já confirmaram pelo menos um e-mail e estão aguardando aprovação
    def get_queryset(self, request):
        id_entidades = Email.objects.filter(entidade__aprovado__isnull=True, confirmado=True).values_list('entidade_id')
        query = self.model.objects.filter(pk__in=id_entidades)
        if not request.user.is_superuser:
            if len(query) == 0:
                url_painel = reverse('painel')
                messages.info(request, mark_safe(u'Nenhuma entidade aguardando aprovação. Clique <a href="' + url_painel + '" target="_blank">aqui</a> se desejar retornar ao painel de controle.'))
        return query


class RevisaoEntidade(Entidade):
    """Modelo criado para avaliar as análises de cadastro de entidades via interface administrativa"""
    class Meta:
        proxy = True
        verbose_name = u'Revisão de entidade'
        verbose_name_plural = u'Revisões de entidades'

class RevisaoEntidadeAdmin(BaseEntidadeAdmin):
    list_select_related = ('resp_analise',)
    list_display = ('data_analise', 'nome_responsavel', 'razao_social', 'aprovado',)
    ordering = ('-data_analise',)
    search_fields = ('razao_social', 'nome_fantasia', )
    list_filter = ('aprovado', ('resp_analise', admin.RelatedOnlyFieldListFilter),)
    preserve_filters = True
    inlines = [
        EmailEntidadeInline, TelEntidadeInline, VinculoEntidadeInline, DocumentoInline, NecessidadeInline, AnotacaoEntidadeInline
    ]

    def get_exclude(self, request, obj=None):
        return self.exclude + ('geocode_status', 'importado',)

    # Exibe apenas cadastros em que há um responsável pela análise
    def get_queryset(self, request):
        qs = super(RevisaoEntidadeAdmin, self).get_queryset(request)
        return qs.filter(resp_analise__isnull=False)

    def nome_responsavel(self, instance):
        if instance.resp_analise:
            return instance.resp_analise.nome
        return '(vazio)'
    nome_responsavel.short_description = u'Responsável pela análise'
    nome_responsavel.admin_order_field = 'resp_analise__nome'

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(RevisaoEntidadeAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

class EntidadeComProblemaNaReceita(Entidade):
    """Modelo criado para gerenciar entidades com problema de CNPJ via interface adm"""
    class Meta:
        proxy = True
        verbose_name = u'Entidade com problema na Receita Federal'
        verbose_name_plural = u'Entidades com problema na Receita Federal'

class EntidadeComProblemaNaReceitaAdmin(EntidadeAdmin):
    list_display = ('razao_social', 'situacao_cnpj', 'data_situacao_cnpj', 'motivo_situacao_cnpj', 'situacao_especial_cnpj','tem_cartao_cnpj',)
    ordering = ('razao_social',)
    search_fields = ('razao_social', 'cnpj',)
    list_filter = ()
    readonly_fields = ['nome_fantasia', 'razao_social', 'cnpj', 'fundacao', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'pais', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website', 'facebook', 'instagram', 'twitter', 'youtube']
    actions = ['reprovar']
    inlines = [
        ReadOnlyVinculoEntidadeInline, EmailNovoEntidadeInline, TelEntidadeInline, DocumentoInline, AntigaAnotacaoEntidadeInline, NovaAnotacaoEntidadeInline,
    ]

    def get_exclude(self, request, obj=None):
        return self.exclude + ('geocode_status', 'importado', 'obs_doacoes', 'num_vol', 'num_vol_ano',)

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Exibe apenas entidades aprovadas que estejam com problema na receita
    def get_queryset(self, request):
        return self.model.objects.filter(aprovado=True, data_consulta_cnpj__isnull=False, erro_consulta_cnpj__isnull=True).exclude(situacao_cnpj='ATIVA').annotate(num_cartoes_cnpj=Count('documento', filter=Q(documento__tipodoc__codigo='cnpj')))

    def tem_cartao_cnpj(self, instance):
        return instance.num_cartoes_cnpj > 0
    tem_cartao_cnpj.boolean = True
    tem_cartao_cnpj.short_description = u'Tem cartão'

    @transaction.atomic
    def reprovar(self, request, queryset):
        num_updates = 0
        for obj in queryset:
            if obj.aprovado:
                obj.aprovado = False
                obj.save(update_fields=['aprovado'])
                num_updates = num_updates + 1
        main_msg = ''
        if num_updates > 0:
            main_msg = u'%s entidade(s) reprovada(s). ' % num_updates
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_updates:
            extra_msg = u'%s não modificada(s) por já estar(em) reprovada(s).' % (total_recs-num_updates)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    reprovar.short_description = "Reprovar entidades selecionadas"

class EmailDescoberto(Email):
    """Modelo criado para listar e-mails recém descobertos de entidades"""
    class Meta:
        proxy = True
        verbose_name = u'E-mail descoberto'
        verbose_name_plural = u'E-mails descobertos'

class EmailDescobertoAdmin(admin.ModelAdmin):
    list_display = ('razao_social_entidade', 'endereco', 'responsavel_cadastro', 'data_cadastro', 'confirmado',)
    ordering = ('-data_cadastro',)
    search_fields = ('entidade__razao_social',)
    list_display_links = None

    def razao_social_entidade(self, instance):
        return instance.entidade.razao_social
    razao_social_entidade.short_description = u'Entidade'
    razao_social_entidade.admin_order_field = 'entidade__razao_social'

    def responsavel_cadastro(self, instance):
        return instance.resp_cadastro.nome
    responsavel_cadastro.short_description = u'Responsável'
    responsavel_cadastro.admin_order_field = 'resp_cadastro__nome'

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(EmailDescobertoAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Exibe apenas e-mail de entidades sem nenhum vínculo e que estejam aguardando confirmação
    def get_queryset(self, request):
        return self.model.objects.prefetch_related('entidade', 'resp_cadastro').filter(resp_cadastro__isnull=False, entidade__aprovado=True, entidade__vinculoentidade__isnull=True)

class TipoDocumentoAdmin(admin.ModelAdmin):
    pass

class FraseMotivacionalAdmin(admin.ModelAdmin):
    list_display = ('frase', 'autor', 'utilizacao',)
    actions = ['utilizar_frase']

    @transaction.atomic
    def utilizar_frase(self, request, queryset):
        num_updates = 0
        for obj in queryset:
            obj.utilizar_frase()
            num_updates = 1
            break
        main_msg = ''
        if num_updates > 0:
            main_msg = u'%s frase agendada para utilização hoje. ' % num_updates
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_updates:
            extra_msg = u'%s não agendada(s) pois apenas uma deve ser selecionada.' % (total_recs-num_updates)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    utilizar_frase.short_description = "Utilizar frase hoje"

class ForcaTarefaAdmin(admin.ModelAdmin):
    list_display = ('tarefa', 'data_cadastro', 'meta',)
    readonly_fields = ['meta']

class AnotacaoAguardandoRevisao(AnotacaoEntidade):
    """Modelo criado para exibir anotações aguardando revisão"""
    class Meta:
        proxy = True
        verbose_name = u'Anotação sobre entidade'
        verbose_name_plural = u'Anotações sobre entidades'

class AnotacaoAguardandoRevisaoAdmin(admin.ModelAdmin):
    list_select_related = ('entidade', 'usuario',)
    list_display = ('momento', 'razao_social', 'anotacao', 'nome_responsavel',)
    list_display_links = None
    ordering = ('momento',)
    search_fields = ('entidade__razao_social', 'entidade__nome_fantasia', 'anotacao',)
    list_filter = ('entidade__aprovado',)
    preserve_filters = True
    fields = ['momento', 'razao_social', 'anotacao', 'nome_responsavel']
    readonly_fields = ['momento', 'razao_social', 'anotacao', 'nome_responsavel']
    actions = ['marcar_como_revisada']

    def razao_social(self, instance):
        return format_html('<a href="../entidade/' + str(instance.entidade.id) + '/change/"><img src="' + static('images/misc/inst.svg') + '" alt="True" title="editar entidade" style="margin-right:5px;width:13px;height:13px;"></a>' + instance.entidade.razao_social)
    razao_social.short_description = u'Razão social'
    razao_social.admin_order_field = 'entidade__razao_social'

    def nome_responsavel(self, instance):
        if instance.usuario:
            return  instance.usuario.nome
        return u'Robô'
    nome_responsavel.short_description = u'Responsável'
    nome_responsavel.admin_order_field = 'usuario__nome'

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(AnotacaoAguardandoRevisaoAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Exibe apenas anotações aguardando revisão
    def get_queryset(self, request):
        return self.model.objects.filter(req_acao=True, rev__isnull=True)

    @transaction.atomic
    def marcar_como_revisada(self, request, queryset):
        num_updates = 0
        for obj in queryset:
            if not obj.rev:
                obj.rev = True
                obj.resp_rev = request.user
                obj.data_rev = timezone.now()
                obj.save(update_fields=['rev', 'resp_rev', 'data_rev'])
                num_updates = num_updates + 1
        main_msg = ''
        if num_updates > 0:
            main_msg = u'%s anotação(ões) revisada(s). ' % num_updates
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_updates:
            extra_msg = u'%s não alterada(s) por já estar(em) revisada(s).' % (total_recs-num_updates)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    marcar_como_revisada.short_description = "Marcar anotações como revisadas"

class ConteudoAdmin(admin.ModelAdmin):
    pass

class AcessoAConteudoAdmin(admin.ModelAdmin):
    list_display = ('conteudo', 'usuario', 'momento',)
    ordering = ('-momento',)
    list_display_links = None

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(AcessoAConteudoAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

class TipoArtigoAdmin(admin.ModelAdmin):
    pass

class PostagemBlogAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'slug', 'status', 'data_criacao')
    list_filter = ("status",)
    search_fields = ['titulo', 'texto']
    readonly_fields = ['data_criacao', 'resp_criacao', 'data_atualizacao', 'resp_atualizacao', 'data_publicacao', 'resp_publicacao']
    prepopulated_fields = {'slug': ('titulo',)}

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'texto':
            return db_field.formfield(widget=TinyMCE(
                attrs={'cols': 100, 'rows': 20},
                mce_attrs={'external_link_list_url': reverse('tinymce-linklist')},
                ))
        return super(PostagemBlogAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    # Gravações automáticas na Postagem
    def save_model(self, request, obj, form, change):
        # Postagem já existente
        if obj.id:
            # Situação atual no banco
            antes = PostagemBlog.objects.get(pk=obj.id)
            if antes.status == 0: # Era rascunho
                if antes.data_publicacao is None: # sem data de publicação
                    # e acaba de ser publicado
                    if obj.status == 1:
                        obj.resp_publicacao = request.user
                        obj.data_publicacao = timezone.now()
            elif antes.status == 1: # já estava publicado
                # Continua publicado e houve alteração no texto
                # obs: não cobre a situação de voltar para rascunho,
                # alterar e republicar. Talvez seja o caso de não
                # permitir a volta para rascunho (?)
                if obj.status == 1 and antes.texto != obj.texto:
                    obj.resp_atualizacao = request.user
                    obj.data_atualizacao = timezone.now()
        else:
            # Postagem nova
            obj.resp_criacao = request.user
            
        super().save_model(request, obj, form, change)

@admin.register(Funcao)
class FuncaoAdmin(DraggableMPTTAdmin):
    '''Interface administrativa para funções'''
    list_display = ('tree_actions', 'indented_title', 'qtde_pessoas', 'responsaveis',)
    raw_id_fields = ('entidade',)

admin.site.register(Usuario, MyUserAdmin)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, MyFlatPageAdmin)
admin.site.register(AreaTrabalho, AreaTrabalhoAdmin)
admin.site.register(AreaAtuacao, AreaAtuacaoAdmin)
admin.site.register(Voluntario, VoluntarioAdmin)
admin.site.register(RevisaoVoluntario, RevisaoVoluntarioAdmin)
admin.site.register(Entidade, EntidadeAdmin)
admin.site.register(EntidadeSemEmail, EntidadeSemEmailAdmin)
admin.site.register(EntidadeDeFranca, EntidadeDeFrancaAdmin)
admin.site.register(EntidadeAguardandoAprovacao, EntidadeAguardandoAprovacaoAdmin)
admin.site.register(EntidadeComProblemaNaReceita, EntidadeComProblemaNaReceitaAdmin)
admin.site.register(RevisaoEntidade, RevisaoEntidadeAdmin)
admin.site.register(TipoDocumento, TipoDocumentoAdmin)
admin.site.register(FraseMotivacional, FraseMotivacionalAdmin)
admin.site.register(ForcaTarefa, ForcaTarefaAdmin)
admin.site.register(AnotacaoAguardandoRevisao, AnotacaoAguardandoRevisaoAdmin)
admin.site.register(EmailDescoberto, EmailDescobertoAdmin)
admin.site.register(Conteudo, ConteudoAdmin)
admin.site.register(AcessoAConteudo, AcessoAConteudoAdmin)
admin.site.register(TipoArtigo, TipoArtigoAdmin)
admin.site.register(PostagemBlog, PostagemBlogAdmin)
