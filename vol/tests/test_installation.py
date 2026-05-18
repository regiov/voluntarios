from django.test import TestCase, Client, SimpleTestCase
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.wsgi import get_wsgi_application
from django.urls import get_resolver
from django.db import connection


class TestProjectBoot(SimpleTestCase):
    """
    Testes leves: não exigem banco
    (validam "o código sobe")
    """

    def test_django_check(self):
        """Valida system check do Django"""
        try:
            call_command("check", verbosity=0)
        except SystemCheckError as e:
            self.fail(f"Django system check failed: {e}")

    def test_wsgi_loads(self):
        """Valida carregamento WSGI"""
        try:
            application = get_wsgi_application()
            self.assertIsNotNone(application)
        except Exception as e:
            self.fail(f"WSGI failed to load: {e}")

    def test_urls_load(self):
        """Valida se URLs não quebram importação"""
        try:
            resolver = get_resolver()
            self.assertIsNotNone(resolver)
        except Exception as e:
            self.fail(f"URL resolver failed: {e}")


class TestDatabaseBoot(TestCase):
    """
    Testes com banco:
    migração + conexão + query simples
    """

    def test_migrations_apply(self):
        """Verifica se migrations rodam sem erro"""
        try:
            call_command("migrate", interactive=False, verbosity=0)
        except Exception as e:
            self.fail(f"Migrations failed: {e}")

    def test_database_connection(self):
        """Verifica conexão com banco"""
        try:
            connection.ensure_connection()
            self.assertTrue(connection.is_usable())
        except Exception as e:
            self.fail(f"Database connection failed: {e}")


class TestHTTP(TestCase):
    """
    Teste mínimo HTTP (carregamento do Django completo)
    """

    def test_root_endpoint(self):
        client = Client()
        response = client.get("/")

        # não pode quebrar servidor
        self.assertLess(
            response.status_code,
            500,
            f"Root endpoint crashed: {response.status_code}"
        )