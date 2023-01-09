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

class VoluntarioTestCase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(
            email= 'voluntarios@gmail.com',
            nome= 'Voluntario Teste'
        )

        voluntario = Voluntario.objects.create(
            usuario= usuario,
            data_aniversario= datetime.datetime(2000,12,12)
        )


    def test_iniciais(self):
        voluntario_teste = Usuario.objects.get(nome='Voluntario Teste')
        self.assertEqual(voluntario_teste.voluntario.iniciais(), 'V.T.')

    def test_idade(self):
        voluntario_teste = Voluntario.objects.get(data_aniversario= datetime.datetime(2000,12,12))
        self.assertEqual(voluntario_teste.idade(), 22)

    def test_idade_str(self):
        voluntario_teste = Voluntario.objects.get(data_aniversario= datetime.datetime(2000,12,12))
        self.assertEqual(voluntario_teste.idade_str(), '22 anos')

    def test_menor_idade(self):
        voluntario_teste_menor = Voluntario.objects.get(data_aniversario= datetime.datetime(2008,12,12))
        voluntario_teste_maior = Voluntario.objects.get(data_aniversario= datetime.datetime(2000,12,12))
        self.assertTrue(voluntario_teste_menor.menor_de_idade())
        self.assertFalse(voluntario_teste_maior.menor_de_idade())