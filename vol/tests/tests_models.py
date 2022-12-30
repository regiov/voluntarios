# coding=UTF-8

from django.test import TestCase

from ..models import Usuario, Voluntario

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
    
    def test_retorno_is_voluntario(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')

        voluntario = Voluntario.objects.create(
            usuario               = usuario_teste,
            data_aniversario      = '1999-05-27',
            profissao             = 'Developer',
            ddd                   = '21',
            telefone              = '994383837',
            estado                = 'RJ',
            cidade                = 'Rio de Janeiro'
        )
        self.assertTrue(usuario_teste.is_voluntario)