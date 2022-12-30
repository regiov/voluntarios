# coding=UTF-8

import os
import urllib.parse
import urllib.request
import json
import datetime
import re

from django.db import models, transaction
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError, MultipleObjectsReturned
from django.core import signing
from django.core.validators import validate_email
from django.dispatch import receiver
from django.urls import reverse

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)

from allauth.account import app_settings as allauth_settings
from allauth.account.models import EmailAddress

from mptt.models import MPTTModel, TreeForeignKey

from notification.utils import notify_support

from .utils import track_data

from django.contrib.auth import password_validation
from allauth.socialaccount.models import SocialAccount

# Unidades federativas do Brasil
UFS = (
    ( u'AC', u'Acre' ),
    ( u'AL', u'Alagoas' ),
    ( u'AM', u'Amazonas' ),
    ( u'AP', u'Amapá' ),
    ( u'BA', u'Bahia' ),
    ( u'CE', u'Ceará' ),
    ( u'DF', u'Distrito Federal' ),
    ( u'ES', u'Espírito Santo' ),
    ( u'GO', u'Goiás' ),
    ( u'MA', u'Maranhão' ),
    ( u'MG', u'Minas Gerais' ),
    ( u'MS', u'Mato Grosso do Sul' ),
    ( u'MT', u'Mato Grosso' ),
    ( u'PA', u'Pará' ),
    ( u'PB', u'Paraíba' ),
    ( u'PE', u'Pernambuco' ),
    ( u'PI', u'Piauí' ),
    ( u'PR', u'Paraná' ),
    ( u'RJ', u'Rio de Janeiro' ),
    ( u'RN', u'Rio Grande do Norte' ),
    ( u'RO', u'Rondônia' ),
    ( u'RS', u'Rio Grande do Sul' ),
    ( u'RR', u'Roraima' ),
    ( u'SC', u'Santa Catarina' ),
    ( u'SE', u'Sergipe' ),
    ( u'SP', u'São Paulo' ),
    ( u'TO', u'Tocantins' ),
)

UFS_SIGLA = [(uf[0], uf[0]) for uf in UFS]

class MyUserManager(BaseUserManager):

    def get_by_natural_key(self, username):
        """
        Sobreposição de método default para viabilizar case-insensitive login.
        """
        return self.get(**{self.model.USERNAME_FIELD: username.lower()})

    def create_user(self, email, nome, password=None):
        """
        Cria e salva um novo usuário com o email, nome e senha fornecidos.
        Método necessário para apps com definição própria de usuário.
        Atenção: não estamos lidando com aceitação de termos de uso por aqui!
        Em princípio apenas o método create_superuser, usado apenas em
        linha de comando, chama este método.
        """
        if not email:
            raise ValidationError('Faltou o e-mail')

        email_normalizado = self.normalize_email(email)
        user = self.model(email=email_normalizado, nome=nome,)

        user.set_password(password)
        user.save(using=self._db)
        request = None # request é usado apenas no envio da mensagem de confirmação do e-mail
        # Usuário cadastrado sem envio de mensagem de confirmação de e-mail. Quando houver
        # tentativa de login o sistema irá enviar a mensagem automaticamente.
        email_obj = EmailAddress.objects.add_email(request, user, email_normalizado, confirm=False)
        email_obj.set_as_primary()
        return user

    def create_superuser(self, email, nome, password):
        """
        Cria e salva um superusuário com o email, nome e senha fornecidos.
        Método necessário para apps com definição própria de usuário.
        Utilizado apenas pela linha de comando.
        """
        user = self.create_user(email, password=password, nome=nome,)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save(using=self._db)
        return user


class Usuario(AbstractBaseUser, PermissionsMixin):
    id           = models.AutoField(primary_key=True)
    email        = models.EmailField(verbose_name=u'E-mail', unique=True,)
    nome         = models.CharField(u'Nome completo', max_length=255)
    is_superuser = models.BooleanField(u'Poderes de superusuário', default=False)
    is_staff     = models.BooleanField(u'Membro da equipe', default=False, help_text=u'Indica que usuário consegue acessar a interface administrativa.')
    is_active    = models.BooleanField(u'Ativo', default=False, help_text=u'Indica que o usuário encontra-se ativo, estando habilitado a fazer login no sistema.')
    date_joined  = models.DateTimeField(u'Data de registro', default=timezone.now)
    link         = models.CharField(u'Link que levou ao cadastro', max_length=20, null=True, blank=True)

    objects = MyUserManager()

    class Meta:
        verbose_name = u'Usuário'
        verbose_name_plural = u'Usuários'

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        if not self.nome:
            return '???'
        space_position = self.nome.find(' ')
        if space_position == -1:
            return self.nome.title()
        return self.nome[:space_position].title()

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Envia mensagem para o usuário.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    @cached_property
    def is_voluntario(self):
        try:
            self.voluntario
            return True
        except ObjectDoesNotExist:
            return False

    @cached_property
    def has_entidade(self):
        return self.vinculoentidade_set.filter(data_fim__isnull=True).count() > 0

    @cached_property
    def has_entidade_aprovada(self):
        return self.vinculoentidade_set.filter(entidade__aprovado=True, data_fim__isnull=True).count() > 0

    def entidades(self):
        return Entidade.objects.filter(vinculoentidade__usuario=self, vinculoentidade__data_fim__isnull=True, vinculoentidade__confirmado=True)

class RemocaoUsuario(models.Model):
    """Registro de remoção de usuário"""
    id      = models.AutoField(primary_key=True)
    momento = models.DateTimeField(u'Momento', default=timezone.now)

    class Meta:
        verbose_name = u'Remoção de usuário'
        verbose_name_plural = u'Remoções de usuários'

    def __str__(self):
        return str(self.id) + ': ' + str(self.momento)

class AreaTrabalho(models.Model):
    """Área de trabalho/ocupação de uma pessoa"""
    """obs: id compatível com banco anterior"""
    id   = models.AutoField(primary_key=True)
    nome = models.CharField(u'Nome', max_length=50, unique=True)

    class Meta:
        verbose_name = u'Área de Trabalho'
        verbose_name_plural = u'Áreas de Trabalho'
        ordering = ('nome',)

    def __str__(self):
        return self.nome

class AreaAtuacao(models.Model):
    """Área de atuação de entidades \ Área de interesse de voluntários"""
    """obs: id INcompatível com banco anterior"""
    id        = models.AutoField(primary_key=True)
    categoria = models.CharField(u'Categoria', max_length=100)
    nome      = models.CharField(u'Nome', max_length=200)
    indice    = models.CharField(u'Índice para ordenação', max_length=20, unique=True)
    id_antigo = models.CharField(u'Id antigo', max_length=10, unique=True)

    class Meta:
        verbose_name = u'Área de Atuação'
        verbose_name_plural = u'Áreas de Atuação'
        ordering = ('indice',)

    def __str__(self):
        return self.nome

class AreaAtuacaoHierarquica(AreaAtuacao):
    """Área de atuação com nome formatado para exibição hierárquica"""
    class Meta:
        proxy = True

    def __str__(self):
        if '.' in self.indice:
            return u"\u00A0\u00A0\u00A0\u25E6 " + self.nome
        return u"\u2022 " + self.nome

