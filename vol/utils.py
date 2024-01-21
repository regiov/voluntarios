# coding=UTF-8

# IMPORTANTE:
#
# Como as rotinas aqui são usadas pelo models.py, não se pode importar modelos em novas rotinas pois dá erro.
#

from django.db.models.signals import post_init
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.urls import reverse

from notification.utils import notify_user_msg, notify_email_msg, notify_email
from notification.models import Message, Event

def track_data(*fields):
    """
    Source: https://gist.github.com/dcramer/730765
    
    Tracks property changes on a model instance.
    
    The changed list of properties is refreshed on model initialization
    and save.
    
    >>> @track_data('name')
    >>> class Post(models.Model):
    >>>     name = models.CharField(...)
    >>> 
    >>>     @classmethod
    >>>     def post_save(cls, sender, instance, created, **kwargs):
    >>>         if instance.has_changed('name'):
    >>>             print("Hooray!")
    """
    
    UNSAVED = dict()

    def _store(self):
        "Updates a local copy of attributes values"
        if self.id:
            self.__data = dict((f, getattr(self, f)) for f in fields)
        else:
            self.__data = UNSAVED

    def inner(cls):
        # contains a local copy of the previous values of attributes
        cls.__data = {}

        def has_changed(self, field):
            "Returns ``True`` if ``field`` has changed since initialization."
            if self.__data is UNSAVED:
                return False
            return self.__data.get(field) != getattr(self, field)
        cls.has_changed = has_changed

        def old_value(self, field):
            "Returns the previous value of ``field``"
            return self.__data.get(field)
        cls.old_value = old_value

        def whats_changed(self):
            "Returns a list of changed attributes."
            changed = {}
            if self.__data is UNSAVED:
                return changed
            for k, v in iter(self.__data.items()):
                if v != getattr(self, k):
                    changed[k] = v
            return changed
        cls.whats_changed = whats_changed

        # Ensure we are updating local attributes on model init
        def _post_init(sender, instance, **kwargs):
            _store(instance)
        post_init.connect(_post_init, sender=cls, weak=False)

        # Ensure we are updating local attributes on model save
        def save(self, *args, **kwargs):
            save._original(self, *args, **kwargs)
            _store(self)
        save._original = cls.save
        cls.save = save
        return cls
    return inner

def notifica_aprovacao_voluntario(usuario):
    '''Envia e-mail comunicando ao usuário a aprovação do seu perfil'''
    # Se o usuário nunca recebeu o aviso de aprovação
    msg = Message.objects.get(code='AVISO_APROVACAO_VOLUNTARIO_V5')
    if Event.objects.filter(user=usuario, message=msg).count() == 0:
        # Envia notificação
        notify_user_msg(usuario, msg, context={'usuario': usuario})

def notifica_aprovacao_entidade(entidade):
    '''Envia e-mail comunicando à entidade a aprovação do seu cadastro'''
    # Se a entidade nunca recebeu o aviso de aprovação
    msg = Message.objects.get(code='AVISO_APROVACAO_ENTIDADE')
    if Event.objects.filter(object_id=entidade.id, content_type=ContentType.objects.get_for_model(entidade).id, message=msg).count() == 0:
        # Envia notificação para a entidade
        notify_email_msg(entidade.email_principal, msg, content_obj=entidade)
        # Envia notificação para responsáveis pelo onboarding
        if hasattr(settings, 'ONBOARDING_TEAM_EMAIL'):
             notify_email(settings.ONBOARDING_TEAM_EMAIL, '\o/ Nova entidade aprovada!', 'Ei! O cadastro da entidade ' + entidade.menor_nome() + ' acaba de ser aprovado no Voluntários. Você está recebendo esse e-mail porque faz parte da equipe de boas-vindas. Use esse link para recepcionar a entidade: https://voluntarios.com.br' + reverse('onboarding_entidades'))
