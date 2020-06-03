# coding=UTF-8

from django.apps import AppConfig

from allauth.account.signals import user_signed_up

from vol.signals import my_user_signed_up

class VolConfig(AppConfig):
    name = 'vol'
    verbose_name = "Voluntariado"

    def ready(self):
        # importing model classes
        #from .models import MyModel  # or...
        #MyModel = self.get_model('MyModel')

        # registering signals with the model's string label
        #pre_save.connect(receiver, sender='app_label.MyModel')
        #user_signed_up.connect(request, user)
        user_signed_up.connect(my_user_signed_up)

