# coding=UTF-8

import urllib.parse
import urllib.request
import json
from datetime import date, datetime

from django.db import models
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.functional import cached_property
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core import signing
from django.core.validators import validate_email

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)

from allauth.account import app_settings as allauth_settings

from notification.utils import notify_support

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

class Voluntario(models.Model):
    """Voluntário"""
    """obs: id compatível com banco anterior"""
    usuario               = models.OneToOneField(Usuario, null=True, on_delete=models.CASCADE)
    data_aniversario_orig = models.CharField(u'Data de nascimento original', max_length=20, null=True, blank=True)
    data_aniversario      = models.DateField(u'Data de nascimento', null=True, blank=True)
    profissao             = models.CharField(u'Profissão', max_length=100, null=True, blank=True)
    ddd                   = models.CharField(u'DDD', max_length=4, null=True, blank=True)
    telefone              = models.CharField(u'Telefone', max_length=60, null=True, blank=True)
    cidade                = models.CharField(u'Cidade', max_length=100)
    estado                = models.CharField(u'Estado', max_length=2)
    #pais                 = models.CharField(u'País', max_length=50)
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
    aprovado              = models.NullBooleanField(u'Aprovado')
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
        self.ultima_visualiza = datetime.now()
        self.save(update_fields=['qtde_visualiza', 'ultima_visualiza'])

    def iniciais(self):
        txt = ''
        partes = self.usuario.nome.split(' ')
        for parte in partes:
            txt = txt + parte[:1].upper() + '.'
        return txt

    def idade(self):
        if self.data_aniversario is not None:
            hoje = date.today()
            val = hoje.year - self.data_aniversario.year - ((hoje.month, hoje.day) < (self.data_aniversario.month, self.data_aniversario.day))
            if val <= 110:
                return str(val) + u' anos'
        return ''

    def areas_de_interesse(self):
        areas = ''
        cnt = 0
        for area in self.areainteresse_set.all():
            if cnt > 0:
                areas = areas + ', '
            areas = areas + area.area_atuacao.nome
            cnt = cnt + 1
        return areas

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

class Entidade(models.Model):
    """Entidade."""
    """obs: id corresponde ao colocweb em registros importados."""
    nome_fantasia      = models.CharField(u'Nome Fantasia', max_length=100, null=True, blank=True) 
    razao_social       = models.CharField(u'Razão Social', max_length=120) 
    cnpj               = models.CharField(u'CNPJ', max_length=36, null=True, blank=True) 
    area_atuacao       = models.ForeignKey(AreaAtuacao, verbose_name=u'Área de Atuação', on_delete=models.PROTECT, null=True)
    descricao          = models.TextField(u'Descrição', null=True, blank=True)
    cep                = models.CharField(u'CEP', max_length=10, null=True, blank=True) 
    logradouro         = models.CharField(u'Logradouro', max_length=100, null=True, blank=True) 
    bairro             = models.CharField(u'Bairro', max_length=40, null=True, blank=True) 
    cidade             = models.CharField(u'Cidade', max_length=60, null=True, blank=True) 
    estado             = models.CharField(u'Estado', max_length=4, null=True, blank=True) 
    coordenadas        = models.PointField(u'Coordenadas', null=True, blank=True)
    geocode_status     = models.CharField(u'Situação do georreferenciamento', choices=GEOCODE_STATUS, max_length=20, null=True, blank=True) 
    ddd                = models.CharField(u'DDD', max_length=4, null=True, blank=True)
    telefone           = models.CharField(u'Telefone', max_length=100, null=True, blank=True) 
    email              = models.CharField(u'E-mail', max_length=90, null=True, blank=True) 
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

    importado          = models.BooleanField(u'Importado da base anterior', default=False) 
    confirmado         = models.BooleanField(u'E-mail confirmado', default=False)
    confirmado_em      = models.DateTimeField(u'Data da confirmação do e-mail', null=True, blank=True)
    aprovado           = models.NullBooleanField(u'Cadastro revisado e aprovado')
    data_cadastro      = models.DateTimeField(u'Data de cadastro', auto_now_add=True, null=True, blank=True, db_index=True)
    qtde_visualiza     = models.IntegerField(u'Quantidade de visualizações da entidade (desde 12/01/2019)', default=0)
    ultima_visualiza   = models.DateTimeField(u'Última visualização da entidade (desde 12/01/2019)', null=True, blank=True)
    ultima_atualizacao = models.DateTimeField(u'Última atualização feita pelo responsável', auto_now=True, null=True, blank=True)
    ultima_revisao     = models.DateTimeField(u'Última revisão', null=True, blank=True)

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
    def gerenciada(self):
        return VinculoEntidade.objects.filter(entidade=self, data_fim__isnull=True, confirmado=True).count() > 0

    @cached_property
    def has_valid_email(self):
        try:
            validate_email(self.email)
            return True
        except Exception:
            return False

    def hit(self):
        '''Contabiliza mais uma visualização do registro'''
        self.qtde_visualiza = self.qtde_visualiza + 1
        self.ultima_visualiza = datetime.now()
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

    def numero_telefone(self):
        '''Retorna número completo do telefone: (ddd) número'''
        if self.ddd:
            return '(' + self.ddd + ') ' + self.telefone
        return self.telefone

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
    entidade = models.ForeignKey(Entidade, on_delete=models.CASCADE)
    anotacao = models.TextField(u'Anotação')
    usuario  = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    momento  = models.DateTimeField(u'Momento', auto_now_add=True, null=True, blank=True)
    req_acao = models.BooleanField(u'Requer alteração', default=False)

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
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE, null=True)
    id_ong           = models.IntegerField(u'IDOng', null=True, blank=True) 
    qtde_orig        = models.CharField(u'Quantidade', max_length=510, null=True, blank=True) 
    descricao        = models.CharField(u'Descrição', max_length=510, null=True, blank=True) 
    valor_orig       = models.CharField(u'Valor', max_length=510, null=True, blank=True) 
    data_solicitacao = models.DateTimeField(u'Data da solicitação', auto_now_add=True, null=True, blank=True)

    def __str__(self):
        if self.qtde_orig is None:
            return self.descricao
        return self.qtde_orig + u' ' + self.descricao
