# coding=UTF-8

from django.test import TestCase

class ModulesTest(TestCase):

    def test_tinymce(self):
        try:
            import tinymce
        except Exception as e:
            self.fail(u"Could not import tinymce Python module")

    def test_openid(self):
        try:
            import openid
        except Exception as e:
            self.fail(u"Could not import python3-openid Python module")

    def test_requests(self):
        try:
            import requests
        except Exception as e:
            self.fail(u"Could not import requests Python module")

    def test_requests_oauth(self):
        try:
            import requests_oauthlib
        except Exception as e:
            self.fail(u"Could not import requests_oauthlib Python module")
