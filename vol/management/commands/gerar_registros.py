
import random
import string
from random import randint

from django.core.management.base import BaseCommand

from vol.models import *

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('num_voluntarios', type=int, nargs='?', default = 5, help='Número de voluntários a serem inseridos no banco de dados.')
        parser.add_argument('num_entidades', type=int, nargs='?', default = 5, help='Número de entidades a serem inseridas no banco de dados.')

    def handle(self, *args, **options):
        num_voluntarios = options['num_voluntarios']
        num_entidades = options['num_entidades']

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

            entidade = Entidade(razao_social=nome_entidade, 
                        
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
                        
                        logradouro=logradouro_aleatorio)
            entidade.save()
            
            tel = Telefone(tipo='1', 
                        
                        prefixo=ddd, 
                        
                        numero=telefone, 
                        
                        confirmado=True,

                        contato=nomeContato, 
                        
                        entidade=entidade)
            tel.save()

            email = Email(entidade=entidade,
                            
                            endereco=email_aleatorio,
                            
                            principal=True,
                            
                            confirmado=True)
            email.save()

            usuario = Usuario(email=email_aleatorio, 
                            
                            nome=nomeCompleto, 
                            
                            password=senha_aleatoria, 
                            
                            is_active=True)
            usuario.save()

            vinculo = VinculoEntidade(entidade=entidade, 
                                        
                                        usuario=usuario, 
                                        
                                        confirmado=True)
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

            usuario = Usuario(email=email_aleatorio, 
                            
                            nome=nomeCompleto, 
                            
                            password=senha_aleatoria, 
                            
                            is_active=True)
            usuario.save()

            voluntarios = Voluntario(usuario=usuario,
                                    
                                    estado=estados, 
                                    
                                    cidade=cidade,

                                    data_aniversario=data,

                                    ddd=ddd,

                                    telefone=telefone,
            
                                    aprovado=True)
            voluntarios.save()

        print('Número de voluntários adicionados ao banco de dados:' + ' ' + str(num_voluntarios))
        print('Número de entidades adicionadas ao banco de dados:' + ' ' + str(num_entidades))
        
    