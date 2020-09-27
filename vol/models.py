# coding=UTF-8

import os
import urllib.parse
import urllib.request
import json
import datetime

from django.db import models, transaction
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core import signing
from django.core.validators import validate_email
from django.dispatch import receiver
from django.urls import reverse

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)

from allauth.account import app_settings as allauth_settings

from notification.utils import notify_support

from .utils import track_data

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
        Utilizado apenas pela interface adm.
        """
        if not email:
            raise ValidationError('Faltou o e-mail')

        user = self.model(email=self.normalize_email(email), nome=nome,)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, password):
        """
        Cria e salva um superusuário com o email, nome e senha fornecidos.
        Método necessário para apps com definição própria de usuário.
        Utilizado apenas pela interface adm.
        """
        user = self.create_user(email, password=password, nome=nome,)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save(using=self._db)
        return user

class Usuario(AbstractBaseUser, PermissionsMixin):
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
    momento = models.DateTimeField(u'Momento', default=timezone.now)

    class Meta:
        verbose_name = u'Remoção de usuário'
        verbose_name_plural = u'Remoções de usuários'

    def __str__(self):
        return str(self.id) + ': ' + str(self.momento)

class AreaTrabalho(models.Model):
    """Área de trabalho/ocupação de uma pessoa"""
    """obs: id compatível com banco anterior"""
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
    voluntario   = models.ForeignKey(Voluntario, on_delete=models.CASCADE)
    area_atuacao = models.ForeignKey(AreaAtuacao, on_delete=models.PROTECT, verbose_name=u'Área de Atuação')

    class Meta:
        verbose_name = u'Área de Interesse'
        verbose_name_plural = u'Áreas de Interesse'
        unique_together = ('area_atuacao', 'voluntario')

    def __str__(self):
        return self.area_atuacao.nome

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

@track_data('aprovado')
class Entidade(models.Model):
    """Entidade."""
    """obs: id corresponde ao colocweb em registros importados."""
    nome_fantasia      = models.CharField(u'Nome Fantasia', max_length=100, null=True, blank=True) 
    razao_social       = models.CharField(u'Razão Social', max_length=120) 
    cnpj               = models.CharField(u'CNPJ', max_length=36, null=True, blank=True) 
    area_atuacao       = models.ForeignKey(AreaAtuacao, verbose_name=u'Área de Atuação', on_delete=models.PROTECT, null=True, blank=True)
    descricao          = models.TextField(u'Descrição', null=True, blank=True)
    cep                = models.CharField(u'CEP', max_length=10, null=True, blank=True) 
    logradouro         = models.CharField(u'Logradouro', max_length=100, null=True, blank=True) 
    bairro             = models.CharField(u'Bairro', max_length=40, null=True, blank=True) 
    cidade             = models.CharField(u'Cidade', max_length=60, null=True, blank=True) 
    estado             = models.CharField(u'Estado', max_length=4, null=True, blank=True) 
    pais               = models.CharField(u'País', max_length=90, null=True, blank=True)
    coordenadas        = models.PointField(u'Coordenadas', null=True, blank=True)
    geocode_status     = models.CharField(u'Situação do georreferenciamento', choices=GEOCODE_STATUS, max_length=20, null=True, blank=True) 
    website            = models.CharField(u'Website', max_length=110, null=True, blank=True) 
    despesas           = models.CharField(u'Despesas', max_length=100, null=True, blank=True) 
    beneficiados       = models.CharField(u'Beneficiados', max_length=100, null=True, blank=True) 
    voluntarios        = models.CharField(u'Voluntários', max_length=100, null=True, blank=True) 
    reg_cnas           = models.CharField(u'Registro CNAS', max_length=50, null=True, blank=True)
    fundacao           = models.DateField(u'Fundação', null=True, blank=True) 
    auditores          = models.CharField(u'Auditores', max_length=100, null=True, blank=True) 
    premios            = models.CharField(u'Prêmios', max_length=100, null=True, blank=True) 
    num_vol            = models.IntegerField(u'Número de voluntários trabalhando atualmente', null=True, blank=True) 
    num_vol_ano        = models.IntegerField(u'Número de voluntários necessários ao longo do ano', null=True, blank=True) 

    nome_resp          = models.CharField(u'Nome do responsável', max_length=50, null=True, blank=True) 
    sobrenome_resp     = models.CharField(u'Sobrenome do responsável', max_length=70, null=True, blank=True) 
    cargo_resp         = models.CharField(u'Cargo do responsável', max_length=50, null=True, blank=True) 
    nome_contato       = models.CharField(u'Nome da pessoa de contato', max_length=100, null=True, blank=True) 

    banco              = models.CharField(u'Banco', max_length=74, null=True, blank=True) 
    agencia            = models.CharField(u'Agência', max_length=14, null=True, blank=True) 
    conta              = models.CharField(u'Conta', max_length=26, null=True, blank=True) 

    mytags             = models.CharField(u'Tags (sep. por vírgula)', max_length=100, null=True, blank=True) 

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
        for email in self.email_set.filter(confirmado=True).order_by('id'):
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

class AnotacaoEntidade(models.Model):
    """Anotação sobre entidade"""
    entidade  = models.ForeignKey(Entidade, on_delete=models.CASCADE, related_name='anotacaoentidade_set')
    anotacao  = models.TextField(u'Anotação')
    usuario   = models.ForeignKey(Usuario, on_delete=models.PROTECT)
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
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE, related_name='email_set')
    endereco         = models.CharField(u'E-mail', max_length=90)
    principal        = models.BooleanField(u'Principal', default=True)
    confirmado       = models.BooleanField(u'Confirmado', default=False)
    data_confirmacao = models.DateTimeField(u'Data da última confirmação', null=True, blank=True)
    resp_cadastro    = models.ForeignKey(Usuario, verbose_name=u'Responsável pelo cadastro', related_name='resp_cadastro_email_set', on_delete=models.PROTECT, null=True, blank=True)
    data_cadastro    = models.DateTimeField(u'Data do cadastro', auto_now_add=True, null=True, blank=True)

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

class AtividadeAdmin(models.Model):
    """Dados sobre atividades administrativas feitas pelo usuário como parte da equipe do site"""
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
