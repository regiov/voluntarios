# coding=UTF-8

import re

from datetime import date, timedelta

from django import forms
from django.utils.safestring import mark_safe
from django.utils.functional import lazy
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone

from notification.utils import notify_support

from vol.models import AreaTrabalho, AreaAtuacaoHierarquica, Voluntario, Entidade, UFS_SIGLA, AreaInteresse, Telefone, TIPO_TEL, Email, TipoArtigo, TermoAdesao, TIPO_DOC_IDENTIF, ESTADO_CIVIL, Estado, Cidade, ProcessoSeletivo, MODO_TRABALHO, AreaTrabalhoEmProcessoSeletivo

def _limpa_cpf(val, obrigatorio=False):
    if (val is None or len(val) == 0) and obrigatorio:
        raise forms.ValidationError(u'Preenchimento do CPF obrigatório.')

    if val:
        dval = val.replace('-', '').replace('.', '')
        if not dval.isdigit():
            raise forms.ValidationError(u'Formato incorreto do CPF.')
        if len(dval) != 11:
            raise forms.ValidationError(u'Tamanho incorreto do CPF.')
        if dval == dval[0] * 11:
            # 11111111111, 22222222222, etc, passam no teste do dígito mas são inválidos
            raise forms.ValidationError(u'CPF inválido.')

        # Verifica dígitos
        s1 = 0
        for i in range(0, 9):
            s1 = s1 + (10 - i) * int(dval[i])

        d1 = (s1 * 10) % 11
        if d1 > 9:
            d1 = 0

        if str(d1) != dval[9]:
            raise forms.ValidationError(u'Primeiro dígito de verificação do CPF incorreto.')

        s2 = 0
        for i in range(0, 10):
            s2 = s2 + (11 - i) * int(dval[i])

        d2 = (s2 * 10) % 11
        if d2 > 9:
            d2 = 0

        if str(d2) != dval[10]:
            raise forms.ValidationError(u'Segundo dígito de verificação do CPF incorreto.')

    return val

