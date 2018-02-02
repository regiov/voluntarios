# coding=UTF-8

import urllib.parse
import urllib.request
import json
from datetime import date

from django.db import models
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point

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
    indice    = models.CharField(u'Índice numerado', max_length=20, unique=True)
    id_antigo = models.CharField(u'Id antigo', max_length=10, unique=True)

    class Meta:
        verbose_name = u'Área de Atuação'
        verbose_name_plural = u'Áreas de Atuação'
        ordering = ('id',)

    def __str__(self):
        return self.nome

class Voluntario(models.Model):
    """Voluntário"""
    """obs: id compatível com banco anterior"""
    nome                  = models.CharField(u'Nome completo', max_length=100)
    data_aniversario_orig = models.CharField(u'Data de nascimento original', max_length=20, null=True, blank=True)
    data_aniversario      = models.DateField(u'Data de nascimento', null=True, blank=True)
    profissao             = models.CharField(u'Profissão', max_length=100, null=True, blank=True)
    email                 = models.EmailField(u'E-mail', db_index=True)
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
    confirmado            = models.BooleanField(u'E-mail confirmado', default=False)
    aprovado              = models.NullBooleanField(u'Cadastro revisado e aprovado')

    class Meta:
        verbose_name = u'Voluntário'
        verbose_name_plural = u'Voluntários'
        ordering = ('nome',)

    def __str__(self):
        return self.nome

    def iniciais(self):
        txt = ''
        partes = self.nome.split(' ')
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

class EntNec(models.Model):
    """Tabela temporária para armazenar dados de tblEntidades do banco V_EntNec97Asp.mdb"""
    colocweb      = models.IntegerField(u'colocweb') 
    entidade      = models.CharField(u'Entidade', max_length=120) 
    nomeguerra    = models.CharField(u'Nome de guerra', max_length=100, null=True, blank=True) 
    cgc           = models.CharField(u'CGC', max_length=36, null=True, blank=True) 
    mantenedor    = models.CharField(u'mantenedor', max_length=60, null=True, blank=True) 
    reg_cnas      = models.CharField(u'reg_cnas', max_length=50, null=True, blank=True)
    fundacao      = models.DateTimeField(u'fundacao', null=True, blank=True) 
    sede          = models.IntegerField(u'sede', null=True, blank=True) 
    endrec1       = models.CharField(u'endrec1', max_length=100, null=True, blank=True) 
    bairro        = models.CharField(u'Bairro', max_length=40, null=True, blank=True) 
    cep           = models.CharField(u'CEP', max_length=100, null=True, blank=True) 
    idcidade      = models.IntegerField(u'IDCidade', null=True, blank=True) 
    cidade        = models.CharField(u'Cidade', max_length=60, null=True, blank=True) 
    estado        = models.CharField(u'Estado', max_length=4, null=True, blank=True) 
    telefone      = models.CharField(u'Telefone', max_length=100, null=True, blank=True) 
    e_mail        = models.CharField(u'E-mail', max_length=90, null=True, blank=True) 
    link          = models.CharField(u'Link', max_length=110, null=True, blank=True) 
    banco         = models.CharField(u'Banco', max_length=74, null=True, blank=True) 
    agencia       = models.CharField(u'Agência', max_length=14, null=True, blank=True) 
    conta         = models.CharField(u'Conta', max_length=26, null=True, blank=True) 
    nome          = models.CharField(u'nome', max_length=50, null=True, blank=True) 
    sobrenome     = models.CharField(u'sobrenome', max_length=70, null=True, blank=True) 
    cargo         = models.CharField(u'cargo', max_length=50, null=True, blank=True) 
    contato1      = models.CharField(u'contato1', max_length=100, null=True, blank=True) 
    idsetor       = models.CharField(u'IDSetor', max_length=100, null=True, blank=True) 
    setor         = models.CharField(u'setor', max_length=100, null=True, blank=True) 
    ult_atuali    = models.CharField(u'ult_atuali', max_length=30, null=True, blank=True)

class GetEnt(models.Model):
    """Tabela temporária para armazenar dados de tblEntidades do banco V_GetEntidade97Asp.mdb"""
    entidade      = models.CharField(u'Entidade', max_length=120) 
    nomeguerra    = models.CharField(u'Nome de guerra', max_length=100, null=True, blank=True) 
    cgc           = models.CharField(u'CGC', max_length=36, null=True, blank=True) 
    despesas      = models.CharField(u'Despesas', max_length=100, null=True, blank=True) 
    beneficiados  = models.CharField(u'Beneficiados', max_length=100, null=True, blank=True) 
    voluntarios   = models.CharField(u'Voluntarios', max_length=100, null=True, blank=True) 
    auditores     = models.CharField(u'Auditores', max_length=100, null=True, blank=True) 
    premios       = models.CharField(u'Prêmios', max_length=100, null=True, blank=True) 
    data_cadastro = models.DateTimeField(u'Data do cadastro')

