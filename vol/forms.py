# coding=UTF-8

import re

from datetime import date, timedelta

from django import forms
from django.utils.safestring import mark_safe

from vol.models import AreaTrabalho, AreaAtuacaoHierarquica, Voluntario, Entidade, UFS_SIGLA, AreaInteresse, Telefone, TIPO_TEL, Email

class FormVoluntario(forms.ModelForm):
    "Formulário para cadastro de voluntário"
    data_aniversario = forms.DateField(label=u'Data de nascimento',
                                       widget=forms.SelectDateWidget(years=[y for y in range(date.today().year-105, date.today().year-5)], empty_label=(u'ano', u'mês', u'dia'), attrs={'class':'form-control'}),
                                       #input_date_formats=['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'],
                                       #initial=date(date.today().year-36, 5, 22),
                                       help_text="",
                                       # Aparentemente não há como exibir os valores de empty_label se o campo é obrigatório,
                                       # portanto deixamos ele opcional e deixamos a verificação de obrigatoriedade para a
                                       # validação customizada em clean_data_aniversario
                                       required=False)
    estado = forms.ChoiceField(label=u'Estado',
                               # Adiciona uma primeira opção vazia
                               choices=tuple([(0, '--')] + UFS_SIGLA),
                               widget=forms.Select(attrs={'class':'form-control'}),
                               help_text="")
    cidade = forms.CharField(label=u'Cidade em que reside',
                             max_length=100,
                             widget=forms.TextInput(attrs={'class':'form-control', 'size':25}),
                             error_messages={'invalid': u'Digite a cidade onde mora.'},
                             help_text="")
    profissao = forms.CharField(label=u'Profissão',
                                max_length=100,
                                widget=forms.TextInput(attrs={'class':'form-control', 'size':25}),
                                help_text="",
                                required=False)
    empregado = forms.ChoiceField(label=u'Está trabalhando atualmente?',
                                  # A classe list-inline do bootstrap faz com que as opções fiquem alinhadas horizontalmente
                                  widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                  choices = [(True, 'sim'), (False, 'não')],
                                  help_text="",
                                  required=False)
    area_trabalho = forms.ModelChoiceField(label=u'Qual a sua área de trabalho',
                                           empty_label=u'-- Escolha a área de trabalho --',
                                           queryset=AreaTrabalho.objects.all().order_by('nome'),
                                           widget=forms.Select(attrs={'class':'form-control'}),
                                           help_text="",
                                           required=False)
    ddd = forms.CharField(label=u'Telefone (ddd)',
                          max_length=3,
                          widget=forms.TextInput(attrs={'class':'form-control', 'size':4}),
                          help_text="",
                          required=False)
    telefone = forms.CharField(label=u'número',
                               max_length=60,
                               widget=forms.TextInput(attrs={'class':'form-control', 'size':25}),
                               help_text="",
                               required=False)
    empresa = forms.CharField(label=u'Empresa/Organização onde trabalha',
                              max_length=60,
                              widget=forms.TextInput(attrs={'class':'form-control', 'size':40}),
                              help_text="",
                              required=False)
    foi_voluntario = forms.ChoiceField(label=u'Já fez trabalho voluntário?',
                                       # A classe list-inline do bootstrap faz com que as opções fiquem alinhadas horizontalmente
                                       widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                       choices = [(True, 'sim'), (False, 'não')],
                                       help_text="",
                                       required=False)
    entidade_que_ajudou = forms.CharField(label=u'Entidade que ajudou',
                                          max_length=100,
                                          widget=forms.TextInput(attrs={'class':'form-control', 'size':40}),
                                          help_text="",
                                          required=False)
    area_interesse = forms.ModelChoiceField(label=u'Área de Interesse',
                                            empty_label=u'-- Escolha a área de atuação --',
                                            queryset=AreaAtuacaoHierarquica.objects.all().order_by('indice'),
                                            widget=forms.Select(attrs={'class':'form-control'}),
                                            help_text="",
                                            required=False)
    descricao = forms.CharField(label=u'Descrição',
                                max_length=7000,
                                widget=forms.Textarea(attrs={'class':'form-control', 'rows':5, 'cols':30}),
                                help_text="",
                                required=False)
    ciente_autorizacao = forms.BooleanField(label=u'',
                                            # Acrescenta margem para o label não ficar muito colado
                                            widget=forms.CheckboxInput(attrs={'style':'margin-right:5px;'}),
                                            help_text="",
                                            required=False)

    class Meta:
        model = Voluntario
        fields = ("data_aniversario", "estado", "cidade", "profissao", "ddd", "telefone", "empregado",
                  "empresa", "foi_voluntario", "entidade_que_ajudou", "descricao", "area_trabalho",
                  "area_interesse", "ciente_autorizacao")

    def clean_data_aniversario(self):
        val = self.cleaned_data['data_aniversario']
        if not val:
            raise forms.ValidationError(u'É obrigatório informar a data de nascimento.')
        return val

    def clean_estado(self):
        val = self.cleaned_data['estado'].strip().upper()
        ufs = dict(UFS_SIGLA)
        if val not in ufs.keys():
            raise forms.ValidationError(u'Faltou selecionar o estado.')
        return val

    def clean_cidade(self):
        return self.cleaned_data['cidade'].strip()

    def clean_profissao(self):
        val = self.cleaned_data['profissao'].strip()
        if val.lower() in ['desempregado', 'desempregada']:
            raise forms.ValidationError(u'"Desempregado" não é uma profissão. Exemplos de conteúdo válido: engenheiro, pedreiro, advogado, dona de casa, estudante, etc.')
        return val

    def clean_ddd(self):
        return self.cleaned_data['ddd'].strip()

    def clean_telefone(self):
        return self.cleaned_data['telefone'].strip()

    def clean_empresa(self):
        return self.cleaned_data['empresa'].strip()

    def clean_entidade_que_ajudou(self):
        return self.cleaned_data['entidade_que_ajudou'].strip()

    def clean_descricao(self):
        return self.cleaned_data['descricao'].strip()

    def clean(self):
        cleaned_data = super(FormVoluntario, self).clean()
        # Se tem erro em algum campo mas não tem erro geral de formulário
        if self.errors and not self.non_field_errors():
            self.add_error(None, u'Por favor, verifique as pendências abaixo')
        return cleaned_data

