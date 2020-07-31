from django.contrib import admin

from notification.models import Message

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

admin.site.register(Message, MessageAdmin)

