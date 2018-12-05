# coding=UTF-8

from django.contrib import admin
from django.contrib.gis.admin import GeoModelAdmin
from django.db import transaction
from django.utils.translation import gettext, gettext_lazy as _
from django.db.models import Count, Q

# Usuário customizado
from django.contrib.auth.admin import UserAdmin

# Como usar TinyMCE para editar flatpages:
# source: https://stackoverflow.com/questions/15123927/embedding-tinymce-in-django-flatpage
from django.contrib.flatpages.admin import FlatpageForm, FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from tinymce.widgets import TinyMCE

from vol.models import Usuario, AreaTrabalho, AreaAtuacao, Voluntario, Entidade, Necessidade, AreaInteresse

from vol.views import envia_confirmacao_entidade

from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.account.adapter import get_adapter

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
        account_adapter = get_adapter(request)
        for obj in queryset:
            for emailconfirmation in EmailConfirmation.objects.filter(email_address__user_id=obj.id, email_address__verified=False):
                account_adapter.send_confirmation_mail(request, emailconfirmation, False)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s usuário(s) notificado(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s usuário(s) não notificado(s) por já possuir(em) cadastro confirmado.' % (total_recs-num_messages)
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

class NecessidadeInline(admin.TabularInline):
    model = Necessidade
    fields = ['qtde_orig', 'descricao', 'valor_orig', 'data_solicitacao',]
    readonly_fields = ['data_solicitacao']
    extra = 0

class EntidadeAdmin(GeoModelAdmin):
    list_display = ('razao_social', 'cnpj', 'email', 'data_cadastro', 'importado', 'confirmado', 'aprovado',)
    ordering = ('-aprovado', '-data_cadastro',)
    search_fields = ('razao_social', 'cnpj', 'email',)
    list_filter = ('aprovado', 'confirmado', 'importado',)
    preserve_filters = True
    exclude = ('coordenadas',)
    readonly_fields = ('geocode_status', 'importado', 'confirmado',)
    actions = ['aprovar', 'enviar_confirmacao']
    inlines = [
        NecessidadeInline,
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
                envia_confirmacao_entidade(obj.razao_social, obj.email)
                num_messages = num_messages + 1
        main_msg = ''
        if num_messages > 0:
            main_msg = u'%s entidade(s) notificada(s). ' % num_messages
        extra_msg = ''
        total_recs = len(queryset)
        if total_recs > num_messages:
            extra_msg = u'%s não notificada(s) por já possuir(em) cadastro confirmado.' % (total_recs-num_messages)
        self.message_user(request, "%s%s" % (main_msg, extra_msg))
    enviar_confirmacao.short_description = "Enviar nova mensagem de confirmação"

admin.site.register(Usuario, MyUserAdmin)
admin.site.unregister(FlatPage)
admin.site.register(FlatPage, MyFlatPageAdmin)
admin.site.register(AreaTrabalho, AreaTrabalhoAdmin)
admin.site.register(AreaAtuacao, AreaAtuacaoAdmin)
admin.site.register(Voluntario, VoluntarioAdmin)
admin.site.register(Entidade, EntidadeAdmin)