class FormVoluntario(forms.ModelForm):
    "Formulário para cadastro de voluntário"
    data_aniversario = forms.DateField(label=u'Data de nascimento',
                                       widget=forms.SelectDateWidget(
                                           years=[y for y in range(date.today().year - 105, date.today().year - 5)],
                                           empty_label=(u'ano', u'mês', u'dia'),
                                           attrs={'class': 'form-control combo-data'}),
                                       # input_date_formats=['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'],
                                       # initial=date(date.today().year-36, 5, 22),
                                       help_text="",
                                       # Aparentemente não há como exibir os valores de empty_label se o campo é obrigatório,
                                       # portanto deixamos ele opcional e deixamos a verificação de obrigatoriedade para a
                                       # validação customizada em clean_data_aniversario
                                       required=False)
    estado = forms.ChoiceField(label=u'Estado',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[(e.sigla, e.sigla) for e in Estado.objects.all().order_by('sigla')])
    cidade = forms.ChoiceField(label=u'Cidade em que reside',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[]) # definido via init para validação. No form é carregado via ajax.
    profissao = forms.CharField(label=u'Profissão',
                                max_length=100,
                                widget=forms.TextInput(attrs={'class': 'form-control', 'size': 25}),
                                help_text="",
                                required=False)
    empregado = forms.ChoiceField(label=u'Está trabalhando atualmente?',
                                  # A classe list-inline do bootstrap faz com que as opções fiquem alinhadas horizontalmente
                                  widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                  choices=[(True, 'sim'), (False, 'não')],
                                  help_text="",
                                  required=False)
    area_trabalho = forms.ModelChoiceField(label=u'Qual a sua área de trabalho',
                                           empty_label=u'-- Escolha a área de trabalho --',
                                           queryset=AreaTrabalho.objects.all().order_by('nome'),
                                           widget=forms.Select(attrs={'class': 'form-control'}),
                                           help_text="",
                                           required=False)
    ddd = forms.CharField(label=u'Telefone (ddd)',
                          max_length=3,
                          widget=forms.TextInput(attrs={'class': 'form-control', 'size': 4}),
                          help_text="",
                          required=False)
    telefone = forms.CharField(label=u'número',
                               max_length=60,
                               widget=forms.TextInput(attrs={'class': 'form-control', 'size': 25}),
                               help_text="",
                               required=False)
    empresa = forms.CharField(label=u'Empresa/Organização onde trabalha',
                              max_length=60,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 40}),
                              help_text="",
                              required=False)
    foi_voluntario = forms.ChoiceField(label=u'Já fez trabalho voluntário?',
                                       # A classe list-inline do bootstrap alinha as opções horizontalmente
                                       widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                       choices=[(True, 'sim'), (False, 'não')],
                                       help_text="",
                                       required=False)
    entidade_que_ajudou = forms.CharField(label=u'Entidade que ajudou',
                                          max_length=100,
                                          widget=forms.TextInput(attrs={'class': 'form-control', 'size': 40}),
                                          help_text="",
                                          required=False)
    area_interesse = forms.ModelChoiceField(label=u'Área de Interesse',
                                            empty_label=u'-- Escolha a área de atuação --',
                                            queryset=AreaAtuacaoHierarquica.objects.all().order_by('indice'),
                                            widget=forms.Select(attrs={'class': 'form-control'}),
                                            help_text="",
                                            required=False)
    descricao = forms.CharField(label=u'Descrição',
                                max_length=7000,
                                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'cols': 30}),
                                help_text="",
                                required=False)
    ciente_autorizacao = forms.BooleanField(label=u'',
                                            # Acrescenta margem para o label não ficar muito colado
                                            widget=forms.CheckboxInput(attrs={'style': 'margin-right:5px;'}),
                                            help_text="",
                                            required=False)
    invisivel = forms.BooleanField(label=u'',
                                   # Acrescenta margem para o label não ficar muito colado
                                   widget=forms.CheckboxInput(attrs={'style': 'margin-right:5px;'}),
                                   help_text="",
                                   required=False)

    class Meta:
        model = Voluntario
        fields = ("data_aniversario", "estado", "cidade", "profissao", "ddd", "telefone", "empregado",
                  "empresa", "foi_voluntario", "entidade_que_ajudou", "descricao", "area_trabalho",
                  "area_interesse", "ciente_autorizacao", "invisivel")

    def __init__(self, *args, **kwargs):

        super(FormVoluntario, self).__init__(*args, **kwargs)

        estado = self.data.get('estado')
        if estado is None and self.instance:
            estado = self.instance.estado

        if estado:
            # Atualiza opções válidas de cidades de acordo com o estado
            cidades = Cidade.objects.filter(uf=estado).order_by('nome')
            self.fields['cidade'] = forms.ChoiceField(label=u'Cidade em que reside',
                                                      widget=forms.Select(attrs={'class': 'form-control'}),
                                                      choices=[(c.nome, c.nome) for c in cidades])

    def clean_data_aniversario(self):
        val = self.cleaned_data['data_aniversario']
        if not val:
            raise forms.ValidationError(u'É obrigatório informar a data de nascimento.')
        return val

    def clean_profissao(self):
        val = self.cleaned_data['profissao'].strip()
        if val.lower() in ['desempregado', 'desempregada']:
            raise forms.ValidationError(
                u'"Desempregado" não é uma profissão. Exemplos de conteúdo válido: engenheiro, pedreiro, advogado, dona de casa, estudante, etc.')
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
                                    help_text=u'(sigla, apelido)',
                                    widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}))
    razao_social = forms.CharField(label=u'Razão social',
                                   max_length=120,
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}))
    cnpj = forms.CharField(label=u'CNPJ',
                           max_length=36,
                           help_text=u'Exemplo: 99.999.999/9999-99',
                           widget=forms.TextInput(attrs={'class': 'form-control', 'size': 18}))
    area_atuacao = forms.ModelChoiceField(label=u'Área de Atuação',
                                          empty_label=u'-- Escolha a área de atuação --',
                                          queryset=AreaAtuacaoHierarquica.objects.all().order_by('indice'),
                                          widget=forms.Select(attrs={'class': 'form-control'}),
                                          help_text="")
    descricao = forms.CharField(label=u'Descrição',
                                max_length=7000,
                                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'cols': 30}),
                                help_text="objetivo da entidade, tipo de trabalho realizado, quem se beneficia, perfil dos voluntários, etc.",
                                required=False)
    num_vol = forms.CharField(label=u'N° atual de voluntários',
                              max_length=5,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 5}),
                              help_text="")
    num_vol_ano = forms.CharField(label=u'N° de voluntários necessários por ano',
                                  max_length=5,
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'size': 5}),
                                  help_text="")
    nome_resp = forms.CharField(label=u'Primeiro nome',
                                max_length=50,
                                widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                help_text="")
    sobrenome_resp = forms.CharField(label=u'Sobrenome',
                                     max_length=70,
                                     widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                     help_text="")
    cargo_resp = forms.CharField(label=u'Cargo',
                                 max_length=50,
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                 help_text="")
    cep = forms.CharField(label=u'CEP',
                          max_length=10,
                          widget=forms.TextInput(attrs={'class': 'form-control', 'size': 10}))
    logradouro = forms.CharField(label=u'Logradouro',
                                 max_length=100,
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'size': 35}),
                                 error_messages={'invalid': u'Digite o logradouro (rua) onde fica a entidade.'},
                                 help_text="")
    bairro = forms.CharField(label=u'Bairro',
                             max_length=40,
                             widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                             error_messages={'invalid': u'Digite o bairro.'},
                             help_text="")
    estado = forms.ChoiceField(label=u'Estado',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[(e.sigla, e.sigla) for e in Estado.objects.all().order_by('sigla')])
    cidade = forms.ChoiceField(label=u'Cidade',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[]) # definido via init para validação. No form é carregado via ajax.
    nome_contato = forms.CharField(label=u'Falar com',
                                   max_length=100,
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                   help_text="nome da pessoa com quem os voluntários devem falar",
                                   required=False)
    website = forms.CharField(label=u'Website',
                              max_length=110,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                              help_text="",
                              required=False)
    facebook = forms.CharField(label=u'Página no Facebook',
                               max_length=110,
                               widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                               help_text="link para a página",
                               required=False)
    instagram = forms.CharField(label=u'Instagram',
                                max_length=40,
                                widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                help_text="nome da conta",
                                required=False)
    twitter = forms.CharField(label=u'Twitter',
                              max_length=20,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                              help_text="nome da conta",
                              required=False)
    youtube = forms.CharField(label=u'Canal no Youtube',
                              max_length=110,
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                              help_text="link para o canal",
                              required=False)
    doacoes = forms.ModelMultipleChoiceField(label=u'Artigos aceitos como doação',
                                             queryset=TipoArtigo.objects.all().order_by('ordem'),
                                             widget=forms.CheckboxSelectMultiple(),
                                             help_text="",
                                             required=False)
    obs_doacoes = forms.CharField(label=u'Detalhes adicionais sobre as doações',
                                  max_length=7000,
                                  widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}),
                                  help_text="procedimento a ser seguido, horários de atendimento, etc.",
                                  required=False)

    class Meta:
        model = Entidade
        fields = ('nome_fantasia', 'razao_social', 'cnpj', 'area_atuacao', 'descricao', 'num_vol', 'num_vol_ano',
                  'nome_resp', 'sobrenome_resp', 'cargo_resp', 'cep', 'logradouro', 'bairro', 'cidade', 'estado',
                  'nome_contato', 'website', 'facebook', 'instagram', 'twitter', 'youtube', 'doacoes', 'obs_doacoes')

    def __init__(self, *args, **kwargs):

        super(FormEntidade, self).__init__(*args, **kwargs)

        estado = self.data.get('estado')
        if estado is None and self.instance:
            estado = self.instance.estado

        if estado:
            # Atualiza opções válidas de cidades de acordo com o estado
            cidades = Cidade.objects.filter(uf=estado).order_by('nome')
            self.fields['cidade'] = forms.ChoiceField(label=u'Cidade',
                                                      widget=forms.Select(attrs={'class': 'form-control'}),
                                                      choices=[(c.nome, c.nome) for c in cidades])

        if not self.entidade_nova():

            # Eventuais artigos já marcados como aceitos para doação
            self.initial['doacoes'] = list(self.instance.necessidadeartigo_set.all().values_list('tipoartigo_id',
                                                                                                 flat=True))

            # Proibe edição de CNPJ válido de entidades já aprovadas
            if self.instance.cnpj is not None and self.instance.cnpj_valido() and self.instance.aprovado:
                self.fields['cnpj'].widget.attrs['readonly'] = True
                self.fields['cnpj'].help_text = ''

    def entidade_nova(self):
        if self.instance and self.instance.pk:
            return False
        return True

    def clean_cnpj(self):
        instance = getattr(self, 'instance', None)
        # Alteração de entidade existente
        if instance and instance.pk:
            if instance.cnpj and len(instance.cnpj) > 0:
                if instance.cnpj_valido():
                    # Garante que o CNPJ não seja alterado quando já preenchido e válido
                    return instance.cnpj
                else:
                    # Obriga correção do CNPJ
                    raise forms.ValidationError(u'CNPJ incorreto')
        # Cadastro de entidade nova
        else:
            if len(self.cleaned_data['cnpj']) > 0:
                # Verifica o CNPJ caso esteja preenchido
                entidade_tmp = Entidade(cnpj=self.cleaned_data['cnpj'])
                if entidade_tmp.cnpj_valido() == False:
                    raise forms.ValidationError(u'CNPJ incorreto')
                # Verifica se já existe outra entidade com o mesmo CNPJ
                if Entidade.objects.filter(cnpj=self.cleaned_data['cnpj'], aprovado=True).count() > 0:
                    notify_support(u'CNPJ repetido', u'Tentativa de cadastro de entidade com CNPJ existente: ' + self.cleaned_data['cnpj'])
                    raise forms.ValidationError(u'Já existe uma entidade cadastrada com o mesmo CNPJ. Por favor, entre em contato conosco através do e-mail no final da página informando nome e CNPJ da entidade para que possamos avaliar a melhor forma de proceder nesse caso.')
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
                                          widget=forms.Select(attrs={'class': 'form-control combo-area-interesse'}),
                                          help_text="",
                                          required=False)

    class Meta:
        model = AreaInteresse
        fields = ("area_atuacao",)


