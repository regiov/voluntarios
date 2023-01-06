# coding=UTF-8

from django.test import TestCase

from ..models import Usuario

class UsuarioTestCase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(
        email= 'voluntarioteste@gmail.com',
        nome= 'Voluntario Teste'
        )

    def test_retorno_str(self):
        usuario_teste = Usuario.objects.get(email='voluntarioteste@gmail.com')
        self.assertEqual(usuario_teste.__str__(), 'voluntarioteste@gmail.com')
    
    def test_retorno_get_full_name(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')
        self.assertEqual(usuario_teste.get_full_name(), 'Voluntario Teste')
    
    def test_retorno_get_short_name(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')
        self.assertEqual(usuario_teste.get_short_name(), 'Voluntario')