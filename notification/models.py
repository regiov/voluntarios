from django.db import models

class Event(models.Model):
    '''
    Notification event.
    '''
    rtype    = models.CharField(u'Recipient type (S=support)', max_length=1)
    subject  = models.CharField(u'Subject', max_length=200)
    msg      = models.TextField(u'Message')
    repeat   = models.IntegerField(u'Repetitions', default=0)
    creation = models.DateTimeField(u'Creation timestamp', auto_now_add=True)
    last_rep = models.DateTimeField(u'Last repetition', null=True, blank=True)

