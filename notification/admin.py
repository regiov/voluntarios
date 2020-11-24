from django.contrib import admin

from notification.models import Message, Event

class MessageAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    readonly_fields = ['code']

    def has_add_permission(self, request):
        # Não permite inclusão
        return False

    def has_delete_permission(self, request, obj=None):
        # Não permite remoção
        return False

    # Remove opção de deleção nas ações
    def get_actions(self, request):
        actions = super(MessageAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

class EventAdmin(admin.ModelAdmin):
    list_display = ('message_code', 'creation', 'content_object', 'nobounce')
    fields = ('rtype', 'message', 'user', 'subject', 'content', 'creation', 'repeat', 'last_rep', 'content_type', 'object_id', 'content_object', 'bounce',)
    readonly_fields = ('rtype', 'message', 'user', 'subject', 'content', 'creation', 'repeat', 'last_rep', 'content_type', 'object_id', 'content_object',)
    list_filter = ('message__code',)

    def has_add_permission(self, request):
        # Não permite inclusão
        return False

    def has_delete_permission(self, request, obj=None):
        # Não permite remoção
        return False

    # Remove opção de deleção nas ações
    def get_actions(self, request):
        actions = super(EventAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def message_code(self, instance):
        if instance.message:
            return instance.message.code
        return '-'
    message_code.short_description = u'Message code'
    message_code.admin_order_field = 'message__code'

    def nobounce(self, instance):
        return instance.bounce is None
    nobounce.boolean = True
    nobounce.short_description = u'No bounce'

admin.site.register(Message, MessageAdmin)
admin.site.register(Event, EventAdmin)