class FormEntidade(forms.ModelForm):
    "Formulário para cadastro de entidade"
    nome_fantasia = forms.CharField(label=u'Nome fantasia',
                                    max_length=100,
                                    help_text=u'(apelido)',
                                    widget=forms.TextInput(attrs={'class':'form-control', 'size':30}))
    razao_social = forms.CharField(label=u'Razão social',
                                   max_length=120,
                                   widget=forms.TextInput(attrs={'class':'form-control', 'size':30}))
    cnpj = forms.CharField(label=u'CNPJ',
                           max_length=36,
                           help_text=u'Exemplo: 99.999.999/9999-99',
                           widget=forms.TextInput(attrs={'class':'form-control', 'size':18}))
    area_atuacao = forms.ModelChoiceField(label=u'Área de Atuação',
                                          empty_label=u'-- Escolha a área de atuação --',
                                          queryset=AreaAtuacaoHierarquica.objects.all().order_by('indice'),
                                          widget=forms.Select(attrs={'class':'form-control'}),
                                          help_text="")
    descricao = forms.CharField(label=u'Descrição',
                                max_length=7000,
                                widget=forms.Textarea(attrs={'class':'form-control', 'rows':5, 'cols':30}),
                                help_text="objetivo da entidade, tipo de trabalho realizado, quem se beneficia, perfil dos voluntários, etc.",
                                required=False)
    num_vol = forms.CharField(label=u'N° atual de voluntários',
                              max_length=5,
                              widget=forms.TextInput(attrs={'class':'form-control', 'size':5}),
                              help_text="")
    num_vol_ano = forms.CharField(label=u'N° de voluntários necessários por ano',
                                  max_length=5,
                                  widget=forms.TextInput(attrs={'class':'form-control', 'size':5}),
                                  help_text="")
    nome_resp = forms.CharField(label=u'Primeiro nome',
                                max_length=50,
                                widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                                help_text="")
    sobrenome_resp = forms.CharField(label=u'Sobrenome',
                                     max_length=70,
                                     widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                                     help_text="")
    cargo_resp = forms.CharField(label=u'Cargo',
                                 max_length=50,
                                 widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                                 help_text="")
    cep = forms.CharField(label=u'CEP',
                          max_length=10,
                          widget=forms.TextInput(attrs={'class':'form-control', 'size':10}))
    logradouro = forms.CharField(label=u'Logradouro',
                                 max_length=100,
                                 widget=forms.TextInput(attrs={'class':'form-control', 'size':35}),
                                 error_messages={'invalid': u'Digite o logradouro (rua) onde fica a entidade.'},
                                 help_text="")
    bairro = forms.CharField(label=u'Bairro',
                             max_length=40,
                             widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                             error_messages={'invalid': u'Digite o bairro.'},
                             help_text="")
    cidade = forms.CharField(label=u'Cidade',
                             max_length=60,
                             widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                             error_messages={'invalid': u'Digite a cidade.'},
                             help_text="")
    estado = forms.ChoiceField(label=u'Estado',
                               initial=None,
                               choices=UFS_SIGLA,
                               widget=forms.Select(attrs={'class':'form-control'}),
                               help_text="")
    nome_contato = forms.CharField(label=u'Falar com',
                                   max_length=100,
                                   widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                                   help_text="",
                                   required=False)
    website = forms.CharField(label=u'Website',
                              max_length=110,
                              widget=forms.TextInput(attrs={'class':'form-control', 'size':30}),
                              help_text="",
                              required=False)

    class Meta:
        model = Entidade
        fields = ('nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'num_vol', 'num_vol_ano',
                  'nome_resp', 'sobrenome_resp', 'cargo_resp', 'cep', 'logradouro', 'bairro',
                  'cidade', 'estado', 'nome_contato', 'website')

    def __init__(self, *args, **kwargs):

        super(FormEntidade, self).__init__(*args, **kwargs)

        if self.instance and self.instance.pk:

            if self.instance.cnpj is not None and len(self.instance.cnpj) > 0 and self.instance.aprovado:
                self.fields['cnpj'].widget.attrs['readonly'] = True
                self.fields['cnpj'].help_text = ''

    def clean_cnpj(self):
        # Garante que o CNPJ não seja alterado quando já preenchido
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.cnpj and len(instance.cnpj) > 0:
            return instance.cnpj
        return self.cleaned_data['cnpj']

    def clean_num_vol(self):
        val = self.cleaned_data['num_vol'].strip()
        if not val.isdigit():
            raise forms.ValidationError(u'Digite apenas números na quantidade atual de voluntários')
        return val

    def clean_num_vol_ano(self):
        val = self.cleaned_data['num_vol_ano'].strip()
        if not val.isdigit():
            raise forms.ValidationError(u'Digite apenas números na quantidade de voluntários necessária por ano')
        return val

    def clean_estado(self):
        val = self.cleaned_data['estado'].strip().upper()
        ufs = dict(UFS_SIGLA)
        if val not in ufs.keys():
            raise forms.ValidationError(u'Estado inexistente')
        return val

    def clean_cidade(self):
        return self.cleaned_data['cidade'].strip()

    def clean(self):
        cleaned_data = super(FormEntidade, self).clean()
        # Se tem erro em algum campo mas não tem erro geral de formulário
        if self.errors and not self.non_field_errors():
            self.add_error(None, u'Por favor, verifique as pendências abaixo')
        return cleaned_data

