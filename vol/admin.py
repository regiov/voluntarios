# coding=UTF-8

from django.contrib import admin
from django.contrib.gis.admin import GeoModelAdmin
from django.db import transaction
from django.utils.translation import gettext, gettext_lazy as _
from django.utils import timezone
from django.db.models import Count, Q, TextField
from django.forms import Textarea
from datetime import datetime

# Usuário customizado
from django.contrib.auth.admin import UserAdmin

# Como usar TinyMCE para editar flatpages:
# source: https://stackoverflow.com/questions/15123927/embedding-tinymce-in-django-flatpage
from django.contrib.flatpages.admin import FlatpageForm, FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from tinymce.widgets import TinyMCE

from vol.models import Usuario, AreaTrabalho, AreaAtuacao, Voluntario, Entidade, VinculoEntidade, Necessidade, AreaInteresse, AnotacaoEntidade, TipoDocumento, Documento, Telefone, Email

from vol.views import envia_confirmacao_email_entidade

from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation

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
    actions = ['reenviar_confirmacao']

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

class MyFlatPageForm(FlatpageForm):

    class Meta:
        model = FlatPage
        fields = FlatpageForm.Meta.fields
        widgets = {
            'content' : TinyMCE(attrs={'cols': 100, 'rows': 15}),
        }


class MyFlatPageAdmin(FlatPageAdmin):
    form = MyFlatPageForm

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
    readonly_fields = ('usuario', 'data_aniversario_orig', 'site', 'importado',)
    actions = ['aprovar']
    inlines = [
        AreaInteresseInline,
    ]
    fields = ('usuario', 'data_aniversario_orig', 'data_aniversario', 'profissao', 'ddd', 'telefone', 'cidade', 'estado', 'empresa', 'foi_voluntario', 'entidade_que_ajudou', 'area_trabalho', 'descricao', 'newsletter', 'fonte', 'site', 'importado', 'aprovado',)

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
            return instance.usuario.email
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


class AnaliseVoluntario(Voluntario):
    """Modelo criado para avaliar as análises de cadastro de voluntários via interface administrativa"""
    class Meta:
        proxy = True
        verbose_name = u'Análise de voluntário'
        verbose_name_plural = u'Análises de voluntários'

