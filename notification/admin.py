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

admin.site.register(Message, MessageAdmin)

