# coding=UTF-8

from django.apps import AppConfig

class VolConfig(AppConfig):
    name = 'vol'
    verbose_name = "Voluntariado"

    def ready(self):

        # Deve-se imortar daqui para evitar erro de Modelos ainda não carregdos no setup do Django
        from django.db.models.signals import pre_save, post_save
        from allauth.account.signals import user_signed_up
        from .signals import my_user_signed_up, voluntario_post_save, entidade_pre_save, entidade_post_save

        # Conexão de sinais
        user_signed_up.connect(my_user_signed_up)
        post_save.connect(voluntario_post_save, sender='vol.Voluntario')
        pre_save.connect(entidade_pre_save, sender='vol.Entidade')
        pre_save.connect(entidade_pre_save, sender='vol.EntidadeAguardandoAprovacao')
        post_save.connect(entidade_post_save, sender='vol.Entidade')
        post_save.connect(entidade_post_save, sender='vol.EntidadeAguardandoAprovacao')