class FormAreaInteresse(forms.ModelForm):
    "Formulário de áreas de interesse de voluntário"
    area_atuacao = forms.ModelChoiceField(label=u'Área de Interesse',
                                          empty_label=u'-- Escolha uma opção --',
                                          queryset=AreaAtuacaoHierarquica.objects.all().order_by('indice'),
                                          widget=forms.Select(attrs={'class':'form-control combo-area-interesse'}),
                                          help_text="")

    class Meta:
        model = AreaInteresse
        fields = ("area_atuacao",)

class ExtendedSignupForm(forms.Form):
    "Formulário com campos adicionais para a página de cadastro de usuário"
    nome = forms.CharField(label=u'Nome completo',
                            max_length=100,
                            error_messages={'invalid': u'Favor digitar nome e sobrenome.'},
                            help_text="(não utilize abreviações)",
                            widget=forms.TextInput(attrs={'class':'form-control', 'size':35}))
    aceitacao = forms.BooleanField(label=mark_safe(u'Sim, estou de acordo com os <a href="/p/termos-de-uso/" target="_blank">termos de uso</a> e a <a href="/p/politica-de-privacidade/" target="_blank">política de privacidade</a> do site'),
                                   widget=forms.CheckboxInput(attrs={}),
                                   initial=False)
    field_order = ['nome', 'email', 'password1', 'password2', 'aceitacao']

    def clean_nome(self):
        """
        Garante apenas caracteres alfanuméricos e pelo menos duas palavras.
        Remove espaços no início e no fim.
        Remove espaços seguidos.
        """
        nome = self.cleaned_data['nome'].strip()
        
        nome = re.sub(' +', ' ', nome)
        
        partes = nome.split(' ')
        
        if len(partes) < 2:
            raise forms.ValidationError(u'Favor digitar nome e sobrenome.')

        return nome

    def clean_aceitacao(self):
        aceitou = self.cleaned_data['aceitacao']
        if not aceitou:
            raise forms.ValidationError(u'Para se cadastrar é preciso aceitar os termos de uso e a politica de privacidade')
        return aceitou

    def signup(self, request, user):
        user.nome = self.cleaned_data['nome']
        user.save()

