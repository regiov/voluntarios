# coding=UTF-8

from django.apps import AppConfig

class VolConfig(AppConfig):
    name = 'vol'
    verbose_name = "Voluntariado"

    def ready(self):

        # Deve-se imortar daqui para evitar erro de Modelos ainda não carregdos no setup do Django
        from django.db.models.signals import post_save
        from allauth.account.signals import user_signed_up
        from .signals import my_user_signed_up, voluntario_post_save

        # Conexão de sinais
        user_signed_up.connect(my_user_signed_up)
        post_save.connect(voluntario_post_save, sender='vol.Voluntario')