class ExtendedSignupForm(forms.Form):
    "Formulário com campos adicionais para a página de cadastro de usuário"
    nome = forms.CharField(label=u'Nome completo',
                           max_length=100,
                           error_messages={'invalid': u'Favor digitar nome e sobrenome.'},
                           help_text="(não utilize abreviações)",
                           widget=forms.TextInput(attrs={'class': 'form-control', 'size': 35}))
    aceitacao = forms.BooleanField(label=mark_safe(
        u'Sim, estou de acordo com os <a href="/p/termos-de-uso/" target="_blank">termos de uso</a> e a <a href="/p/politica-de-privacidade/" target="_blank">política de privacidade</a> do site'),
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
            raise forms.ValidationError(
                u'Para se cadastrar é preciso aceitar os termos de uso e a politica de privacidade')
        return aceitou

    def signup(self, request, user):
        user.nome = self.cleaned_data['nome']
        user.save()


class FormTelefone(forms.ModelForm):
    "Formulário para telefone"
    # Atenção, todos os campos são required = False para poder ignorar registros em branco no formulário
    tipo = forms.ChoiceField(label=u'Tipo',
                             choices=TIPO_TEL,
                             initial=u'1',  # celular
                             widget=forms.Select(attrs={'class': 'form-control'}),
                             help_text="",
                             required=False)  # melhor a msg de erro do clean
    prefixo = forms.CharField(label=u'Prefixo',
                              max_length=2,
                              widget=forms.TextInput(attrs={'class': 'form-control input-prefixo', 'size': 2}),
                              help_text="",
                              required=False)  # melhor a msg de erro do clean
    numero = forms.CharField(label=u'Número',
                             max_length=15,
                             widget=forms.TextInput(attrs={'class': 'form-control input-numero', 'size': 10}),
                             help_text="",
                             required=False)  # melhor a msg de erro do clean

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
                                widget=forms.TextInput(attrs={'class': 'form-control input-endereco', 'size': 30}),
                                error_messages={'invalid': u'Digite um e-mail válido.'},
                                required=False)  # melhor a msg de erro do clean)
    principal = forms.BooleanField(label=u'Principal',
                                   initial=True,
                                   widget=forms.CheckboxInput(attrs={'class': 'input-principal'}),
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


class FormOnboarding(forms.Form):
    "Formulário para envio de mensagem de boas vindas às entidades"
    assunto = forms.CharField(label=u'Assunto',
                              widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                              required=False)
    mensagem = forms.CharField(label=u'Mensagem',
                               max_length=7000,
                               widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 20, 'cols': 30}),
                               help_text="",
                               required=False)  # para poder apagar o conteúdo e gerar de novo com outro modelo
    assinatura = forms.CharField(label=u'Nome na assinatura',
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                 required=False)