class FormTelefone(forms.ModelForm):
    "Formulário para telefone"
    # Atenção, todos os campos são required = False para poder ignorar registros em branco no formulário
    tipo = forms.ChoiceField(label=u'Tipo',
                             choices=TIPO_TEL,
                             initial=u'1', # celular
                             widget=forms.Select(attrs={'class':'form-control'}),
                             help_text="",
                             required=False) # melhor a msg de erro do clean
    prefixo = forms.CharField(label=u'Prefixo',
                              max_length=2,
                              widget=forms.TextInput(attrs={'class':'form-control input-prefixo', 'size':2}),
                              help_text="",
                              required=False) # melhor a msg de erro do clean
    numero = forms.CharField(label=u'Número',
                             max_length=15,
                             widget=forms.TextInput(attrs={'class':'form-control input-numero', 'size':10}),
                             help_text="",
                             required=False) # melhor a msg de erro do clean

    class Meta:
        model = Telefone
        fields = ('tipo', 'prefixo', 'numero',)

    def clean_tipo(self):
        val = self.cleaned_data['tipo'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o tipo de telefone')
        tipos = []
        for tipo in TIPO_TEL:
            tipos.append(tipo[0])
        if val not in tipos:
            raise forms.ValidationError(u'Verifique o tipo de telefone')
        return val

    def clean_prefixo(self):
        # Pode não haver prefixo (há casos de 0800)
        val = self.cleaned_data['prefixo'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o prefixo do telefone')
        else:
            if not val.isdigit():
                raise forms.ValidationError(u'Utilize apenas números no prefixo')
            if len(val) != 2:
                raise forms.ValidationError(u'Utilize 2 dígitos no prefixo')
        return val

    def clean_numero(self):
        val = self.cleaned_data['numero'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o número do telefone')
        num_digitos = sum(c.isdigit() for c in val)
        if num_digitos < 8:
            raise forms.ValidationError(u'O número do telefone deve conter pelo menos 8 dígitos')
        return val

class FormEmail(forms.ModelForm):
    "Formulário para e-mail"
    # Atenção, todos os campos são required = False para poder ignorar registros em branco no formulário
    endereco = forms.EmailField(label=u'',
                                widget=forms.TextInput(attrs={'class':'form-control input-endereco', 'size':30}),
                                error_messages={'invalid': u'Digite um e-mail válido.'},
                                required=False) # melhor a msg de erro do clean)
    principal = forms.BooleanField(label=u'Principal',
                                   initial=True,
                                   widget=forms.CheckboxInput(attrs={'class':'input-principal'}),
                                   help_text="",
                                   required=False)

    class Meta:
        model = Email
        fields = ('endereco', 'principal',)
        
    def clean_endereco(self):
        # Deixar e-mail em caixa baixa para padronização
        val = self.cleaned_data['endereco'].strip().lower()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o e-mail')
        return val