GEOCODE_STATUS = (
    ('OK', 'Georreferenciado com endereço completo'),
    ('ZERO_RESULTS', 'Não foi possível georreferenciar'),
)

class Entidade(models.Model):
    """Entidade."""
    """obs: id corresponde ao colocweb em registros importados."""
    nome_fantasia      = models.CharField(u'Nome Fantasia', max_length=100, null=True, blank=True) 
    razao_social       = models.CharField(u'Razão Social', max_length=120) 
    cnpj               = models.CharField(u'CNPJ', max_length=36, null=True, blank=True) 
    area_atuacao       = models.ForeignKey(AreaAtuacao, verbose_name=u'Área de Atuação', on_delete=models.PROTECT, null=True)
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

    nome_resp          = models.CharField(u'Nome do responsável', max_length=50, null=True, blank=True) 
    sobrenome_resp     = models.CharField(u'Sobrenome do responsável', max_length=70, null=True, blank=True) 
    cargo_resp         = models.CharField(u'Cargo do responsável', max_length=50, null=True, blank=True) 
    nome_contato       = models.CharField(u'Nome da pessoa de contato', max_length=100, null=True, blank=True) 

    banco              = models.CharField(u'Banco', max_length=74, null=True, blank=True) 
    agencia            = models.CharField(u'Agência', max_length=14, null=True, blank=True) 
    conta              = models.CharField(u'Conta', max_length=26, null=True, blank=True) 

    importado          = models.BooleanField(u'Importado da base anterior', default=False) 
    confirmado         = models.BooleanField(u'E-mail confirmado', default=False)
    aprovado           = models.NullBooleanField(u'Cadastro revisado e aprovado')
    data_cadastro      = models.DateTimeField(u'Data de cadastro', auto_now_add=True, null=True, blank=True, db_index=True)
    ultima_atualizacao = models.DateTimeField(u'Última atualização', auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = u'Entidade'
        verbose_name_plural = u'Entidades'
        ordering = ('razao_social',)

    def __str__(self):
        return self.razao_social

    def menor_nome(self):
        '''Retorna o nome fantasia, se houver. Caso contrário retorna a razão social.'''
        if self.nome_fantasia:
            return self.nome_fantasia
        return self.razao_social

    def endereco(self):
        '''Retorna logradouro, cidade e estado separados por vírgula'''
        endereco = self.logradouro if self.logradouro else ''
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

    def geocode(self, request=None, verbose=False):
        '''Atribui uma coordenada à entidade a partir de seu endereço usando o serviço do Google'''
        endereco = self.endereco()
        if len(endereco) == 0:
            self.coordenadas = None
            self.save(update_fields=['coordenadas'])
            return 'NO_ADDRESS'

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

                elif status == 'ZERO_RESULTS':

                    self.geocode_status = status
                    self.coordenadas = None
                    self.save(update_fields=['coordenadas', 'geocode_status'])

            if 'error_message' in j:

                notify_support(u'Erro de geocode', u'Entidade: ' + str(self.id) + "\n" + u'Endereço: ' + endereco + "\n" + u'Erro: ' + j['error_message'], request)

            else:

                notify_support(u'Surpresa no geocode', u'Entidade: ' + str(self.id) + "\n" + u'Endereço: ' + endereco + "\n" + u'Response: ' + str(j), request)

            if verbose:
                print(endereco + ': ' + str(j))

        return status

class Necessidade(models.Model):
    """Necessidade de bem/serviço por parte de uma entidade"""
    entidade         = models.ForeignKey(Entidade, on_delete=models.CASCADE, null=True)
    id_ong           = models.IntegerField(u'IDOng') 
    qtde_orig        = models.CharField(u'Quantidade', max_length=510, null=True, blank=True) 
    descricao        = models.CharField(u'Descrição', max_length=510, null=True, blank=True) 
    valor_orig       = models.CharField(u'Valor', max_length=510, null=True, blank=True) 
    data_solicitacao = models.DateTimeField(u'Data da solicitação', auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.qtde_orig + u' ' + self.descricao
