# coding=UTF-8

from django.test import TestCase
import datetime

from ..models import Usuario, Voluntario

class UsuarioTestCase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(
            email= 'voluntarios@gmail.com',
            nome= 'Voluntario Teste',
        )

    def test_retorno_str(self):
        usuario_teste = Usuario.objects.get(email='voluntarios@gmail.com')
        self.assertEqual(usuario_teste.__str__(), 'voluntarios@gmail.com')
    
    def test_retorno_get_full_name(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')
        self.assertEqual(usuario_teste.get_full_name(), 'Voluntario Teste')
    
    def test_retorno_get_short_name(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')
        self.assertEqual(usuario_teste.get_short_name(), 'Voluntario')

    def test_retorno_is_voluntario(self):
        usuario_teste = Usuario.objects.get(nome= 'Voluntario Teste')

        voluntario_teste = Voluntario.objects.create(
            usuario = usuario_teste
        )
        
        self.assertTrue(usuario_teste.is_voluntario)

class VoluntarioTestCase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(
            email= 'voluntarios@gmail.com',
            nome= 'Voluntario Teste',
        )
        
        voluntario = Voluntario.objects.create(
            usuario= usuario,
            data_aniversario= datetime.datetime(2000,12,12),
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

        usuario_menor = Usuario.objects.create(
            email= 'menor_idade@gmail.com',
            nome= 'Menor Idade'
        )

        voluntario_menor = Voluntario.objects.create(
            usuario= usuario_menor,
            data_aniversario= datetime.datetime(2020,12,12)
        )
        voluntario_teste = Voluntario.objects.get(data_aniversario= datetime.datetime(2020,12,12))
        self.assertTrue(voluntario_teste.menor_de_idade())

    def test_maior_idade(self):

        voluntario_teste = Voluntario.objects.get(data_aniversario= datetime.datetime(2000,12,12))
        self.assertFalse(voluntario_teste.menor_de_idade())

    def test_normalizar(self):

        usuario_norm = Usuario.objects.create(
            email= 'NORM@GMAIL.COM',
            nome= 'usuario da normalizar'
        )

        voluntario_norm = Voluntario.objects.create(
            usuario= usuario_norm,
            data_aniversario= datetime.datetime(2002,12,12),
            telefone= '(021)99999999',
            cidade='RIO DE JANEIRO',
            profissao='ESTUDANTE',
            entidade_que_ajudou='NENHUMA',
            empresa='DESEMPREGADO',
        )

        voluntario_teste = Voluntario.objects.get(data_aniversario= datetime.datetime(2002,12,12))
        voluntario_teste.normalizar()
        
        self.assertEqual(voluntario_teste.ddd,'21')
        self.assertEqual(voluntario_teste.telefone,'99999999')
        self.assertEqual(voluntario_teste.usuario.nome, 'Usuario da Normalizar')
        self.assertEqual(voluntario_teste.usuario.email, 'norm@gmail.com')
        self.assertEqual(voluntario_teste.cidade, 'Rio de Janeiro')
        self.assertEqual(voluntario_teste.empresa, '')
        self.assertEqual(voluntario_teste.entidade_que_ajudou, '')
        self.assertEqual(voluntario_teste.profissao, 'Estudante')