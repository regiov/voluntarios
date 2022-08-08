# coding=UTF-8

from django import forms

from allauth.account.adapter import DefaultAccountAdapter, get_adapter
from allauth.utils import email_address_exists
from allauth.account.forms import SignupForm
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).

        Tenta os seguintes passos antes de logar :
        - A conta social existe, só continua.
        - A conta social não tem email ou email desconhecido, só cotinua.
        - Já existe um email igual ao da conta social:
            - Confere se o email já foi verificado, e nesse caso linka a conta social à conta existente no sistema.
        """

        # social account already exists, so this is just a login
        if sociallogin.is_existing:
            return

        # some social logins don't have an email address
        if not sociallogin.email_addresses:
            return

        # find the first verified email that we get from this sociallogin
        for email in sociallogin.email_addresses:
            try:
                existing_email = EmailAddress.objects.get(email__iexact=email.email, verified=True)
                # connect this new social login to the existing user
                sociallogin.connect(request, existing_email.user)
                return
            except EmailAddress.DoesNotExist:
                continue

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

