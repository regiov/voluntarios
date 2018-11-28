# coding=UTF-8

from allauth.account.adapter import DefaultAccountAdapter
from allauth.utils import email_address_exists
from django import forms

from allauth.account.forms import SignupForm
from allauth.account.adapter import get_adapter

class MyAccountAdapter(DefaultAccountAdapter):
    "Adaptador customizado para excluir usuário atual da verificação de unicidade de e-mail"
    def validate_unique_email(self, email):
        user = None
        if self.request and self.request.user:
            user = self.request.user
        if email_address_exists(email, exclude_user=user):
            raise forms.ValidationError(self.error_messages['email_taken'])
        return email

class ChangeUserProfileForm(SignupForm):
    "Formulário para edição de campos do usuário, sempre recebendo request como parâmetro"
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super(ChangeUserProfileForm, self).__init__(**kwargs)

    def validate_unique_email(self, value):
        return get_adapter(self.request).validate_unique_email(value)

