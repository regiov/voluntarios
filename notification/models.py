from django.db import models
from django.conf import settings

class Message(models.Model):
    '''
    Message template.
    '''
    code        = models.CharField(u'Code', max_length=50)
    description = models.TextField(u'Description')
    subject     = models.CharField(u'Subject', max_length=200, null=True, blank=True)
    content     = models.TextField(u'Message content', null=True, blank=True)

class Event(models.Model):
    '''
    Notification event.
    '''
    rtype    = models.CharField(u'Recipient type (S=support, U=user)', max_length=1)
    message  = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE)
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    subject  = models.CharField(u'Message subject', null=True, blank=True, max_length=200)
    content  = models.TextField(u'Message content', null=True, blank=True)
    repeat   = models.IntegerField(u'Repetitions', default=0)
    creation = models.DateTimeField(u'Creation timestamp', auto_now_add=True)
    last_rep = models.DateTimeField(u'Last repetition', null=True, blank=True)

