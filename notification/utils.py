# coding=UTF-8

"""
Notification functions.
"""

try:
    from django.utils.timezone import now as datetime_now
except ImportError:
    import datetime
    datetime_now = datetime.datetime.now

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.template import engines

from notification.models import Event

def notify_support(subject, msg, request=None, repeat_after=None):
    """
    Generic funtion to send e-mail to support.
    repeat_after may specify the number of MINUTES before the same type of event should be sent by email again.
    """
    if not settings.SUPPORT_NOTIFICATION_ENABLED:
        return
    env = ''
    if request is not None and request.user.is_authenticated:
        env = 'user: ' + request.user.get_full_name() + "\n\n"
    new_record = True
    last_event = None
    delta_minutes = None
    if repeat_after is not None:
        last_event = Event.objects.filter(subject=subject).order_by('-creation').first()
        if last_event is not None:
            now = datetime_now()
            delta = now - last_event.creation
            delta_minutes = delta.total_seconds()/60.0
            if delta_minutes < repeat_after:
                last_event.repeat = last_event.repeat + 1
                last_event.last_rep = now
                last_event.save(update_fields=['repeat', 'last_rep'])
                new_record = False
    if new_record:
        event = Event(rtype='S', subject=subject, content=env + msg)
        event.save()
        try:
            send_mail(settings.SUBJECT_PREFIX + subject,
                      env + msg,
                      settings.NOTIFY_SUPPORT_FROM,
                      [settings.NOTIFY_SUPPORT_TO],
                      fail_silently=True)
        except Exception as e:
            # TODO?
            pass

def notify_user_msg(user, message, context={}, from_email=settings.NOTIFY_USER_FROM):
    """
    Generic funtion to send e-mail to users based on a message object.
    """
    subject = message.subject
    content = message.content
    if len(context) > 0:
        if 'django' not in engines:
            msg = u"error: django engine unavailable!\n\nsubject: %s\n\nto: %s\n\nmessage:\n\n%s" % (subject, user.email, content)
            notify_support(u'Notification failure', msg)
            return
        django_engine = engines['django']
        template = django_engine.from_string(content)
        content = template.render(context=context)
    try:
        user.email_user(subject, content, from_email)
        event = Event(rtype='U', user=user, message=message)
        event.save()
    except Exception as e:
        error = type(e).__name__ + str(e.args)
        msg = u"error: %s\n\nsubject: %s\n\nto: %s\n\nmessage:\n\n%s" % (error, subject, user.email, content)
        notify_support(u'Notification failure', msg)

def notify_user_template(user, subject_template, msg_template, from_email=settings.NOTIFY_USER_FROM, context={}):
    """
    Generic funtion to send e-mail to users based on templates for subject and message.
    """
    subject = render_to_string(subject_template, context)
    # Subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    message = render_to_string(msg_template, context)
    try:
        user.email_user(subject, message, from_email)
    except Exception as e:
        error = type(e).__name__ + str(e.args)
        msg = u"error: %s\n\nsubject: %s\n\nto: %s\n\nmessage:\n\n%s" % (error, subject, user.get_full_name(), message)
        notify_support(u'Notification failure', msg)

def notify_email(to, subject, msg_template, context={}, from_email=settings.NOTIFY_USER_FROM, **kwargs):
    """
    Generic funtion to send a message to an e-mail using a template for the message.
    """
    message = render_to_string(msg_template, context)
    try:
        send_mail(subject, message, from_email, [to], **kwargs)
    except Exception as e:
        error = type(e).__name__ + str(e.args)
        msg = u"error: %s\n\nsubject: %s\n\nto: %s\n\nmessage:\n\n%s" % (error, subject, to, message)
        notify_support(u'Notification failure', msg)
