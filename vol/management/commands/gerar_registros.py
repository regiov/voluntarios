# coding=UTF-8

import random
import string
from datetime import timedelta
from random import randint

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.exceptions import MultipleObjectsReturned

from vol.models import Usuario, Voluntario, Entidade, Telefone, Email, VinculoEntidade, ProcessoSeletivo, Estado, Cidade, MODO_TRABALHO

class Command(BaseCommand):
    help = u"Gera registros fictícios para teste."
    usage_str = "Uso: ./manage.py gerar_registros [--num-voluntarios X] [--num-entidades Y] [--num-vagas Z]"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--num-voluntarios',
            type=int,
            nargs='?',
            default=0,
            help='Número de voluntários fictícios.'
            )
        parser.add_argument(
            '--num-entidades',
            type=int,
            nargs='?',
            default=0,
            help='Número de entidades fictícias.'
            )
        parser.add_argument(
            '--num-vagas',
            type=int,
            nargs='?',
            default=0,
            help='Número de vagas fictícias.'
            )

    def handle(self, *args, **options):
        num_voluntarios = options['num_voluntarios']
        num_entidades = options['num_entidades']
        num_vagas = options['num_vagas']

        if num_voluntarios < 0:
            self.stderr.write("--num-voluntarios deve ser maior ou igual a zero.")
            return
        if num_entidades < 0:
            self.stderr.write("--num-entidades deve ser maior ou igual a zero.")
            return
        if num_vagas < 0:
            self.stderr.write("--num-vagas deve ser maior ou igual a zero.")
            return
        if num_voluntarios + num_entidades + num_vagas == 0:
            self.stderr.write("Nada a ser feito. Especifique pelo menos um valor maior que zero para algum dos parâmetros.")
            return
            
        categoria = ('Associação Nacional', 'Federação Nacional', 'Organização Não-Governamental', 'Sociedade Beneficente',  'Fundação', 'União', 'Instituto', 'Entidade')
        nome = ('do Meio Ambiente', 'do Voluntariado', 'da Saúde', 'da Boa Vontade', 'da Preservação da Natureza', 'do Idoso', 'da Informática', 'do Empreendedorismo', 'da Assistência Social', 'do Auxílio Social', 'da Caridade', 'dos Animais', 'do Cuidado aos Animais de Rua', 'do Cuidado aos Moradores de Rua', 'do Auxílio a Famílias Sem Teto', 'de Pequenos Negócios', 'da Segurança Alimentar', 'dos Hospitais', 'do Hospital São Vicente', 'do Hospital Nossa Senhora das Graças', 'do Hospital Conceição', 'da Casa de Acolhimento')
        estados_cidades_bairros = {'SP': {'São Paulo': ['Ibirapuera', 'Lapa', 'Mooca'], 'Santos': ['Gonzaga', 'Embaré', 'Aparecida'], 'Araraquara': ['Vila Xavier', 'Centro', 'Gonzaga']}, 'PR': {'Curitiba': ['Xaxim', 'Centro', 'Alto da XV'], 'Londrina': ['Vila Fraternidade', 'Heimtal', 'Parque das Indústrias Leves'], 'Pinhais': ['Vargem Grande', 'Jardim Amélia', 'Atuba']}, 'RJ': {'Rio de Janeiro': ['Tijuca', 'Botafogo', 'Campo Grande'], 'Niterói': ['Baldeador', 'Muriqui', 'Santa Rosa'], 'Duque de Caxias': ['Centro', 'Campo Elíseos', 'Barro Branco']}, 'MG': {'Belo Horizonte': ['Padre Eustáquio', 'Buritis', 'Lindéia'], 'Contagem': ['Água Branca', 'Alvorada', 'Beija-flor'], 'Juiz de Fora': ['São Mateus', 'Centro', 'Boa Vista']}, 'ES': {'Vitória': ['Boa Vista', 'Parque Industrial', 'Jardim da Penha'], 'Serra': ['Barcelona', 'Bela Vista', 'Barro Vermelho'], 'Guarapari'  : ['Muquiçaba', 'Nova Guarapari', 'Meaípe']}, 'RS': {'Porto Alegre': ['Belém Novo', 'Belém Velho', 'Boa Vista do Sul'], 'Canoas': ['Centro', 'Marechal Rondon', 'Nossa Senhora das Graças'], 'São Leopoldo': ['São José', 'Feitoria', 'Rio dos Sinos']}, 'SC': {'Florianópolis': ['Centro', 'Capoeira', 'Trindade'], 'Joinville': ['América', 'Atiradores', 'Bucarein'], 'Blumenau': ['Água Verde', 'Boa Vista', 'Bom Retiro']}, 'MS': {'Campo Grande': ['América', 'Guanandi', 'Centenário'], 'Cuiabá': ['Jardim dos Ipês', 'Jardim Passaredo', 'Lagoa Azul'], 'Dourados': ['Campo Belo', 'Altos do Indaiá', 'Jardim Central']}, 'MT': {'Cuiabá': ['Altos do Coxipó', 'Jardim dos Ipês', 'Jardim Passaredo'], 'Sorriso': ['Bela Vista', 'Califórnia', 'Caravágio'], 'Várzea Grande': ['Água Vermelha', 'Água Limpa', '7 de Maio']}, 'GO': {'Goiânia': ['Setor Central', 'Setor Serrinha', 'Setor Jardim América'], 'Anápolis': ['Alvorada', 'Alto da Bela Vista', 'Anexo Bom Sucesso'], 'Trindade': ['Setor Sul', 'Centro', 'Setor Barcelos']}, 'TO': {'Araguaína': ['Parque Bom Viver', 'Ponte', 'Parque Vale Araguaia'], 'Gurupi': ['Alto da Boa Vista', 'Alto dos Buritis', 'Cidade Industrial'], 'Palmas': ['Jardim Taquari', 'Setor Santa Fé', 'Setor União Sul']}, 'BA': {'Salvador': ['Alto da Terezinha', 'Alto do Cabrito', 'Amaralina'], 'Ilhéus': ['Portal', 'São Francisco', 'Centro'], 'Camaçari': ['Abrantes', 'Alto da Cruz', 'Alto Triângulo']}, 'SE': {'Lagarto': ['Cidade Nova', 'Centro', 'Novo Horizonte'], 'Arapiraca': ['Guaribas', 'Eldorados', 'Alto Cruziero'], 'Aracaju': ['Getúlio Vargas', 'Peneira Lobo', 'Centro']}, 'PE': {'Caruaru': ['Caiuca', 'Centenário', 'Centro'], 'Recife': ['Água Fria', 'Centro', 'Arruda'], 'Petrolina': ['Jardim Amazonas', 'Cacheado', 'Terras do Sul']}, 'AL': {'Arapiraca': ['Alto Cruzeiro', 'Centro', 'Bom Sucesso'], 'Maceió': ['Antares', 'Centro', 'Canaã'], 'Penedo': ['Centro', 'Nosso Senhor', 'Santa Cecília']}, 'PB': {'Campina Grande': ['Cruzeiro', 'Três Irmãs', 'Centro'], 'Patos': ['Distrito Industrial', 'Jardim Magnólia', 'Centro'], 'Tavares': ['Boa Esperança', 'Padre Pio', 'Alvorada']}, 'RN': {'Natal': ['Igapó', 'Guararapes', 'Lagoa Azul'], 'Mossoró': ['Santa Felicidade', 'Campina', 'Bairro Alto'], 'Parnamirim': ['Boqueirão', 'Capão', 'Colombo']}, 'CE': {'Fortaleza': ['Centro', 'Alvorada', 'Bom Retiro'], 'Sobral': ['Lusíadas', 'Centro', 'Sítio Cercado'], 'Brejo Santo': ['Lagoa do Mato', 'Araujao', 'São Francisco']}, 'PI': {'Teresina': ['Centro', 'Guarabira', 'Vale'], 'Parnaíba': ['Alto Campo', 'Capão', 'Centro'], 'Floriano': ['Fazenda Norte', 'Centro', 'Esperança']}, 'MA': {'São Luís': ['Centro', 'Bairro da Luz', 'Bairro Industrial'], 'Açailandia': ['Centro', 'Porta', 'São João'], 'Imperatriz': ['Arcanjo Miguel', 'Centro', 'Avenida']}, 'PA': {'Belém': ['Bairro Central', 'Centro', 'Linha Norte'], 'Santarém': ['Centro', 'Batel', 'Campina'], 'Marabá': ['Mercês', 'Carmo', 'Centro']}, 'AM': {'Manaus': ['Rio Claro', 'Rio Negro', 'Centro'], 'Parintins': ['Centro', 'Avenida', 'Alvorada'], 'Manacapuru': ['Distrito dos Guedes', 'Centro', 'Campo Grande']}, 'RR': {'Boa Vista': ['Centro', 'Morro Dourado', 'Lagoa do Mato'], 'Alto Alegre': ['Zona Rural', 'Paisagem Araripe', 'São Francisco'], 'Rorainópolis': ['Sede', 'Vila Velha', 'Vila Nova']}, 'AC': {'Rio Branco': ['Centro', 'Bairro da Passagem', 'Bairro da Liberdade'], 'Cruzeiro do Sul': ['Centro', 'Centro Histórico', 'Vista Alegre'], 'Sena Madureira': ['Boa Vista', 'Nove de Abril', 'Santa Clara']}, 'AP': {'Macapá': ['Roselândia', 'Centro', 'Capão Raso'], 'Santana': ['Vila Independência', 'Colônia', 'Morro do Castelo'], 'Porto Grande': ['Boa Fortuna', 'Bom Pastor', 'Poço Fundo']}, 'RO': {'Porto Velho': ['São Francisco', 'Centro', 'Alto Limoeiro'], 'Ariquemes': ['Itajara', 'Nossa Senhora da Penha', 'Retiro do Muriaé'], 'Vilhena': ['Centro', 'Mercês', 'Hauer']}}
        nomes = ('Gabriel', 'João', 'Maria', 'Joana', 'Joaquim', 'Carlos', 'Eduardo', 'Francisco', 'Gabriele', 'Priscila', 'Emannoel', 'Ricardo', 'Leticia', 'Marcos', 'Bruna', 'Miguel', 'Artur', 'Helena', 'Fátima', 'Maria', 'Eliza', 'Luisa', 'Luis', 'Heitor', 'Davi', 'Bernardo', 'Samuel', 'Heloísa', 'Sofia', 'Alice', 'Laura', 'Rafael', 'Lúcia')
        sobrenome = ('Silva', 'Santos', 'Pereira', 'Oliveira', 'Lima', 'Sampaio', 'Souza', 'Silva', 'Leite', 'Tavares', 'Bragança', 'Alves', 'Ribeiro', 'Gomes', 'Moraes', 'Azevedo', 'Almeida', 'Matos', 'Macedo', 'Ribeiro', 'Rocha', 'Siqueira', 'Serra', 'Guimarães', 'Costa', 'Campos', 'Cardoso', 'Teixeira')
        cargo = ('Assistente', 'Analista', 'Supervisor', 'Diretor')
        logradouro = ('Chácara', 'Fazenda', 'Casa', 'Condomínio', 'Prédio', 'Sítio', 'Vila', 'Rua', 'Residencial', 'Alameda')

        for x in range (num_entidades):

            nome_entidade = random.choice(categoria)+" "+random.choice(nome)
            
            estados = random.choice(list(estados_cidades_bairros))
                
            cidade = random.choice(list(estados_cidades_bairros[estados]))

            bairros = random.choice(estados_cidades_bairros[estados][cidade])

            length = randint(2, 4)
            random_fantasia = ''.join(random.choices(string.ascii_uppercase, k=length))

            atuacao = random.choice(AreaAtuacao.objects.filter())

            cep = randint(10000000, 99999999)

            cnpj = randint(10000000000000, 99999999999999)

            numerovol_atual = randint(1, 20)

            numerovol_necessario = randint(8, 30)
            
            nome_aleatorio = random.choice(nomes)

            sobrenome_aleatorio = random.choice(sobrenome)

            cargo_aleatorio = random.choice(cargo)

            logradouro_aleatorio = random.choice(logradouro)

            ddd = randint(11, 99)

            telefone = randint(900000000, 999999999)

            length = randint(5, 10)
            email_aleatorio = ''.join(random.choices(string.ascii_letters, k=length)) + '@gmail.com'

            nomeCompleto = random.choice(nomes)+" "+random.choice(sobrenome)

            nomeContato = nomeCompleto = random.choice(nomes)+" "+random.choice(sobrenome)

            length_senha = randint(8, 12)
            senha_aleatoria = ''.join(random.choices(string.ascii_letters, k=length_senha)) + str(randint(1, 999))

            entidade = Entidade(
                razao_social=nome_entidade, 
                estado=estados, 
                cidade=cidade, 
                bairro=bairros, 
                nome_fantasia=random_fantasia, 
                cep=cep, 
                area_atuacao=atuacao, 
                cnpj=cnpj, 
                num_vol=numerovol_atual, 
                num_vol_ano=numerovol_necessario, 
                nome_resp=nome_aleatorio, 
                sobrenome_resp=sobrenome_aleatorio, 
                cargo_resp=cargo_aleatorio, 
                logradouro=logradouro_aleatorio,
                aprovado=True
                )
            entidade.save()
            
            tel = Telefone(
                tipo='1', 
                prefixo=ddd, 
                numero=telefone, 
                confirmado=True,
                contato=nomeContato, 
                entidade=entidade
                )
            tel.save()

            email = Email(
                entidade=entidade,
                endereco=email_aleatorio,
                principal=True,
                confirmado=True
                )
            email.save()

            usuario = Usuario(
                email=email_aleatorio, 
                nome=nomeCompleto, 
                password=senha_aleatoria, 
                is_active=True
                )
            usuario.save()

            vinculo = VinculoEntidade(
                entidade=entidade, 
                usuario=usuario, 
                confirmado=True
                )
            vinculo.save()


        for x in range(num_voluntarios):
                
            nome_entidade = random.choice(categoria)+" "+random.choice(nome)
            
            estados = random.choice(list(estados_cidades_bairros))
                
            cidade = random.choice(list(estados_cidades_bairros[estados]))
                  
            bairros = random.choice(estados_cidades_bairros[estados][cidade])

            length = randint(2, 4)
            random_fantasia = ''.join(random.choices(string.ascii_uppercase, k=length))

            cep = randint(10000000, 99999999)

            cnpj = randint(10000000000000, 99999999999999)

            numerovol_atual = randint(1, 20)

            numerovol_necessario = randint(8, 30)
            
            nome_aleatorio = random.choice(nomes)

            sobrenome_aleatorio = random.choice(sobrenome)

            cargo_aleatorio = random.choice(cargo)

            logradouro_aleatorio = random.choice(logradouro)

            length = randint(5, 10)
            email_aleatorio = ''.join(random.choices(string.ascii_letters, k=length)) + '@gmail.com'

            ddd = randint(11, 99)

            telefone = randint(900000000, 999999999)

            length = randint(5, 10)
            email_aleatorio = ''.join(random.choices(string.ascii_letters, k=length)) + '@gmail.com'

            nomeCompleto = random.choice(nomes)+" "+random.choice(sobrenome)

            nomeContato = nomeCompleto = random.choice(nomes)+" "+random.choice(sobrenome)

            length_senha = randint(8, 12)
            senha_aleatoria = ''.join(random.choices(string.ascii_letters, k=length_senha)) + str(randint(1, 999))

            agora = datetime.datetime.now()
            ini = agora - datetime.timedelta(days=80*365)
            fim = agora - datetime.timedelta(days=18*365)
            data = ini + random.random()*(fim-ini)

            usuario = Usuario(
                email=email_aleatorio, 
                nome=nomeCompleto, 
                password=senha_aleatoria, 
                is_active=True
                )
            usuario.save()

            voluntarios = Voluntario(
                usuario=usuario,
                estado=estados, 
                cidade=cidade,
                data_aniversario=data,
                ddd=ddd,
                telefone=telefone,
                aprovado=True
                )
            voluntarios.save()

        if num_vagas > 0:
            entidades = Entidade.objects.prefetch_related('vinculoentidade_set').filter(aprovado=True, vinculoentidade__confirmado=True)
            if entidades.count() == 0:
                self.stderr.write("Nenhuma entidade disponível para criar vagas. Crie entidades antes.")
                return

        profissoes = ['Designer', 'Captador de recursos', 'Digitador', 'Programador', 'Motorista', 'Psicólogo', 'Atendente social']
        agora = timezone.now()
        i = ProcessoSeletivo.objects.all().count() + 1
        for x in range(num_vagas):
            entidade = random.choice(entidades)
            responsavel = entidade.vinculoentidade_set.all()[0].usuario
            profissao = random.choice(profissoes)
            modo = random.choice(MODO_TRABALHO)
            vaga = ProcessoSeletivo(
                entidade=entidade,
                cadastrado_por=responsavel,
                titulo=f'Vaga {i} - {profissao}',
                resumo_entidade=entidade.descricao,
                modo_trabalho=modo[0],
                atividades='Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
                carga_horaria=random.choice(('flexível', 'a combinar', '3as e 6as das 14 às 16h')),
                requisitos=random.choice(('dedicação', 'pontualidade e disciplina', 'grau superior completo', 'ser de fácil relacionamento')),
                inicio_inscricoes=agora
                )
            if modo[0] != 0 and entidade.estado:
                try:
                    estado = Estado.objects.get(sigla=entidade.estado.upper())
                    cidade = Cidade.objects.get(nome__iexact=entidade.cidade.lower())
                    vaga.estado = estado
                    vaga.cidade = cidade
                    if random.randint(0, 1) == 1:
                        vaga.somente_da_cidade = True
                except (Estado.DoesNotExist, Cidade.DoesNotExist, MultipleObjectsReturned) as e:
                    pass
                if random.randint(0, 10) > 4:
                    limite = agora + timedelta(days=random.randint(30, 90))
                    vaga.limite_inscricoes = limite
                    vaga.previsao_resultado = limite + timedelta(days=random.randint(1, 20))
            vaga.save()
            vaga.solicitar_aprovacao()
            vaga.save()
            # Refresca o objeto para evitar erro de transição de status
            vaga = ProcessoSeletivo.objects.get(codigo=vaga.codigo)
            vaga.aprovar_e_publicar()
            vaga.save()
            i = i + 1
            
        print(f'Número de voluntários produzidos: {num_voluntarios}')
        print(f'Número de entidades produzidas: {num_entidades}')
        print(f'Número de vagas produzidas: {num_vagas}')
       
    