class FormCriarTermoAdesao(forms.Form):
    "Formulário para cadastro de termo de adesão de voluntário"
    email_voluntarios = forms.CharField(label=u'E-mail do(s) voluntário(s) envolvido(s)',
                                        max_length=100,
                                        widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}),
                                        help_text="Separe por vírgula caso haja mais de um voluntário. Se houver diferença nas atividades, carga horária ou duração do termo, cadastre termos separados para cada um.",
                                        error_messages={'invalid': u'Preencha com ao menos um e-mail de voluntário.'})
    atividades = forms.CharField(label=u'Atividades',
                                 max_length=7000,
                                 widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}))
    carga_horaria = forms.CharField(label=u'Carga horária',
                                    max_length=50,
                                    widget=forms.TextInput(attrs={'class': 'form-control', 'size': 50}),
                                    help_text="(exemplo: X horas ou dias por semana)")
    data_inicio = forms.DateField(label=u'Início',
                                  initial=date.today,
                                  widget=forms.SelectDateWidget(
                                      years=[y for y in range(date.today().year - 10, date.today().year + 10)],
                                      empty_label=(u'ano', u'mês', u'dia'), attrs={'class': 'form-control'}))
    data_fim = forms.DateField(label=u'Término',
                               widget=forms.SelectDateWidget(empty_label=(u'ano', u'mês', u'dia'),
                                                             attrs={'class': 'form-control'}),
                               help_text="(para duração indeterminada, deixe em branco)",
                               required=False)
    condicoes = forms.CharField(label=u'Condições',
                                max_length=7000,
                                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'cols': 30}))
    texto_aceitacao = forms.CharField(label=u'Texto do aceite',
                                      max_length=255,
                                      widget=forms.TextInput(attrs={'class': 'form-control', 'size': 500}))
    # No casos em que a entidade não é formalmente constituída, há a opção de ter ou não um responsável por parte da entidade
    tem_responsavel = forms.ChoiceField(label=u'Você deseja constar no termo como responsável por parte da entidade?',
                                        # A classe list-inline do bootstrap faz com que as opções fiquem alinhadas horizontalmente
                                        widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                        choices=[(True, 'sim'), (False, 'não')],
                                        help_text="Via de regra o termo de adesão é assinado tanto pelo voluntário quanto por um responsável legal por parte da entidade, a não ser que a entidade não seja formalmente constituída, ou seja, não possua CNPJ, situação em que é possível optar por assinar ou não como responsável.",
                                        required=False)
    # Confirmação de que o usuário é responsável legal
    sou_responsavel = forms.ChoiceField(label=u'Você é responsável legal por parte da entidade?',
                                        # A classe list-inline do bootstrap faz com que as opções fiquem alinhadas horizontalmente
                                        widget=forms.RadioSelect(attrs={'class': 'list-inline'}),
                                        choices=[(True, 'sim'), (False, 'não')],
                                        help_text="Para entidades formalmente constituídas (com CNPJ) o termo de adesão deve ser assinado tanto pelo voluntário quanto por um responsável legal por parte da entidade. No momento o sistema requer que a pessoa que esteja cadastrando o termo (você!) seja um dos responsáveis legais da entidade. Portanto se a sua resposta for \"não\", não será possível prosseguir. Entre em contato conosco se esse for o seu caso.",
                                        required=False)

    def clean_email_voluntarios(self):
        # Deixar e-mail em caixa baixa para padronização
        val = self.cleaned_data['email_voluntarios'].lower().replace(' ', '')
        if len(val) == 0:
            raise forms.ValidationError(u'É preciso incluir pelo menos um e-mail de voluntário')
        emails = val.split(',')
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError(
                    u'Erro na validação do e-mail: ' + email + '. Verifique se digitou corretamente.')
        return val

    def clean_data_fim(self):
        inicio = self.cleaned_data['data_inicio']
        fim = self.cleaned_data['data_fim']
        if fim and inicio > fim:
            raise forms.ValidationError(u'A data de término do termo não pode ser menor que a de início!')
        return fim


