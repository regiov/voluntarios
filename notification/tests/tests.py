# coding=UTF-8

from django.test import TestCase

class SettingsTest(TestCase):
    def test_notification_settings(self):
        """
        Ensures that notification settings are defined.
        """
        from django.conf import settings
        self.assertIsNotNone(settings.SUBJECT_PREFIX)
        self.assertIsNotNone(settings.NOTIFY_SUPPORT_FROM)
        self.assertIsNotNone(settings.NOTIFY_SUPPORT_TO)
        self.assertIsNotNone(settings.NOTIFY_USER_FROM)

class NotificationTest(TestCase):
    def test_support_notification(self):
        """
        Ensures that support notification is working.
        """
        from django.conf import settings
        from notification.utils import notify_support
        subject = 'Support notification test'
        notify_support(subject, 'Test message')
        print('A test message with subject "' + subject + '" was in theory sent to ' + settings.NOTIFY_SUPPORT_TO + '. Check the mail box.')

