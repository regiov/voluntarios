from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Message(models.Model):
    '''
    Message template.
    '''
    id          = models.AutoField(primary_key=True)
    code        = models.CharField(u'Code', max_length=50)
    description = models.TextField(u'Description')
    subject     = models.CharField(u'Subject', max_length=200, null=True, blank=True)
    content     = models.TextField(u'Message content', null=True, blank=True)

    def __str__(self):
        if self.code:
            return self.code
        return self.subject

class Event(models.Model):
    '''
    Notification event.
    '''
    id       = models.AutoField(primary_key=True)
    rtype    = models.CharField(u'Recipient type (S=support, U=user, E=generic)', max_length=1)
    message  = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE)
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    email    = models.CharField(u'E-mail', max_length=90, null=True, blank=True)
    subject  = models.CharField(u'Message subject', null=True, blank=True, max_length=200)
    content  = models.TextField(u'Message content', null=True, blank=True)
    repeat   = models.IntegerField(u'Repetitions', default=0)
    creation = models.DateTimeField(u'Creation timestamp', auto_now_add=True)
    last_rep = models.DateTimeField(u'Last repetition', null=True, blank=True)
    # Generic relation, allowing events to be related to any external model
    content_type   = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id      = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    bounce  = models.TextField(u'Bounce message content', null=True, blank=True)

