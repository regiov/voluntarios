# coding: utf-8

# Arquivo contendo mensagens do Django ou outros apps externos para fins de sobreposição da tradução.
# 
# Abordagem descrita em: http://stackoverflow.com/questions/7878028/override-default-django-translations

from django.utils.translation import ungettext

_ = lambda s: s
django_standard_messages_to_override = [
    _("E-mail address"),
    _("Remember Me"),
    #ungettext("Please submit %d or more forms.","Please submit %d or more forms.", 1) % 1,
]
