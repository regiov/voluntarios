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

        Se a conta social tem um email que já existe no nosso banco e que já foi verificado,
        então linka a conta com o usuário, seja em login normal, seja em cadastro.
        """

        # if social login is already registered, no need to do anything
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

    def get_signup_form_initial_data(self, sociallogin):
        """
        Preenche automaticamente o máximo de campos no formulário de cadastro.
        """
        email = ''
        if sociallogin.email_addresses:
            for email_address in sociallogin.email_addresses:
                # Pega o primeiro email
                email = email_address
                break

        extra_data = sociallogin.account.extra_data

        nome = ''
        if sociallogin.account.provider == 'facebook':
            if 'name' in extra_data:
                nome = extra_data['name']
        elif sociallogin.account.provider == 'linkedin_oauth2':
            if 'firstName' in extra_data and 'lastName' in extra_data and 'localized' in extra_data['firstName'] and 'localized' in extra_data['lastName'] and 'pt_BR' in extra_data['firstName']['localized'] and 'pt_BR' in extra_data['lastName']['localized']:
                first_name = extra_data['firstName']['localized']['pt_BR']
                last_name = extra_data['lastName']['localized']['pt_BR']
                nome = f'{first_name} {last_name}'
            
        return {'email': email, 'nome': nome}


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