class FormAssinarTermoAdesaoVol(forms.Form):
    profissao_voluntario = forms.CharField(label=u'Profissão',
                                           max_length=100,
                                           widget=forms.TextInput(attrs={'class': 'form-control', 'size': 25}))
    nacionalidade_voluntario = forms.CharField(label=u'Nacionalidade',
                                               max_length=50,
                                               widget=forms.TextInput(attrs={'class': 'form-control', 'size': 50}))
    tipo_identif_voluntario = forms.ChoiceField(label=u'Identidade',
                                                choices=TIPO_DOC_IDENTIF,
                                                initial=u'RG',
                                                widget=forms.Select(attrs={'class': 'form-control'}))
    identif_voluntario = forms.CharField(label=u'Número',
                                         max_length=20,
                                         widget=forms.TextInput(attrs={'class': 'form-control', 'size': 20}))
    cpf_voluntario = forms.CharField(label=u'CPF',
                                     max_length=20,
                                     widget=forms.TextInput(attrs={'class': 'form-control', 'size': 20}))
    estado_civil_voluntario = forms.ChoiceField(label=u'Estado civil',
                                                choices=ESTADO_CIVIL,
                                                widget=forms.Select(attrs={'class': 'form-control'}))
    endereco_voluntario = forms.CharField(label=u'Endereço',
                                          max_length=7000,
                                          widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}))
    ddd_voluntario = forms.CharField(label=u'Telefone (ddd)',
                                     max_length=2,
                                     widget=forms.TextInput(attrs={'class': 'form-control input-prefixo', 'size': 2}))
    telefone_voluntario = forms.CharField(label=u'Número',
                                          max_length=15,
                                          widget=forms.TextInput(
                                              attrs={'class': 'form-control input-numero', 'size': 10}))
    aceitacao = forms.BooleanField(label=u'',
                                   # Acrescenta margem para o label não ficar muito colado
                                   widget=forms.CheckboxInput(attrs={'style': 'margin-right:5px;'}),
                                   required=False)

    def clean_tipo_identif_voluntario(self):
        val = self.cleaned_data['tipo_identif_voluntario'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o tipo de identidade')
        tipos = []
        for tipo in TIPO_DOC_IDENTIF:
            tipos.append(tipo[0])
        if val not in tipos:
            raise forms.ValidationError(u'Verifique o tipo de identidade')
        return val

    def clean_cpf_voluntario(self):
        val = self.cleaned_data['cpf_voluntario'].strip()
        return _limpa_cpf(val, True)

    def clean_estado_civil_voluntario(self):
        val = self.cleaned_data['estado_civil_voluntario'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o estado civil')
        tipos = []
        for tipo in ESTADO_CIVIL:
            tipos.append(tipo[0])
        if val not in tipos:
            raise forms.ValidationError(u'Estado civil inválido')
        return val

    def clean_ddd_voluntario(self):
        # Pode não haver prefixo (há casos de 0800)
        val = self.cleaned_data['ddd_voluntario'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o prefixo do telefone')
        else:
            if not val.isdigit():
                raise forms.ValidationError(u'Utilize apenas números no prefixo')
            if len(val) != 2:
                raise forms.ValidationError(u'Utilize 2 dígitos no prefixo')
        return val

    def clean_telefone_voluntario(self):
        val = self.cleaned_data['telefone_voluntario'].strip()
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o número do telefone')
        num_digitos = sum(c.isdigit() for c in val)
        if num_digitos < 8:
            raise forms.ValidationError(u'O número do telefone deve conter pelo menos 8 dígitos')
        return val

    def clean_endereco_voluntario(self):
        val = self.cleaned_data['endereco_voluntario']
        if len(val) == 0:
            raise forms.ValidationError(u'Faltou o endereço')
        else:
            if '???' in val:
                raise forms.ValidationError(u'Favor preencher o endereço completo')
        return val

    def clean_aceitacao(self):
        aceitou = self.cleaned_data['aceitacao']
        if not aceitou:
            raise forms.ValidationError(
                u'Para submeter é preciso marcar a opção de aceitação do termo no final do formulário')
        return aceitou

class FormAreaTrabalho(forms.ModelForm):
    "Formulário de áreas de trabalho de voluntários para processo seletivo"
    area_trabalho = forms.ModelChoiceField(label='Área de trabalho do voluntário',
                                           empty_label=u'-- Escolha uma opção --',
                                           queryset=AreaTrabalho.objects.all().order_by('nome'),
                                           widget=forms.Select(attrs={'class': 'form-control combo-area-trabalho'}),
                                           help_text="",
                                           required=False) # deve ser falso para evitar problema com combo extra

    class Meta:
        model = AreaTrabalhoEmProcessoSeletivo
        fields = ("area_trabalho",)

    def disable(self):
        for field_name, field in self.fields.items():
            field.widget.attrs['disabled'] = 'disabled'

class FormProcessoSeletivo(forms.ModelForm):

    class Meta:
        model = ProcessoSeletivo
        fields = ('titulo', 'resumo_entidade', 'modo_trabalho', 'estado', 'cidade',
                  'atividades', 'requisitos', 'carga_horaria', 'inicio_inscricoes',
                  'limite_inscricoes', 'previsao_resultado',)

    titulo = forms.CharField(label=u'Título da vaga',
                             max_length=100,
                             widget=forms.TextInput(attrs={'class': 'form-control', 'size': 30}))
    resumo_entidade = forms.CharField(label=u'Resumo sobre a entidade',
                                      max_length=100,
                                      widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}))
    modo_trabalho = forms.ChoiceField(label=u'Modo de trabalho',
                                      choices=[('', u'-- Escolha uma opção --')] + list(MODO_TRABALHO),
                                      widget=forms.Select(attrs={'class': 'form-control'}))
    estado = forms.ChoiceField(label=u'Estado',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[(e.sigla, e.sigla) for e in Estado.objects.all().order_by('sigla')],
                               required=False)
    cidade = forms.ChoiceField(label=u'Cidade',
                               widget=forms.Select(attrs={'class': 'form-control'}),
                               choices=[], # definido via init para validação. No form é carregado via ajax.
                               required=False,
                               initial='')
    atividades = forms.CharField(label='Atividades a serem realizadas',
                                 widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}))
    requisitos = forms.CharField(label='Pré-requisitos',
                                 widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 30}),
                                 required=False)
    carga_horaria = forms.CharField(label='Dias e horários de execução das atividades',
                                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 1, 'cols': 30}))
    inicio_inscricoes = forms.DateTimeField(label=u'Início das inscrições',
                                  initial=date.today,
                                  widget=forms.SelectDateWidget(
                                      years=[y for y in range(date.today().year, date.today().year + 10)],
                                      empty_label=(u'ano', u'mês', u'dia'), attrs={'class': 'form-control'}))
    limite_inscricoes = forms.DateTimeField(label='Limite para inscrições', initial=date.today,
                                  widget=forms.SelectDateWidget(
                                      years=[y for y in range(date.today().year, date.today().year + 10)],
                                      empty_label=(u'ano', u'mês', u'dia'), attrs={'class': 'form-control'}))
    previsao_resultado = forms.DateTimeField(label='Data prevista para os resultados', initial=date.today,
                                  widget=forms.SelectDateWidget(
                                      years=[y for y in range(date.today().year, date.today().year + 10)],
                                      empty_label=(u'ano', u'mês', u'dia'), attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):

        # Parâmetro customizado
        disabled = False
        if 'disabled' in kwargs:
            disabled = kwargs['disabled']
            # precisa ser removido antes do super para evitar erro
            del kwargs['disabled']

        super(FormProcessoSeletivo, self).__init__(*args, **kwargs)

        estado = self.data.get('estado')
        if estado is None and self.instance and self.instance.estado:
            estado = self.instance.estado.sigla
            self.initial['estado'] = estado

        if estado:
            # Atualiza opções válidas de cidades de acordo com o estado
            cidades = Cidade.objects.filter(uf=estado).order_by('nome')
            self.fields['cidade'] = forms.ChoiceField(label=u'Cidade',
                                                      widget=forms.Select(attrs={'class': 'form-control'}),
                                                      choices=[(c.nome, c.nome) for c in cidades],
                                                      initial='')

        # Exibe campos desabilitados a depender do status
        if disabled or (self.instance and not self.instance.editavel()):
            for field_name, field in self.fields.items():
                if field_name == 'inicio_inscricoes':
                    # Permite edição de início das inscrições caso o processo ainda esteja aguardando publicação
                    if not self.instance.passivel_de_antecipar_inscricoes():
                        # se utilizarmos readonly, combos continuam podendo ser alterados
                        field.widget.attrs['disabled'] = 'disabled'
                elif field_name in ('limite_inscricoes', 'previsao_resultado'):
                    # Permite edição de data limite e previsão de resultado quando o processo se encontra
                    # aberto a inscrições ou mesmo aguardando seleção
                    if not self.instance.passivel_de_estender_inscricoes():
                        # se utilizarmos readonly, combos continuam podendo ser alterados
                        field.widget.attrs['disabled'] = 'disabled'
                else:
                    # se utilizarmos readonly, combos continuam podendo ser alterados
                    field.widget.attrs['disabled'] = 'disabled'

    def clean_estado(self):
        # Como o campo estado não é um ModelChoiceField, transforma a sigla do estado numa instância de Estado
        val = self.cleaned_data['estado']
        if isinstance(val, str):
            try:
                val = Estado.objects.get(sigla=val)
            except Estado.DoesNotExist:
                raise forms.ValidationError(u'Escolha um estado da lista')
        return val

    def clean_cidade(self):
        # Como o campo cidade não é um ModelChoiceField, transforma o nome da cidade numa instância de Cidade
        val = self.cleaned_data['cidade']
        estado = self.clean_estado()
        if isinstance(val, str):
            try:
                val = Cidade.objects.get(uf=estado, nome=val)
            except Cidade.DoesNotExist:
                raise forms.ValidationError(u'Escolha uma cidade da lista')
        return val

    def clean_inicio_inscricoes(self):
        # Garante que a data não esteja no passado em caso de antecipação de inscrições
        val = self.cleaned_data['inicio_inscricoes']
        if self.instance and self.instance.pk and self.instance.passivel_de_antecipar_inscricoes():
            current_tz = timezone.get_current_timezone()
            now = timezone.now().astimezone(current_tz)
            # obs: um processo pode estar aguardando publicação já com a data de início no passado, caso
            # a aprovação do processo tenha demorado ou caso a própria entidade tenha demorado para solicitar
            # aprovação, portanto a validação abaixo só deve ser feita em caso de antecipação de início de
            # inscrições quando a data de início a ser alterada estiver no futuro
            if val and self.instance.inicio_inscricoes > now and val < now:
                raise forms.ValidationError(u'A data de início das inscrições deve ser maior ou igual a data de hoje')
        return val

    def clean_limite_inscricoes(self):
        # Garante que o limite, quando definido, seja sempre maior ou igual ao início
        val = self.cleaned_data['limite_inscricoes']
        if val:
            inicio_inscricoes = self.cleaned_data.get('inicio_inscricoes', None)
            if inicio_inscricoes is None:
                inicio_inscricoes = self.instance.inicio_inscricoes

            if val < inicio_inscricoes:
                raise forms.ValidationError(u'A data limite das inscrições deve ser maior ou igual à data de início das inscrições')
            # Em caso de alteração do limite de inscrições, a nova data não pode estar no passado
            if self.instance and self.instance.pk and self.instance.passivel_de_estender_inscricoes():
                current_tz = timezone.get_current_timezone()
                now = timezone.now().astimezone(current_tz)
                if val:
                    if val < now:
                        raise forms.ValidationError(u'A data limite de inscrições deve ser maior ou igual a hoje')
                    elif val < self.instance.limite_inscricoes and self.instance.passivel_de_estender_inscricoes():
                        raise forms.ValidationError(u'Em respeito aos voluntários que já viram o anúncio porém ainda não se inscreveram, a data limite de inscrições não pode ser antecipada')
        return val

    def clean_previsao_resultado(self):
        # Garante que a previsão de resultado, quando definida, seja sempre maior ou igual ao início e ao limite
        val = self.cleaned_data['previsao_resultado']
        if val:
            # Se o campo estiver desabilitado, não haverá valor em cleaned_data, portanto podemos pegar direto do processo
            inicio_inscricoes = self.cleaned_data.get('inicio_inscricoes', None)
            if inicio_inscricoes is None:
                inicio_inscricoes = self.instance.inicio_inscricoes

            if val < inicio_inscricoes:
                raise forms.ValidationError(u'A data da previsão do resultado deve ser maior ou igual à data de início das inscrições')

            # O campo limite não é obrigatório
            limite_inscricoes = self.cleaned_data.get('limite_inscricoes', None)
            if limite_inscricoes:
                if val < self.cleaned_data['limite_inscricoes']:
                    raise forms.ValidationError(u'A data da previsão do resultado deve ser maior ou igual à data limite das inscrições')

            # Em caso de alteração da previsão do resultado, a nova data não pode estar no passado
            if self.instance and self.instance.pk and self.instance.passivel_de_estender_inscricoes():
                current_tz = timezone.get_current_timezone()
                now = timezone.now().astimezone(current_tz)
                if val and self.instance.previsao_resultado > val.date() and val < now.date():
                    raise forms.ValidationError(u'A data de previsão do resultado deve ser maior ou igual a data de hoje')

        return val