class AnaliseVoluntarioAdmin(admin.ModelAdmin):
    list_select_related = ('usuario', 'resp_analise',)
    list_display = ('nome_voluntario', 'data_cadastro', 'nome_responsavel', 'data_analise', 'aprovado',)
    ordering = ('-data_analise',)
    search_fields = ('usuario__nome', 'usuario__email', )
    list_filter = ('aprovado', ('resp_analise', admin.RelatedOnlyFieldListFilter),)
    preserve_filters = True
    readonly_fields = ('usuario', 'resp_analise', 'data_analise', 'aprovado', 'dif_analise',)
    fields = ('usuario', 'resp_analise', 'data_analise', 'aprovado', 'dif_analise',)

    # Exibe apenas cadastros em que há um responsável pela análise
    def get_queryset(self, request):
        qs = super(AnaliseVoluntarioAdmin, self).get_queryset(request)
        return qs.filter(resp_analise__isnull=False)

    def nome_voluntario(self, instance):
        if instance.usuario:
            return instance.usuario.nome
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
        actions = super(AnaliseVoluntarioAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

class EmailEntidadeInline(admin.TabularInline):
    model = Email
    fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao']
    extra = 0

class ReadOnlyEmailEntidadeInline(admin.TabularInline):
    model = Email
    fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao']
    readonly_fields = ['endereco', 'principal', 'confirmado', 'data_confirmacao']
    extra = 0

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class TelEntidadeInline(admin.TabularInline):
    model = Telefone
    fields = ['tipo', 'prefixo', 'numero', 'contato', 'confirmado', 'data_confirmacao', 'confirmado_por']
    readonly_fields = ['data_confirmacao', 'confirmado_por']
    extra = 0

class ReadOnlyTelEntidadeInline(admin.TabularInline):
    model = Telefone
    fields = ['tipo', 'prefixo', 'numero', 'contato', 'confirmado', 'data_confirmacao', 'confirmado_por']
    readonly_fields = ['tipo', 'prefixo', 'numero', 'contato', 'data_confirmacao', 'confirmado_por']
    extra = 0

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class VinculoEntidadeInline(admin.TabularInline):
    model = VinculoEntidade
    fields = ['usuario', 'data_inicio', 'data_fim', 'confirmado']
    raw_id_fields = ('usuario',)
    readonly_fields = ['data_inicio']
    extra = 0

class NecessidadeInline(admin.TabularInline):
    model = Necessidade
    fields = ['qtde_orig', 'descricao', 'valor_orig', 'data_solicitacao',]
    readonly_fields = ['data_solicitacao']
    extra = 0

class DocumentoInline(admin.TabularInline):
    model = Documento
    fields = ['tipodoc', 'doc', 'data_cadastro', 'usuario']
    readonly_fields = ['data_cadastro', 'usuario']
    extra = 0

class AnotacaoEntidadeInline(admin.TabularInline):
    model = AnotacaoEntidade
    fields = ['anotacao', 'req_acao', 'usuario', 'momento']
    readonly_fields = ['usuario', 'momento']
    extra = 0
    formfield_overrides = {
        TextField: {'widget': Textarea(attrs={'rows':2, 'cols':75})},
    } 

class BaseEntidadeAdmin(admin.ModelAdmin):
    # Grava alterações automáticas
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if isinstance(instance, AnotacaoEntidade) or isinstance(instance, Documento):
                if instance.usuario_id is None:
                    # Grava usuário corrente em anotações e documentos
                    instance.usuario = request.user
            if isinstance(instance, Telefone):
                # Atualiza status de confirmação de telefone
                if instance.confirmado:
                    if instance.confirmado_por is None:
                        instance.confirmado_por = request.user
                    if instance.data_confirmacao is None:
                        instance.data_confirmacao = timezone.now()
                else:
                    if instance.confirmado_por is not None:
                        instance.confirmado_por = None
                    instance.data_confirmacao = None
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
    search_fields = ('razao_social', 'cnpj', 'email_set__endereco',)
    list_filter = ('aprovado', 'importado',)
    preserve_filters = True
    exclude = ('coordenadas', 'despesas', 'beneficiados', 'voluntarios', 'reg_cnas', 'auditores', 'banco', 'agencia', 'conta', 'qtde_visualiza', 'ultima_visualiza', 'mytags',)
    readonly_fields = ('geocode_status', 'importado',)
    actions = ['aprovar', 'enviar_confirmacao']
    inlines = [
        EmailEntidadeInline, TelEntidadeInline, VinculoEntidadeInline, DocumentoInline, NecessidadeInline, AnotacaoEntidadeInline
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
            if not obj.confirmado:
                envia_confirmacao_email_entidade(request, obj)
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

class ValidacaoEntidade(Entidade):
    """Modelo criado para realizar validação do cadastro de entidades via interface administrativa"""
    class Meta:
        proxy = True
        verbose_name = u'Entidade para revisão'
        verbose_name_plural = u'Entidades para revisão'

class ValidacaoEntidadeAdmin(BaseEntidadeAdmin):
    list_display = ('razao_social', 'cnpj', 'email_principal', 'data_cadastro', 'cidade', 'estado', 'ultima_revisao',)
    ordering = ('-data_cadastro', '-ultima_revisao',)
    search_fields = ('razao_social', 'cnpj', 'email_set__endereco', 'cidade',)
    fields = ['nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website', 'ultima_revisao', 'mytags']
    readonly_fields = ['nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'logradouro', 'bairro', 'cidade', 'estado', 'cep', 'nome_resp', 'sobrenome_resp', 'cargo_resp', 'nome_contato', 'website']
    inlines = [
        ReadOnlyEmailEntidadeInline, ReadOnlyTelEntidadeInline, DocumentoInline, AnotacaoEntidadeInline,
    ]

    # Desabilita inclusão
    def has_add_permission(self, request):
        return False

    # Desabilita remoção
    def has_delete_permission(self, request, obj=None):
        return False

    # Remove opção de deleção das ações
    def get_actions(self, request):
        actions = super(ValidacaoEntidadeAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Exibe apenas entidades aprovadas
    def get_queryset(self, request):
        return self.model.objects.filter(aprovado=True)

class TipoDocumentoAdmin(admin.ModelAdmin):
    pass

admin.site.register(Usuario, MyUserAdmin)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, MyFlatPageAdmin)
admin.site.register(AreaTrabalho, AreaTrabalhoAdmin)
admin.site.register(AreaAtuacao, AreaAtuacaoAdmin)
admin.site.register(Voluntario, VoluntarioAdmin)
admin.site.register(AnaliseVoluntario, AnaliseVoluntarioAdmin)
admin.site.register(Entidade, EntidadeAdmin)
admin.site.register(ValidacaoEntidade, ValidacaoEntidadeAdmin)
admin.site.register(TipoDocumento, TipoDocumentoAdmin)