@track_data('aprovado')
class Voluntario(models.Model):
    """Voluntário"""
    """obs: id compatível com banco anterior"""
    id                    = models.AutoField(primary_key=True)
    usuario               = models.OneToOneField(Usuario, null=True, on_delete=models.CASCADE)
    data_aniversario_orig = models.CharField(u'Data de nascimento original', max_length=20, null=True, blank=True)
    data_aniversario      = models.DateField(u'Data de nascimento', null=True, blank=True)
    ciente_autorizacao    = models.BooleanField(u'Ciente que menor precisa de autorização', null=True, blank=True)
    profissao             = models.CharField(u'Profissão', max_length=100, null=True, blank=True)
    ddd                   = models.CharField(u'DDD', max_length=4, null=True, blank=True)
    telefone              = models.CharField(u'Telefone', max_length=60, null=True, blank=True)
    #pais                 = models.CharField(u'País', max_length=50)
    estado                = models.CharField(u'Estado', max_length=2)
    cidade                = models.CharField(u'Cidade', max_length=100)
    empregado             = models.BooleanField(u'Empregado', null=True, blank=True)
    empresa               = models.CharField(u'Empresa', max_length=100, null=True, blank=True)
    foi_voluntario        = models.BooleanField(u'Foi voluntário', default=False)
    entidade_que_ajudou   = models.CharField(u'Entidade que ajudou', max_length=100, null=True, blank=True)
    area_trabalho         = models.ForeignKey(AreaTrabalho, verbose_name=u'Área de Trabalho', on_delete=models.PROTECT, null=True, blank=True)
    descricao             = models.TextField(u'Descrição das habilidades', null=True, blank=True)
    newsletter            = models.BooleanField(u'Aceita receber newsletter', default=False)
    fonte                 = models.CharField(u'Fonte', max_length=100, null=True, blank=True)
    site                  = models.BooleanField(u'Site', default=False)
    data_cadastro         = models.DateTimeField(u'Data do cadastro', auto_now_add=True)
    importado             = models.BooleanField(u'Importado da base anterior', default=False)
    aprovado              = models.BooleanField(u'Aprovado', null=True, blank=True)
    # Campo incluído em 05/10/2021 às 10:37. Voluntários que se cadastraram antes dessa data tem este campo nulo e aparecem nas buscas.
    invisivel             = models.BooleanField(u'Invisível nas buscas', null=True, blank=True)
    # Estes 3 campos (*_analise) só são preenchidos na primeira aprovação/rejeição de perfil de voluntário
    # somente através da interface expressa.
    data_analise          = models.DateTimeField(u'Data da análise', null=True, blank=True, db_index=True)
    resp_analise          = models.ForeignKey(Usuario, verbose_name=u'Responsável pela análise', related_name='resp_analise_voluntario_set', on_delete=models.PROTECT, null=True, blank=True)
    # O objetivo deste campo é ajudar na avaliação da análise feita por quem aprova voluntários
    dif_analise           = models.TextField(u'Alterações na análise', null=True, blank=True)
    qtde_visualiza        = models.IntegerField(u'Quantidade de visualizações do perfil (desde 12/01/2019)', default=0)
    ultima_visualiza      = models.DateTimeField(u'Última visualização do voluntário (desde 12/01/2019)', null=True, blank=True)
    ultima_atualizacao    = models.DateTimeField(u'Data de última atualização', auto_now_add=True, null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = u'Voluntário'
        verbose_name_plural = u'Voluntários'
        permissions = (
            ('search_volunteers', u'Can search Voluntário'),
        )
    def __str__(self):
        return self.usuario.nome

    def hit(self):
        '''Contabiliza mais uma visualização do registro'''
        self.qtde_visualiza = self.qtde_visualiza + 1
        self.ultima_visualiza = timezone.now()
        self.save(update_fields=['qtde_visualiza', 'ultima_visualiza'])

    def iniciais(self):
        txt = ''
        partes = self.usuario.nome.split(' ')
        for parte in partes:
            txt = txt + parte[:1].upper() + '.'
        return txt

    def idade(self):
        if self.data_aniversario is not None:
            hoje = datetime.date.today()
            val = hoje.year - self.data_aniversario.year - ((hoje.month, hoje.day) < (self.data_aniversario.month, self.data_aniversario.day))
            return val
        return None

    def idade_str(self):
        val = self.idade()
        if val is not None:
            if val <= 110:
                return str(val) + u' anos'
        return ''

    def menor_de_idade(self):
        val = self.idade()
        if val is not None and val < 18:
            return True
        return False

    def areas_de_interesse(self):
        areas = ''
        cnt = 0
        for area in self.areainteresse_set.all():
            if cnt > 0:
                areas = areas + ', '
            areas = areas + area.area_atuacao.nome
            cnt = cnt + 1
        return areas

    def nao_foi_voluntario(self):
        '''Indica se não possui experiência como voluntário (usado no template do formulário para deixar o campo entidade_que_ajudou invisível)'''
        return not self.foi_voluntario

    def esconder_empresa(self):
        '''Indica se o campo empresa deve ser escondido (usado no template do formulário para deixar o campo empresa invisível)'''
        return self.empregado == False or (self.empregado is None and not self.empresa)

    def tem_termo_de_adesao(self):
        return TermoAdesao.objects.filter(voluntario=self).count() > 0

    def normalizar(self):
        if self.telefone:
            par = self.telefone.find(')')
            if par > 0:
                # Extrai prefixo se necessário
                self.telefone = self.telefone[par+1:].strip()
                if not self.ddd:
                    # Move para DDD
                    self.ddd = self.telefone[:par+1].strip()
        if self.ddd:
            # Remove eventual parentesis
            self.ddd = self.ddd.replace(')', '').replace('(', '')
            if len(self.ddd) > 2 and self.ddd[:1] == '0':
                # Remove eventual zero inicial
                self.ddd = self.ddd[1:]
        if self.usuario.nome == self.usuario.nome.upper() or self.usuario.nome == self.usuario.nome.lower():
            self.usuario.nome = self.usuario.nome.title().replace(' Do ', ' do ').replace(' Da ', ' da ').replace(' Dos ', ' dos ').replace(' Das ', ' das ').replace(' De ', ' de ')
        if self.usuario.email == self.usuario.email.upper():
            self.usuario.email = self.usuario.email.lower()
        if self.cidade and (self.cidade == self.cidade.upper() or self.cidade == self.cidade.lower()):
            self.cidade = self.cidade.title().replace(' Do ', ' do ').replace(' Da ', ' da ').replace(' Dos ', ' dos ').replace(' Das ', ' das ').replace(' De ', ' de ')
        if self.empresa and self.empresa.lower() == 'desempregado':
            self.empresa = ''
        if self.entidade_que_ajudou and self.entidade_que_ajudou.lower() == 'nenhuma':
            self.entidade_que_ajudou = ''
        if self.profissao:
            if self.profissao == self.profissao.upper() or self.profissao == self.profissao.lower():
                self.profissao = self.profissao.title()
            if self.profissao.lower() == 'desempregado':
                self.profissao = ''
            elif self.profissao.lower() == 'dona de casa':
                self.profissao = 'Do Lar'

class AreaInteresse(models.Model):
    """Area de interesse de voluntário"""
    id           = models.AutoField(primary_key=True)
    voluntario   = models.ForeignKey(Voluntario, on_delete=models.CASCADE)
    area_atuacao = models.ForeignKey(AreaAtuacao, on_delete=models.PROTECT, verbose_name=u'Área de Atuação')

    class Meta:
        verbose_name = u'Área de Interesse'
        verbose_name_plural = u'Áreas de Interesse'
        unique_together = ('area_atuacao', 'voluntario')

    def __str__(self):
        return self.area_atuacao.nome

class TipoArtigo(models.Model):
    """Tipo de artigo material (para doação)"""
    id    = models.AutoField(primary_key=True)
    nome  = models.CharField(u'Nome', max_length=50, unique=True)
    ordem = models.IntegerField(u'Ordem de exibição', null=True, blank=True)

    class Meta:
        verbose_name = u'Tipo de artigo para doação'
        verbose_name_plural = u'Tipos de artigos para doação'
        ordering = ('ordem',)

    def __str__(self):
        return self.nome

GEOCODE_STATUS = (
    ('OK', 'Georreferenciado com endereço completo'),
    ('ZERO_RESULTS', 'Não foi possível georreferenciar'),
)

ENTIDADE_SALT = 'ent'

class EntidadeManager(models.Manager):

    def from_hmac_key(self, key):
        "Retorna uma entidade com base na sua chave hmac"
        try:
            max_age = (60 * 60 * 24 * allauth_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
            pk = signing.loads(key, max_age=max_age, salt=ENTIDADE_SALT)
            ret = Entidade.objects.get(pk=pk)
        except (signing.SignatureExpired, signing.BadSignature, Entidade.DoesNotExist):
            ret = None
        return ret

class StatusCnpj(models.Model):
    '''Status de CNPJ. Modelo abstrato para uso no histórico de status e na entidade.
    O conteúdo dos campos na entidade deve sempre ser o da última consulta. Ao realizar
    uma nova consulta, se já houver algum conteúdo na entidade esse conteúdo deve ser
    movido para o histórico, e o resultado da nova consulta é gravado na entidade.
    Como estes campos são usados no model Entidade, todos eles devem aceitar nulo.
    Não fosse por isso apenas o campo erro_consulta_cnpj deveria aceitar nulo.'''
    id                          = models.AutoField(primary_key=True)
    # Possíveis valores já detectados para o campo abaixo: BAIXADA, SUSPENSA, INAPTA, ATIVA
    situacao_cnpj               = models.CharField(u'Situação na Receita Federal', max_length=50, null=True, blank=True)
    motivo_situacao_cnpj        = models.TextField(u'Motivo da situação', null=True, blank=True)
    data_situacao_cnpj          = models.DateField(u'Data da situação', null=True, blank=True)
    # Possíveis valores já detectados para o campo abaixo: INTERVENCAO
    situacao_especial_cnpj      = models.CharField(u'Situação especial na Receita', max_length=50, null=True, blank=True)
    data_situacao_especial_cnpj = models.DateField(u'Data da situação especial', null=True, blank=True)
    ultima_atualizacao_cnpj     = models.DateTimeField(u'Data da última atualização dos dados do CNPJ', null=True, blank=True)
    data_consulta_cnpj          = models.DateTimeField(u'Data da consulta ao CNPJ', null=True, blank=True)
    erro_consulta_cnpj          = models.CharField(u'Erro na consulta do CNPJ', max_length=200, null=True, blank=True)

    class Meta:
        abstract = True

ONBOARDING_STATUS = {0: 'cadastro anterior ao serviço',
                     1: 'ninguém cuidando',
                     2: 'mensagem em preparação',
                     3: 'aguardando envio',
                     4: 'falha no envio',
                     5: 'aguardando retorno',
                     6: 'sem resposta',
                     7: 'aguardando divulgação',
                     8: 'divulgada',
                     9: 'cancelado',
                     }

@track_data('aprovado')
class Entidade(StatusCnpj):
    """Entidade."""
    """obs: id corresponde ao colocweb em registros importados."""

    id                 = models.AutoField(primary_key=True)
    # Dados básicos
    nome_fantasia      = models.CharField(u'Nome Fantasia', max_length=100, null=True, blank=True) 
    razao_social       = models.CharField(u'Razão Social', max_length=120) 
    cnpj               = models.CharField(u'CNPJ', max_length=36, null=True, blank=True) 
    area_atuacao       = models.ForeignKey(AreaAtuacao, verbose_name=u'Área de Atuação', on_delete=models.PROTECT, null=True, blank=True)
    descricao          = models.TextField(u'Descrição', null=True, blank=True)

    # Endereço
    cep                = models.CharField(u'CEP', max_length=10, null=True, blank=True) 
    logradouro         = models.CharField(u'Logradouro', max_length=100, null=True, blank=True) 
    bairro             = models.CharField(u'Bairro', max_length=40, null=True, blank=True) 
    cidade             = models.CharField(u'Cidade', max_length=60, null=True, blank=True) 
    estado             = models.CharField(u'Estado', max_length=4, null=True, blank=True) 
    pais               = models.CharField(u'País', max_length=90, null=True, blank=True)
    coordenadas        = models.PointField(u'Coordenadas', null=True, blank=True)
    geocode_status     = models.CharField(u'Situação do georreferenciamento', choices=GEOCODE_STATUS, max_length=20, null=True, blank=True)
    
    website            = models.CharField(u'Website', max_length=110, null=True, blank=True)
    facebook           = models.CharField(u'Página no facebook', max_length=110, null=True, blank=True)
    instagram          = models.CharField(u'Instagram', max_length=255, null=True, blank=True)
    twitter            = models.CharField(u'Twitter', max_length=20, null=True, blank=True)
    youtube            = models.CharField(u'Canal no youtube', max_length=110, null=True, blank=True)
    voluntarios        = models.CharField(u'Voluntários', max_length=100, null=True, blank=True)
    fundacao           = models.DateField(u'Fundação', null=True, blank=True)
    num_vol            = models.IntegerField(u'Número de voluntários trabalhando atualmente', null=True, blank=True) 
    num_vol_ano        = models.IntegerField(u'Número de voluntários necessários ao longo do ano', null=True, blank=True) 

    # Responsável & contato
    nome_resp          = models.CharField(u'Nome do responsável', max_length=50, null=True, blank=True) 
    sobrenome_resp     = models.CharField(u'Sobrenome do responsável', max_length=70, null=True, blank=True) 
    cargo_resp         = models.CharField(u'Cargo do responsável', max_length=50, null=True, blank=True) 
    nome_contato       = models.CharField(u'Nome da pessoa de contato', max_length=100, null=True, blank=True) 

    # Necessidade de doações
    doacoes            = models.ManyToManyField(TipoArtigo, through='NecessidadeArtigo')
    obs_doacoes        = models.TextField(u'Observações sobre as doações', null=True, blank=True)

    # Campos de gerenciamento
    importado          = models.BooleanField(u'Importado da base anterior', default=False) 
    confirmado         = models.BooleanField(u'E-mail confirmado', default=False)
    confirmado_em      = models.DateTimeField(u'Data da confirmação do e-mail', null=True, blank=True)
    aprovado           = models.BooleanField(u'Cadastro aprovado', null=True, blank=True)
    data_cadastro      = models.DateTimeField(u'Data de cadastro', auto_now_add=True, null=True, blank=True, db_index=True)
    qtde_visualiza     = models.IntegerField(u'Quantidade de visualizações da entidade (desde 12/01/2019)', default=0)
    ultima_visualiza   = models.DateTimeField(u'Última visualização da entidade (desde 12/01/2019)', null=True, blank=True)
    ultima_atualizacao = models.DateTimeField(u'Última atualização feita pelo responsável', auto_now_add=True, null=True, blank=True)
    ultima_revisao     = models.DateTimeField(u'Última revisão', null=True, blank=True)
    
    # Estes 2 campos (*_analise) só são preenchidos na primeira aprovação/rejeição do cadastro
    data_analise       = models.DateTimeField(u'Data da análise', null=True, blank=True, db_index=True)
    resp_analise       = models.ForeignKey(Usuario, verbose_name=u'Responsável pela análise', related_name='resp_analise_entidade_set', on_delete=models.PROTECT, null=True, blank=True)
    
    # Campos utilizados para gerenciar lock de registro na interface administrativa
    resp_bloqueio      = models.ForeignKey(Usuario, verbose_name=u'Em edição por', related_name='resp_bloqueio_entidade_set', on_delete=models.PROTECT, null=True, blank=True)
    data_bloqueio      = models.DateTimeField(u'Início da edição', null=True, blank=True)

    # Campos para gerenciamento de onboading
    # obs: mudar para modelo próprio no futuro??
    resp_onboarding            = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo onboarding', related_name='resp_onboarding_entidade_set', on_delete=models.PROTECT, null=True, blank=True)
    data_resp_onboarding       = models.DateTimeField(u'Data da atribuição do responsável pelo onboarding', null=True, blank=True)
    assunto_msg_onboarding     = models.CharField(u'Assunto da mensagem de boas-vindas', max_length=100, null=True, blank=True)
    msg_onboarding             = models.TextField(u'Mensagem de boas-vindas', null=True, blank=True)
    assinatura_onboarding      = models.CharField(u'Assinatura na mensagem', max_length=100, null=True, blank=True)
    data_envio_onboarding      = models.DateTimeField(u'Data de envio da primeira mensagem de boas-vindas', null=True, blank=True)
    total_envios_onboarding    = models.IntegerField(u'Número de envios de mensagem de boas-vindas', default=0)
    falha_envio_onboarding     = models.TextField(u'Erro no envio da última mensagem de boas-vindas', null=True, blank=True)
    data_visualiza_onboarding  = models.DateTimeField(u'Data da primeira visualização da mensagem de boas-vindas', null=True, blank=True)
    data_ret_envio_onboarding  = models.DateTimeField(u'Data de retorno à mensagem de boas-vindas', null=True, blank=True)
    # campo p/ cancelamento da divulgação?
    link_divulgacao_onboarding = models.CharField(u'Link para postagem de divulgação da entidade', max_length=255, null=True, blank=True)
    cancelamento_onboarding    = models.CharField(u'Motivo de cancelamento do onboarding', max_length=50, null=True, blank=True)

    objects = EntidadeManager()

    class Meta:
        verbose_name = u'Entidade'
        verbose_name_plural = u'Entidades'
        ordering = ('razao_social',)

    def __str__(self):
        return self.razao_social

    def hmac_key(self):
        "Retorna a chave hmac da entidade"
        if self.pk:
            return signing.dumps(obj=self.pk, salt=ENTIDADE_SALT)
        raise ValueError(u'Entidade sem chave primária')

    def esconder_obs_doacoes(self):
        '''Indica se o campo de observações sobre doações deve ser escondido (usado no formulário da entidade)'''
        return self.necessidadeartigo_set.all().count() == 0

    @cached_property
    def vinculos_ativos(self):
        return VinculoEntidade.objects.filter(entidade=self, data_fim__isnull=True, confirmado=True)

    @cached_property
    def gerenciada(self):
        return self.vinculos_ativos.count() > 0

    @cached_property
    def email_principal_obj(self):
        '''Retorna o endereço de e-mail principal como objeto'''
        try:
            return self.email_set.filter(principal=True)[0]
        except Exception:
            return None

    @cached_property
    def email_principal(self):
        '''Retorna o endereço de e-mail principal'''
        email = self.email_principal_obj
        if email:
            return email.endereco
        return None

    @cached_property
    def email_principal_confirmado(self):
        '''Indica se o endereço de e-mail principal foi confirmado'''
        email = self.email_principal_obj
        if email:
            return email.confirmado
        return False

    @cached_property
    def email_principal_sem_problema(self):
        '''Indica se o endereço de e-mail principal não tem problema'''
        email = self.email_principal_obj
        if email:
            return not email.com_problema
        return False

    @cached_property
    def emails(self):
        '''Retorna os endereços de e-mail'''
        emails = ''
        i = 0
        for email in self.email_set.all().order_by('id'):
            if i > 0:
                emails = emails + u' ou '
            emails = emails + email.html()
            i = i + 1
        return emails

    @cached_property
    def emails_confirmados(self):
        '''Retorna os endereços de e-mail confirmados'''
        emails = ''
        i = 0
        for email in self.email_set.filter(confirmado=True, com_problema=False).order_by('id'):
            if i > 0:
                emails = emails + u' ou '
            emails = emails + email.html()
            i = i + 1
        return emails

    @cached_property
    def has_valid_email(self):
        try:
            validate_email(self.email_principal)
            return True
        except Exception:
            return False

    def cnpj_puro(self):
        return self.cnpj.strip().replace('-', '').replace('.', '').replace('/', '')

    def cnpj_valido(self):

        if not self.cnpj:
            return None

        cnpj = self.cnpj.strip()

        if len(cnpj) == 0:
            return None

        cnpj = self.cnpj_puro()
        
        if not cnpj.isdigit():
            # Caracter estranho presente
            return False

        if len(cnpj) != 14:
            # Tamanho incorreto
            return False

        # Verifica dígitos
        l1 = [6,7,8,9,2,3,4,5,6,7,8,9]
        s1 = 0
        for i in range(0,12):
            s1 = s1 + l1[i]*int(cnpj[i])

        d1 = s1%11
        if d1 == 10:
            d1 = 0

        if str(d1) != cnpj[12]:
            # Dígito de verificação incorreto (a)
            return False

        l2 = [5,6,7,8,9,2,3,4,5,6,7,8,9]
        s2 = 0
        for i in range(0,13):
            s2 = s2 + l2[i]*int(cnpj[i])

        d2 = s2%11
        if d2 == 10:
            d2 = 0

        if str(d2) != cnpj[13]:
            # Dígito de verificação incorreto (b)
            return False

        return True

    def verifica_email_principal(self):
        '''Garante apenas um e-mail principal por entidade'''
        tem_principal = False
        emails = self.email_set.all()
        for email in emails:
            if email.principal:
                if tem_principal:
                    # Se já tem e-mail principal, fica apenas com ele
                    email.principal = False
                    email.save(update_fields=['principal'])
                tem_principal = True
        if len(emails) > 0 and not tem_principal:
            # Se não houver e-mail principal, marca o primeiro como sendo
            emails[0].principal = True
            emails[0].save(update_fields=['principal'])

    def hit(self):
        '''Contabiliza mais uma visualização do registro'''
        self.qtde_visualiza = self.qtde_visualiza + 1
        self.ultima_visualiza = timezone.now()
        self.save(update_fields=['qtde_visualiza', 'ultima_visualiza'])

    def menor_nome(self):
        '''Retorna o nome fantasia, se houver. Caso contrário retorna a razão social.'''
        if self.nome_fantasia:
            return self.nome_fantasia
        return self.razao_social

    def endereco(self, logradouro=None):
        '''Retorna logradouro, cidade e estado separados por vírgula'''
        if logradouro is None:
            endereco = self.logradouro if self.logradouro else ''
        else:
            endereco = logradouro
        if self.cidade:
            if endereco:
                endereco = endereco + ', '
            endereco = endereco + self.cidade
        if self.estado:
            if endereco:
                endereco = endereco + ', '
            endereco = endereco + self.estado
        return endereco

    @cached_property
    def telefones(self):
        '''Retorna número completo dos telefones: (ddd) número'''
        telefones = ''
        i = 0
        for tel in self.tel_set.all().order_by('id'):
            if i > 0:
                telefones = telefones + u' ou '
            telefones = telefones + str(tel)
            i = i + 1
        return telefones

    def status(self):
        if self.aprovado is None:
            return u'aguardando revisão'
        elif self.aprovado:
            return u'aprovado'
        return u'rejeitado'

    def status_email(self):
        if self.confirmado:
            return u'confirmado'
        return u'aguardando confirmação'

    def geocode(self, request=None, verbose=False):
        '''Atribui automaticamente uma coordenada à entidade a partir de seu endereço usando o serviço do Google'''
        endereco = self.endereco()
        if len(endereco) == 0:
            self.coordenadas = None
            self.save(update_fields=['coordenadas'])
            return 'NO_ADDRESS'

        logradouro = self.logradouro if self.logradouro else ''

        while True:

            if verbose:
                print(endereco)

            params = urllib.parse.urlencode({'address': endereco,
                                             'key': settings.GOOGLE_MAPS_API_KEY,
                                             'sensor': 'false',
                                             'region': 'br'})

            url = settings.GOOGLE_MAPS_GEOCODE_URL + '?%s' % params

            j = None
            try:
                resp = urllib.request.urlopen(url)
                j = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                motivo = type(e).__name__ + str(e.args)
                notify_support(u'Erro de geocode', u'Entidade: ' + str(self.id) + "\n" + u'Endereço: ' + endereco + "\n" + u'Motivo: ' + motivo, request)
                return 'GOOGLE_ERROR'

            status = 'NO_RESPONSE'
            if j:
                status = 'NO_STATUS'
                if 'status' in j:
                    status = j['status']
                    if status == 'OK':

                        self.coordenadas = Point(j['results'][0]['geometry']['location']['lng'], j['results'][0]['geometry']['location']['lat'])
                        self.geocode_status = status
                        self.save(update_fields=['coordenadas', 'geocode_status'])
                        break

                    elif status == 'ZERO_RESULTS':

                        if logradouro.count(' ') > 1:
                            # Remove última palavra do logradouro e tenta de novo,
                            # pois muitas vezes o google não consegue quando o
                            # logradouro termina em s/n, andar ou outras coisas estranhas
                            partes = logradouro.split(' ')
                            partes.pop()
                            logradouro = ' '.join(partes)
                            endereco = self.endereco(logradouro)
                            continue
                        elif logradouro.count(' ') == 1:
                            # Tenta só com cidade e estado
                            logradouro = ''
                            endereco = self.endereco(logradouro)
                            continue
                        else:
                            self.geocode_status = status
                            self.coordenadas = None
                            self.save(update_fields=['coordenadas', 'geocode_status'])
                            break
                    else:

                        # Status desconhecido
                        notify_support(u'Surpresa no geocode', u'Entidade: ' + str(self.id) + "\n" + u'Endereço: ' + endereco + "\n" + u'Response: ' + str(j), request)
                        break

                # Erro reportado pelo google
                if 'error_message' in j:

                    notify_support(u'Erro de geocode', u'Entidade: ' + str(self.id) + "\n" + u'Endereço: ' + endereco + "\n" + u'Erro: ' + j['error_message'], request)

                    if verbose:
                        print('Dump: ' + str(j))
                        
                    break

        return status

    def atualizar_consulta_cnpj(self, situacao=None, motivo_situacao=None, data_situacao=None, situacao_especial=None, data_situacao_especial=None, ultima_atualizacao=None, erro_consulta=None):

        if self.data_consulta_cnpj is not None:

            # Se a última atualização é a mesma, assume que não mudaram os dados, então só atualiza a data da consulta
            if self.ultima_atualizacao_cnpj == ultima_atualizacao:
                self.data_consulta_cnpj = timezone.now()
                self.save(update_fields=['data_consulta_cnpj'])
                return
            
            # Se tem uma consulta já feita com outra data de atualização, copia os dados dela para o histórico
            novo_historico = HistoricoStatusCnpj(entidade=self, situacao_cnpj=self.situacao_cnpj, motivo_situacao_cnpj=self.motivo_situacao_cnpj, data_situacao_cnpj=self.data_situacao_cnpj, situacao_especial_cnpj=self.situacao_especial_cnpj, data_situacao_especial_cnpj=self.data_situacao_especial_cnpj, ultima_atualizacao_cnpj=self.ultima_atualizacao_cnpj, erro_consulta_cnpj=self.erro_consulta_cnpj)
            novo_historico.save()

        # Grava a nova consulta na entidade
        self.situacao_cnpj = situacao
        self.motivo_situacao_cnpj = motivo_situacao
        self.data_situacao_cnpj = data_situacao
        self.situacao_especial_cnpj = situacao_especial
        self.data_situacao_especial_cnpj = data_situacao_especial
        self.ultima_atualizacao_cnpj = ultima_atualizacao
        self.erro_consulta_cnpj = erro_consulta
        self.data_consulta_cnpj = timezone.now()
        self.save(update_fields=['situacao_cnpj', 'motivo_situacao_cnpj', 'data_situacao_cnpj', 'situacao_especial_cnpj', 'data_situacao_especial_cnpj', 'ultima_atualizacao_cnpj', 'erro_consulta_cnpj', 'data_consulta_cnpj'])

    @transaction.atomic
    def consulta_cnpj(self):
        '''Verifica os dados do cnpj na receita federal através de serviço web de terceiros'''
        if not self.cnpj_valido():
            return False

        url = 'https://www.receitaws.com.br/v1/cnpj/' + self.cnpj_puro()

        j = None
        try:
            resp = urllib.request.urlopen(url)
            j = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            erro = type(e).__name__ + str(e.args)
            self.atualizar_consulta_cnpj(erro_consulta=erro)
            return False

        if not j:
            self.atualizar_consulta_cnpj(erro_consulta='NO_RESPONSE')
            return False

        if 'status' in j:
            status = j['status']
            if status == 'ERROR':
                if 'message' in j:
                    self.atualizar_consulta_cnpj(erro_consulta=j['message'])
                else:
                    self.atualizar_consulta_cnpj(erro_consulta='UNKNOWN_ERROR')
                return False
        else:
            self.atualizar_consulta_cnpj(erro_consulta='NO_STATUS')
            return False

        if 'situacao' and 'data_situacao' and 'motivo_situacao' and 'situacao_especial' and 'data_situacao_especial' and 'ultima_atualizacao' in j:
            data_situacao = j['data_situacao']
            data1 = data_situacao.split('/')
            if len(data1) != 3:
                self.atualizar_consulta_cnpj(erro_consulta='WRONG_DATE1')
                return False
            data_situacao = data1[2] + '-' + data1[1] + '-' + data1[0]
            data_situacao_especial = j['data_situacao_especial']
            if not data_situacao_especial:
                data_situacao_especial = None
            else:
                data2 = data_situacao_especial.split('/')
                if len(data2) != 3:
                    self.atualizar_consulta_cnpj(erro_consulta='WRONG_DATE2')
                    return False
                else:
                    data_situacao_especial = data2[2] + '-' + data2[1] + '-' + data2[0]
            self.atualizar_consulta_cnpj(situacao=j['situacao'], motivo_situacao=j['motivo_situacao'], data_situacao=data_situacao, situacao_especial=j['situacao_especial'], data_situacao_especial=data_situacao_especial, ultima_atualizacao=j['ultima_atualizacao'])
        else:
            self.atualizar_consulta_cnpj(erro_consulta='MISSING_DATA')
            return False
        
        return True

    def onboarding_status(self):
        if self.cancelamento_onboarding:
            return 9 # cancelado
        if self.resp_onboarding is None:
            if self.data_cadastro is None or self.data_cadastro < datetime.datetime(2020,9,21, tzinfo=datetime.timezone.utc):
                return 0 # anterior ao serviço
            return 1 # aguardando responsável
        else:
            if not self.msg_onboarding or ('[[' in self.msg_onboarding or ']]' in self.msg_onboarding):
                return 2 # msg em preparação
            if self.data_envio_onboarding is None:
                return 3 # aguardando envio
            if self.falha_envio_onboarding:
                return 4 # falha no envio
            if self.data_ret_envio_onboarding is None:
                now = timezone.now()
                tolerancia = now - datetime.timedelta(days=settings.ONBOARDING_MAX_DAYS_WAITING_RESPONSE)
                if self.data_envio_onboarding > tolerancia:
                    return 5 # sem resposta
                else:
                    return 6 # aguardando resposta
            else:
                if self.link_divulgacao_onboarding is None:
                    return 7 # aguardando divulgação
                return 8 # divulgado

    def nome_onboarding_status(self):
        status = self.onboarding_status()
        if status == 9:
            return self.cancelamento_onboarding
        return ONBOARDING_STATUS[status]

class AnotacaoEntidade(models.Model):
    """Anotação sobre entidade"""
    id        = models.AutoField(primary_key=True)
    entidade  = models.ForeignKey(Entidade, on_delete=models.CASCADE, related_name='anotacaoentidade_set')
    anotacao  = models.TextField(u'Anotação')
    # Anotações automáticas feitas via programa não possuem usuário associado
    usuario   = models.ForeignKey(Usuario, on_delete=models.PROTECT, null=True, blank=True)
    momento   = models.DateTimeField(u'Momento', auto_now_add=True, null=True, blank=True)
    req_acao  = models.BooleanField(u'Requer alteração', default=False)
    rev       = models.BooleanField(u'Revisada', null=True, blank=True)
    resp_rev  = models.ForeignKey(Usuario, verbose_name=u'Responsável pela revisão', related_name='resp_revisao_anotacao_set', on_delete=models.PROTECT, null=True, blank=True)
    data_rev  = models.DateTimeField(u'Data/hora da revisão', null=True, blank=True)

    class Meta:
        verbose_name = u'Anotação'
        verbose_name_plural = u'Anotações'
        ordering = ('momento',)

    def __str__(self):
        return self.anotacao

VINCULO_SALT = 'vinc'

class VinculoEntidadeManager(models.Manager):

    def from_hmac_key(self, key):
        "Retorna um vínculo com base na sua chave hmac"
        try:
            max_age = (60 * 60 * 24 * allauth_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
            pk = signing.loads(key, max_age=max_age, salt=VINCULO_SALT)
            ret = VinculoEntidade.objects.get(pk=pk)
        except (signing.SignatureExpired, signing.BadSignature, Entidade.DoesNotExist):
            ret = None
        return ret

class VinculoEntidade(models.Model):
    """Vínculo com entidade"""
    id          = models.AutoField(primary_key=True)
    usuario     = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    entidade    = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    data_inicio = models.DateTimeField(u'Data de início do vínculo', auto_now_add=True)
    data_fim    = models.DateTimeField(u'Data de final do vínculo', null=True, blank=True)
    # Quando a entidade é cadastrada pelo próprio usuário, confirmado já começa com o valor True
    # Quando o usuário solicita vínculo com entidade já cadastrada, confirmado começa com False
    # até que o usuário confirme via e-mail.
    confirmado  = models.BooleanField(u'Confirmado', default=False)

    objects = VinculoEntidadeManager()

    class Meta:
        verbose_name = u'Usuário vinculado'
        verbose_name_plural = u'Usuários vinculados'
        ordering = ('entidade', 'usuario',)

    def __str__(self):
        return str(self.usuario) + u' - ' + str(self.entidade)

    def hmac_key(self):
        "Retorna a chave hmac do vínculo"
        if self.pk:
            return signing.dumps(obj=self.pk, salt=VINCULO_SALT)
        raise ValueError(u'Vínculo sem chave primária')

class Necessidade(models.Model):
    """Necessidade de bem/serviço por parte de uma entidade"""
    id               = models.AutoField(primary_key=True)
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    qtde_orig        = models.CharField(u'Quantidade', max_length=510, null=True, blank=True) 
    descricao        = models.CharField(u'Descrição', max_length=510, null=True, blank=True) 
    valor_orig       = models.CharField(u'Valor', max_length=510, null=True, blank=True) 
    data_solicitacao = models.DateTimeField(u'Data da solicitação', auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = u'Necessidade'
        verbose_name_plural = u'Necessidades'

    def __str__(self):
        if self.qtde_orig is None:
            return self.descricao
        return self.qtde_orig + u' ' + self.descricao

class TipoDocumento(models.Model):
    """Tipo de documento"""
    id     = models.AutoField(primary_key=True)
    nome   = models.CharField(u'Nome', max_length=50, unique=True)
    codigo = models.CharField(u'Código', max_length=10, unique=True)

    class Meta:
        verbose_name = u'Tipo de documento'
        verbose_name_plural = u'Tipos de documento'
        ordering = ('nome',)

    def __str__(self):
        return self.nome

def caminho_do_documento(instance, filename):
    # MEDIA_ROOT/e/d1/d2/d3/d4/dn/XYZ_doc_tipodoc.extensão
    # Pega extensão do arquivo e padroniza como caixa baixa
    ext = ''
    pos = filename.rfind('.')
    if pos != -1:
        ext = filename[pos:].lower()
    # Pega os dígitos do id da entidade e define o formato em função disso
    digitos = [i for i in str(instance.entidade.id)]
    padrao = 'e/'
    for i in range(0, len(digitos)):
        padrao = padrao + '{0[' + str(i) + ']}/'
    padrao = padrao + '{1}_doc_{2}{3}'
    # Acrescenta string aleatória para evitar dedução fácil de links
    codigo = get_random_string(7)
    path = padrao.format(digitos, codigo, instance.tipodoc.codigo, ext)
    # Enquanto já existir um arquivo assim, gera outro código
    while os.path.isfile(os.path.join(settings.MEDIA_ROOT, path)):
        codigo = get_random_string(7)
        path = padrao.format(digitos, codigo, instance.tipodoc.codigo, ext)
    return path

class Documento(models.Model):
    """Documento"""
    id            = models.AutoField(primary_key=True)
    tipodoc       = models.ForeignKey(TipoDocumento, verbose_name=u'Tipo de documento', on_delete=models.PROTECT)
    entidade      = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    doc           = models.FileField(u'Arquivo', upload_to=caminho_do_documento)
    data_cadastro = models.DateTimeField(u'Data de cadastro', auto_now_add=True)
    usuario       = models.ForeignKey(Usuario, on_delete=models.PROTECT, null=True)

    class Meta:
        verbose_name = u'Documento'
        verbose_name_plural = u'Documentos'
        ordering = ('entidade', 'data_cadastro',)

    def __str__(self):
        return str(self.tipodoc) + u' ' + str(self.entidade) + u' ' + str(self.id)

@receiver(models.signals.post_delete, sender=Documento)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Remove arquivo do sistema de arquivos quando um objecto 'Documento' é deletado.
    """
    if instance.doc:
        if os.path.isfile(instance.doc.path):
            os.remove(instance.doc.path)

@receiver(models.signals.pre_save, sender=Documento)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Remove arquivo antigo do sistema de arquivos quando um objecto 'Documento' é atualizado.
    """
    if not instance.pk:
        return False

    try:
        old_file = Documento.objects.get(pk=instance.pk).doc
    except Documento.DoesNotExist:
        return False

    new_file = instance.doc
    if not old_file == new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)

TIPO_TEL = (
    ( u'1', u'cel' ),
    ( u'2', u'com' ),
    ( u'3', u'res' ),
)

class Telefone(models.Model):
    """Telefone de um voluntário ou de uma entidade"""
    id               = models.AutoField(primary_key=True)
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE, null=True, related_name='tel_set')
    voluntario       = models.ForeignKey(Voluntario, on_delete=models.CASCADE, null=True, related_name='tel_set')
    tipo             = models.CharField(u'Tipo', max_length=1, choices=TIPO_TEL, null=True, blank=True)
    prefixo          = models.CharField(u'Prefixo', max_length=4, null=True, blank=True)
    numero           = models.CharField(u'Número', max_length=15)
    contato          = models.CharField(u'Contato', max_length=50, null=True, blank=True)
    confirmado       = models.BooleanField(u'Confirmado', default=False)
    data_confirmacao = models.DateTimeField(u'Data da confirmação', null=True, blank=True)
    confirmado_por   = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT)
    resp_cadastro    = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo cadastro', related_name='resp_cadastro_tel_set', on_delete=models.PROTECT, null=True, blank=True)
    data_cadastro    = models.DateTimeField(u'Data do cadastro', auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = u'Telefone'
        verbose_name_plural = u'Telefones'
        ordering = ('data_cadastro',)

    def __str__(self):
        if self.prefixo:
            return u'(' + self.prefixo + u') ' + self.numero
        return self.numero

    def save(self, *args, **kwargs):
        # Trata campos mutuamente exclusivos. Se colocar isso no "clean", fica
        # complicado lidar com formulários que têm campos das classes pai e filho
        # ao mesmo tempo, pois telefones de novos voluntarios só poderiam ser
        # validados depois da inclusão do voluntario. Se colocar no pre-save, dá
        # outro erro maluco em novos telefones
        # (self.voluntario e self.entidade apontam para objetos temporários do tipo lazy)
        if self.voluntario is None and self.entidade is None:
            raise ValidationError(u'Dono do telefone não especificado')
        else:
            if self.voluntario is not None and self.entidade is not None:
                raise ValidationError(u'Mais de um dono especificado para o mesmo telefone '+str(self.voluntario) + u' ' + str(self.entidade))
        super(Telefone, self).save(*args, **kwargs)

    def mudou_numero(self, obj):
        if obj.numero and self.numero:
            return self.numero.strip().replace(' ', '').replace('-', '') != obj.numero.strip().replace(' ', '').replace('-', '')
        return None

EMAIL_SALT = 'email'

class EmailManager(models.Manager):

    def from_hmac_key(self, key):
        "Retorna um email com base na sua chave hmac"
        try:
            max_age = (60 * 60 * 24 * allauth_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
            pk = signing.loads(key, max_age=max_age, salt=EMAIL_SALT)
            ret = Email.objects.get(pk=pk)
        except (signing.SignatureExpired, signing.BadSignature, Email.DoesNotExist):
            ret = None
        return ret

class Email(models.Model):
    '''E-mail. Obs: Na verdade o mesmo e-mail pode ser usado por mais de uma entidade, portanto
    o correto seria uma relação m2m.'''
    id               = models.AutoField(primary_key=True)
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE, related_name='email_set')
    endereco         = models.CharField(u'E-mail', max_length=90)
    principal        = models.BooleanField(u'Principal', default=True)
    confirmado       = models.BooleanField(u'Confirmado', default=False)
    data_confirmacao = models.DateTimeField(u'Data da última confirmação', null=True, blank=True)
    resp_cadastro    = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo cadastro', related_name='resp_cadastro_email_set', on_delete=models.PROTECT, null=True, blank=True)
    data_cadastro    = models.DateTimeField(u'Data do cadastro', auto_now_add=True, null=True, blank=True)
    com_problema     = models.BooleanField(u'Com problema', default=False)

    objects = EmailManager()

    class Meta:
        verbose_name = u'E-mail'
        verbose_name_plural = u'E-mails'
        unique_together = ('entidade', 'endereco')

    def __str__(self):
        return self.endereco

    def hmac_key(self):
        "Retorna a chave hmac do email"
        if self.pk:
            return signing.dumps(obj=self.pk, salt=EMAIL_SALT)
        raise ValueError(u'Email sem chave primária')

    def html(self):
        '''Retorna o endereço com link'''
        return '<a href="mailto:' + self.endereco + '">' + self.endereco + '</a>'

class NecessidadeArtigo(models.Model):
    '''Aceitação de artigo para doação'''
    id            = models.AutoField(primary_key=True)
    entidade      = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    tipoartigo    = models.ForeignKey(TipoArtigo, verbose_name=u'Tipo de artigo', on_delete=models.PROTECT)
    resp_cadastro = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo cadastro', on_delete=models.PROTECT)
    data_cadastro = models.DateTimeField(u'Data do cadastro', auto_now_add=True)

    class Meta:
        verbose_name = u'Artigo aceito como doação'
        verbose_name_plural = u'Artigos aceitos como doação'
        unique_together = ('entidade', 'tipoartigo')

    def __str__(self):
        return str(self.tipoartigo)

class AtividadeAdmin(models.Model):
    """Dados sobre atividades administrativas feitas pelo usuário como parte da equipe do site"""
    id                  = models.AutoField(primary_key=True)
    usuario             = models.OneToOneField(Usuario, on_delete=models.PROTECT)
    ciencia_privacidade = models.DateTimeField(u'Data da ciência sobre o compromisso de privacidade', null=True, blank=True)
    viu_instrucoes_vol  = models.DateTimeField(u'Data da visualização das instruções sobre aprovação de voluntários', null=True, blank=True)

    class Meta:
        verbose_name = u'Atividade nas interfaces administrativas'
        verbose_name_plural = u'Atividades nas interfaces administrativas'

class FraseMotivacionalManager(models.Manager):

    def reflexao_do_dia(self):
        '''Retorna a frase do dia para reflexão'''

        # Lógica antiga de mostrar frase motivacional, uma por dia ao logo do ano
        #num_frases = FraseMotivacional.objects.all().count()
        #
        #if num_frases > 0:
        #    now = datetime.datetime.now()
        #    day_of_year = int(now.strftime("%j"))
        #    position = (day_of_year % num_frases)
        #    frase = FraseMotivacional.objects.all().order_by('id')[position]

        frase = None
        qs_frase = FraseMotivacional.objects.filter(utilizacao__isnull=False)
        # Se não tem nenhuma marcada para utilização
        if qs_frase.count() == 0:
            # Pega a primeira no banco
            qs_frase = FraseMotivacional.objects.all().order_by('id')
            if qs_frase.count() > 0:
                frase = qs_frase[0]
                frase.utilizar_frase()
        # Se tiver frase marcada
        else:
            # Só deve existir uma, mas todo caso pega a primeira
            frase = qs_frase[0]
            # Verifica se a data coincide com a data atual. Se coincidir, retorna ela.
            if frase.utilizacao != datetime.date.today():
                # Se não coincidir, pega a próxima frase na sequência de ids
                qs_frase = FraseMotivacional.objects.filter(pk__gt=frase.pk).order_by('id')
                if qs_frase.count() == 0:
                    # Se não tiver próxima, começa do zero
                    qs_frase = FraseMotivacional.objects.all().order_by('id')
                if qs_frase.count() > 0:
                    frase = qs_frase[0]
                    frase.utilizar_frase()
        return frase

class FraseMotivacional(models.Model):
    """Frase motivacional"""
    id    = models.AutoField(primary_key=True)
    frase = models.TextField(u'Frase')
    autor = models.TextField(u'Autor')
    mais_info = models.TextField(u'Texto com informações adicionais', null=True, blank=True)
    link_mais_info = models.TextField(u'Link opcional das informações adicionais', null=True, blank=True)
    # O campo abaixo só deve ser preenchido para um registro. Se a data coincidir com a data atual,
    # a frase é que deve ser exibida no dia, do contrário deve-se utilizar o próximo registro,
    # apagando a data do registro anterior e gravando a data atual no próximo registro.
    utilizacao = models.DateField(u'Data de utilização da frase', null=True, blank=True)

    objects = FraseMotivacionalManager()

    class Meta:
        verbose_name = u'Frase motivacional'
        verbose_name_plural = u'Frases motivacionais'

    def __str__(self):
        return '"' + self.frase + '" (' + self.autor + ')'

    def utilizar_frase(self):
        with transaction.atomic():
            FraseMotivacional.objects.filter(utilizacao__isnull=False).update(utilizacao=None)
            self.utilizacao = datetime.date.today()
            self.save(update_fields=['utilizacao'])

class Conteudo(models.Model):
    """Encapsulamento de conteúdo para rastrear o acesso a ele"""
    id             = models.AutoField(primary_key=True)
    codigo         = models.CharField(u'Código', max_length=50, null=True, blank=True) # Mudar para não nulo e único
    nome           = models.CharField(u'Nome', max_length=200)
    nome_url       = models.CharField(u'Nome da URL no arquivo urls.py', max_length=100)
    parametros_url = models.TextField(u'Parâmetros da URL em formato de dicionário', null=True, blank=True)

    class Meta:
        verbose_name = u'Conteúdo com rastreamento de acesso'
        verbose_name_plural = u'Conteúdos com rastreamento de acesso'

    def __str__(self):
        return self.nome

    def get_url(self):
        if self.parametros_url:
            return reverse(self.nome_url, kwargs=eval(self.parametros_url))
        return reverse(self.nome_url)

class AcessoAConteudo(models.Model):
    """Registro de acesso a conteúdo"""
    id       = models.AutoField(primary_key=True)
    usuario  = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    conteudo = models.ForeignKey(Conteudo, on_delete=models.CASCADE)
    # Algumas visualizações importadas de outros locais podem não ter data/hora
    momento  = models.DateTimeField(u'Data/hora da visualização', default=timezone.now, null=True, blank=True)

    class Meta:
        verbose_name = u'Visualização de conteúdo'
        verbose_name_plural = u'Visualizações de conteúdo'
        # Podemos ter repetição da combinação usuário/conteúdo (um usuário pode visualizar o conteúdo mais de uma vez)

class ForcaTarefa(models.Model):
    """Força Tarefa"""
    id             = models.AutoField(primary_key=True)
    tarefa         = models.CharField(u'Tarefa', max_length=200)
    codigo         = models.CharField(u'Código', max_length=50, null=True, blank=True) # Mudar para não nulo e único
    data_cadastro  = models.DateTimeField(u'Data de cadastro', auto_now_add=True)
    meta           = models.IntegerField(u'Total de registros a serem revisados', null=True, blank=True)
    modelo         = models.CharField(u'Nome do modelo usado na busca', help_text=u'Ex: Entidade, Voluntario', max_length=60)
    filtro         = models.TextField(u'Filtro usado na busca em formato de dicionário')
    url            = models.CharField(u'Link para página da tarefa', max_length=80)
    visivel        = models.BooleanField(u'Visível no painel de controle', default=True)
    orientacoes    = models.ForeignKey(Conteudo, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = u'Força tarefa'
        verbose_name_plural = u'Forças tarefas'

    def __str__(self):
        return self.tarefa

class HistoricoStatusCnpj(StatusCnpj):
    '''Histórico de status de CNPJ'''
    id       = models.AutoField(primary_key=True)
    entidade = models.ForeignKey(Entidade, on_delete=models.CASCADE)

    class Meta:
        verbose_name = u'Histórico de status de CNPJ'
        verbose_name_plural = u'Historicos de status de CNPJ'

    def __str__(self):
        return self.situacao_cnpj + u' ' + str(self.data_situacao_cnpj)

TIPO_DOC_IDENTIF = (
    ( u'RG', u'RG' ),
    ( u'RNE', u'RNE' ),
    ( u'CNH', u'CNH' ),
)

ESTADO_CIVIL = (
    ( u'S', u'solteira(o)' ),
    ( u'C', u'casada(o)' ),
    ( u'P', u'separada(o)' ),
    ( u'D', u'divorciada(o)' ),
    ( u'V', u'viúva(o)' ),
)

TERMOADESAO_SALT = 'ta'

class TermoAdesaoManager(models.Manager):

    def from_hmac_key(self, key):
        "Retorna um termo de adesao com base na sua chave hmac"
        # use try except (signing.SignatureExpired, signing.BadSignature, TermoAdesao.DoesNotExist)
        max_age = (60 * 60 * 24 * 60) # 60 dias para aceitar
        slug = signing.loads(key, max_age=max_age, salt=TERMOADESAO_SALT)
        return TermoAdesao.objects.get(slug=slug)

class TermoAdesao(models.Model):
    """Termo de adesão de trabalho voluntário em entidade"""
    id                       = models.AutoField(primary_key=True)
    slug                     = models.SlugField(max_length=10, unique=True)
    entidade                 = models.ForeignKey(Entidade, on_delete=models.SET_NULL, null=True, blank=True)
    nome_entidade            = models.CharField(u'Nome da entidade', max_length=120) 
    cnpj_entidade            = models.CharField(u'CNPJ da entidade', max_length=36, null=True, blank=True) 
    endereco_entidade        = models.TextField(u'Endereço da entidade', null=True, blank=True)
    email_voluntario         = models.EmailField(verbose_name=u'E-mail do voluntário')
    # O termo pode ser enviado para qualquer e-mail, mas para aceitar o voluntário deverá se cadastrar no site
    voluntario               = models.ForeignKey(Voluntario, on_delete=models.SET_NULL, null=True, blank=True)
    # Os campos abaixo são nulos para permitir que um termo seja criado somente com o e-mail,
    # deixando os campos para serem preenchidos posteriormente pelo voluntário
    nome_voluntario          = models.CharField(u'Nome do voluntário', max_length=255, null=True, blank=True)
    nacionalidade_voluntario = models.CharField(u'Nacionalidade do voluntário', max_length=100, null=True, blank=True)
    tipo_identif_voluntario  = models.CharField(u'Tipo de identidade do voluntário', choices=TIPO_DOC_IDENTIF, max_length=3, null=True, blank=True)
    identif_voluntario       = models.CharField(u'Identidade do voluntário', max_length=20, null=True, blank=True)
    cpf_voluntario           = models.CharField(u'CPF do voluntário', max_length=20, null=True, blank=True)
    estado_civil_voluntario  = models.CharField(u'Estado civil do voluntário', choices=ESTADO_CIVIL, max_length=1, null=True, blank=True)
    nascimento_voluntario    = models.DateField(u'Data de nascimento do voluntário', null=True, blank=True)
    profissao_voluntario     = models.CharField(u'Profissão do voluntário', max_length=100, null=True, blank=True)
    endereco_voluntario      = models.TextField(u'Endereço do voluntário', null=True, blank=True)
    ddd_voluntario           = models.CharField(u'DDD do voluntário', max_length=4, null=True, blank=True)
    telefone_voluntario      = models.CharField(u'Telefone do voluntário', max_length=60, null=True, blank=True)
    # Campos preenchidos pela entidade
    condicoes                = models.TextField(u'Condições') # Cláusulas
    atividades               = models.TextField(u'Atividades') # atividades a serem desenvolvidas
    texto_aceitacao          = models.TextField(u'Texto da aceitação') # ex: [] declaro estar de acordo com...
    data_inicio              = models.DateField(u'Data de início')
    data_fim                 = models.DateField(u'Data de fim', null=True, blank=True) # nulo para indeterminado
    carga_horaria            = models.TextField(u'Dias e horários de execução das atividades')
    # Campos de preenchimento automático
    data_cadastro            = models.DateTimeField(u'Data de cadastro', auto_now_add=True)
    resp_cadastro            = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo cadastro', related_name='resp_cadastro_set', on_delete=models.SET_NULL, null=True, blank=True)
    nome_resp_cadastro       = models.CharField(u'Nome do responsável pelo cadastro', max_length=255, null=True, blank=True)
    resp_entidade            = models.ForeignKey(Usuario, verbose_name=u'Responsável por parte da entidade', related_name='resp_entidade_set', on_delete=models.SET_NULL, null=True, blank=True)
    nome_resp_entidade       = models.CharField(u'Nome do responsável por parte da entidade', max_length=255, null=True, blank=True)
    data_envio_vol           = models.DateTimeField(u'Data de envio do termo para o voluntário por e-mail', null=True, blank=True)
    erro_envio_vol           = models.TextField(u'Erro no envio do e-mail para o voluntário', null=True, blank=True)
    data_aceitacao_vol       = models.DateTimeField(u'Data de aceitação pelo voluntário', null=True, blank=True)
    ip_aceitacao_vol         = models.GenericIPAddressField(u'Endereço IP usado na aceitação do voluntário', null=True, blank=True)
    data_rescisao            = models.DateTimeField(u'Data de rescisão', null=True, blank=True)
    resp_rescisao            = models.ForeignKey(Usuario, verbose_name=u'Responsável pela rescisão', related_name='resp_rescisao_set', on_delete=models.SET_NULL, null=True, blank=True)
    nome_resp_rescisao       = models.CharField(u'Nome do responsável pela rescisão', max_length=255, null=True, blank=True)
    motivo_rescisao          = models.TextField(u'Motivo da rescisão', null=True, blank=True)

    objects = TermoAdesaoManager()

    class Meta:
        verbose_name = 'Termo de adesão'
        verbose_name_plural = 'Termos de adesão'

    def __str__(self):
        return self.nome_entidade + ' | ' + self.email_voluntario

    def hmac_key(self):
        "Retorna a chave hmac do termo de adesão"
        if self.slug:
            return signing.dumps(obj=self.slug, salt=TERMOADESAO_SALT)
        raise ValueError(u'Termo de adesão sem slug')

    def gen_slug(self):
        """ Gera slug aleatório para o termo."""
        size = 10
        if not self.slug:
            self.slug = get_random_string(size)
            slug_is_wrong = True  
            while slug_is_wrong:
                slug_is_wrong = False
                other_objs_with_slug = TermoAdesao.objects.filter(slug=self.slug)
                if len(other_objs_with_slug) > 0:
                    slug_is_wrong = True
                if slug_is_wrong:
                    self.slug = get_random_string(size)

    def save(self, *args, **kwargs):
        """ Add Slug creating/checking to save method. """
        self.gen_slug()
        super(TermoAdesao, self).save(*args, **kwargs)

    def horas_do_ultimo_envio_vol(self):
        if self.data_envio_vol is None:
            return None
        delta = timezone.now()-self.data_envio_vol
        return delta.seconds//3600

    def link_assinatura_vol(self, request, absolute=True):
        link = reverse('assinatura_vol_termo_de_adesao')
        if absolute:
            link = request.build_absolute_uri(link)
        return link + '?' + urllib.parse.urlencode({'h': self.hmac_key()})

    def nome_estado_civil_voluntario(self):
        for estado_civil in ESTADO_CIVIL:
            if self.estado_civil_voluntario == estado_civil[0]:
                return estado_civil[1]
        return None

    def telefone_completo_voluntario(self):
        if self.ddd_voluntario and self.telefone_voluntario:
            tel = '55' + self.ddd_voluntario.lstrip('0') + self.telefone_voluntario
            return re.sub(r'[^0-9]', '', tel)
        return None

    def vigente(self):
        current_tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(current_tz)
        hoje = timezone.date()
        if self.data_inicio > hoje:
            return False
        if self.data_fim and self.data_fim < hoje:
            return False
        return True

class Funcao(MPTTModel):
    """Árvrore de funções a serem desempenhadas numa entidade"""
    id           = models.AutoField(primary_key=True)
    entidade     = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    nome         = models.CharField('Nome', max_length=200)
    # Ordenação de funções do mesmo nível
    ordem        = models.SmallIntegerField()
    descricao    = models.TextField(u'Descrição', null=True, blank=True)
    # Quantidade de pessoas que podem desempenhar a tarefa (apenas para tarefas de último nível)
    qtde_pessoas = models.IntegerField(u'Qtde de pessoas', null=True, blank=True, default=0)
    # Enquanto não criamos uma nova tabela para vincular pessoas a funções, podemos listar as pessoas aqui
    responsaveis = models.TextField(u'Responsáveis', null=True, blank=True)
    # Função superior
    parent       = TreeForeignKey('self', verbose_name='Função superior', on_delete=models.PROTECT, null=True, blank=True, related_name='children')

    class Meta:
        verbose_name = 'Função'
        verbose_name_plural = 'Funções'

    class MPTTMeta:
        order_insertion_by = ['ordem']

    def __str__(self):
        return self.nome
