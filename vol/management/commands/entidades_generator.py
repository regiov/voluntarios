import random
import string
from random import randint



from django.core.management.base import BaseCommand

from vol.models import *

class Command(BaseCommand):
    help = "Gera uma combinação aleatória de 5 nomes de entidades."

    def handle(self, *args, **options):
        categoria = ('Associação Nacional', 'Federação Nacional', 'Organização Não-Governamental', 'Sociedade Beneficente',  'Fundação', 'União', 'Instituto', 'Entidade')
        nome = ('do Meio Ambiente', 'do Voluntariado', 'da Saúde', 'da Boa Vontade', 'da Preservação da Natureza', 'do Idoso', 'da Informática', 'do Empreendedorismo', 'da Assistência Social', 'do Auxílio Social', 'da Caridade', 'dos Animais', 'do Cuidado aos Animais de Rua', 'do Cuidado aos Moradores de Rua', 'do Auxílio a Famílias Sem Teto', 'de Pequenos Negócios', 'da Segurança Alimentar', 'dos Hospitais', 'do Hospital São Vicente', 'do Hospital Nossa Senhora das Graças', 'do Hospital Conceição', 'da Casa de Acolhimento')
        estados_cidades = {'SP': {'São Paulo': ['Ibirapuera', 'Lapa', 'Mooca'], 'Santos': ['Gonzaga', 'Embaré', 'Aparecida'], 'Araraquara': ['Vila Xavier', 'Centro', 'Gonzaga']}, 'PR': {'Curitiba': ['Xaxim', 'Centro', 'Alto da XV'], 'Londrina': ['Vila Fraternidade', 'Heimtal', 'Parque das Indústrias Leves'], 'Pinhais': ['Vargem Grande', 'Jardim Amélia', 'Atuba']}, 'RJ': {'Rio de Janeiro': ['Tijuca', 'Botafogo', 'Campo Grande'], 'Niterói': ['Baldeador', 'Muriqui', 'Santa Rosa'], 'Duque de Caxias': ['Centro', 'Campo Elíseos', 'Barro Branco']}, 'MG': {'Belo Horizonte': ['Padre Eustáquio', 'Buritis', 'Lindéia'], 'Contagem': ['Água Branca', 'Alvorada', 'Beija-flor'], 'Juiz de Fora': ['São Mateus', 'Centro', 'Boa Vista']}, 'ES': {'Vitória': ['Boa Vista', 'Parque Industrial', 'Jardim da Penha'], 'Serra': ['Barcelona', 'Bela Vista', 'Barro Vermelho'], 'Guarapari'  : ['Muquiçaba', 'Nova Guarapari', 'Meaípe']}, 'RS': {'Porto Alegre': ['Belém Novo', 'Belém Velho', 'Boa Vista do Sul'], 'Canoas': ['Centro', 'Marechal Rondon', 'Nossa Senhora das Graças'], 'São Leopoldo': ['São José', 'Feitoria', 'Rio dos Sinos']}, 'SC': {'Florianópolis': ['Centro', 'Capoeira', 'Trindade'], 'Joinville': ['América', 'Atiradores', 'Bucarein'], 'Blumenau': ['Água Verde', 'Boa Vista', 'Bom Retiro']}, 'MS': {'Campo Grande': ['América', 'Guanandi', 'Centenário'], 'Cuiabá': ['Jardim dos Ipês', 'Jardim Passaredo', 'Lagoa Azul'], 'Dourados': ['Campo Belo', 'Altos do Indaiá', 'Jardim Central']}, 'MT': {'Cuiabá': ['Altos do Coxipó', 'Jardim dos Ipês', 'Jardim Passaredo'], 'Sorriso': ['Bela Vista', 'Califórnia', 'Caravágio'], 'Várzea Grande': ['Água Vermelha', 'Água Limpa', '7 de Maio']}, 'GO': {'Goiânia': ['Setor Central', 'Setor Serrinha', 'Setor Jardim América'], 'Anápolis': ['Alvorada', 'Alto da Bela Vista', 'Anexo Bom Sucesso'], 'Trindade': ['Setor Sul', 'Centro', 'Setor Barcelos']}, 'TO': {'Araguaína': ['Parque Bom Viver', 'Ponte', 'Parque Vale Araguaia'], 'Gurupi': ['Alto da Boa Vista', 'Alto dos Buritis', 'Cidade Industrial'], 'Palmas': ['Jardim Taquari', 'Setor Santa Fé', 'Setor União Sul']}, 'BA': {'Salvador': ['Alto da Terezinha', 'Alto do Cabrito', 'Amaralina'], 'Ilhéus': ['Portal', 'São Francisco', 'Centro'], 'Camaçari': ['Abrantes', 'Alto da Cruz', 'Alto Triângulo']}, 'SE': {'Lagarto': ['Cidade Nova', 'Centro', 'Novo Horizonte'], 'Arapiraca': ['Guaribas', 'Eldorados', 'Alto Cruziero'], 'Aracaju': ['Getúlio Vargas', 'Peneira Lobo', 'Centro']}, 'PE': {'Caruaru': ['Caiuca', 'Centenário', 'Centro'], 'Recife': ['Água Fria', 'Centro', 'Arruda'], 'Petrolina': ['Jardim Amazonas', 'Cacheado', 'Terras do Sul']}, 'AL': {'Arapiraca': ['Alto Cruzeiro', 'Centro', 'Bom Sucesso'], 'Maceió': ['Antares', 'Centro', 'Canaã'], 'Penedo': ['Centro', 'Nosso Senhor', 'Santa Cecília']}, 'PB': {'Campina Grande': ['Cruzeiro', 'Três Irmãs', 'Centro'], 'Patos': ['Distrito Industrial', 'Jardim Magnólia', 'Centro'], 'Tavares': ['Boa Esperança', 'Padre Pio', 'Alvorada']}, 'RN': {'Natal': ['Igapó', 'Guararapes', 'Lagoa Azul'], 'Mossoró': ['Santa Felicidade', 'Campina', 'Bairro Alto'], 'Parnamirim': ['Boqueirão', 'Capão', 'Colombo']}, 'CE': {'Fortaleza': ['Centro', 'Alvorada', 'Bom Retiro'], 'Sobral': ['Lusíadas', 'Centro', 'Sítio Cercado'], 'Brejo Santo': ['Lagoa do Mato', 'Araujao', 'São Francisco']}, 'PI': {'Teresina': ['Centro', 'Guarabira', 'Vale'], 'Parnaíba': ['Alto Campo', 'Capão', 'Centro'], 'Floriano': ['Fazenda Norte', 'Centro', 'Esperança']}, 'MA': {'São Luís': ['Centro', 'Bairro da Luz', 'Bairro Industrial'], 'Açailandia': ['Centro', 'Porta', 'São João'], 'Imperatriz': ['Arcanjo Miguel', 'Centro', 'Avenida']}, 'PA': {'Belém': ['Bairro Central', 'Centro', 'Linha Norte'], 'Santarém': ['Centro', 'Batel', 'Campina'], 'Marabá': ['Mercês', 'Carmo', 'Centro']}, 'AM': {'Manaus': ['Rio Claro', 'Rio Negro', 'Centro'], 'Parintins': ['Centro', 'Avenida', 'Alvorada'], 'Manacapuru': ['Distrito dos Guedes', 'Centro', 'Campo Grande']}, 'RR': {'Boa Vista': ['Centro', 'Morro Dourado', 'Lagoa do Mato'], 'Alto Alegre': ['Zona Rural', 'Paisagem Araripe', 'São Francisco'], 'Rorainópolis': ['Sede', 'Vila Velha', 'Vila Nova']}, 'AC': {'Rio Branco': ['Centro', 'Bairro da Passagem', 'Bairro da Liberdade'], 'Cruzeiro do Sul': ['Centro', 'Centro Histórico', 'Vista Alegre'], 'Sena Madureira': ['Boa Vista', 'Nove de Abril', 'Santa Clara']}, 'AP': {'Macapá': ['Roselândia', 'Centro', 'Capão Raso'], 'Santana': ['Vila Independência', 'Colônia', 'Morro do Castelo'], 'Porto Grande': ['Boa Fortuna', 'Bom Pastor', 'Poço Fundo']}, 'RO': {'Porto Velho': ['São Francisco', 'Centro', 'Alto Limoeiro'], 'Ariquemes': ['Itajara', 'Nossa Senhora da Penha', 'Retiro do Muriaé'], 'Vilhena': ['Centro', 'Mercês', 'Hauer']}}
        areas_atuacao = ('Ambientalismo Conservação', 'Conservação de recursos naturais', 'Controle da poluição Proteção de animais', 'Tecnologias alternativas', 'Outros/Ambientalismo', 'Assistência e serviços sociais', 'Assistência a adultos', 'Assistência a crianças', 'Assistência a deficientes', 'Assistência a desastres e catástrofes', 'Assistência a idosos e adultos', 'Assistência a jovens', 'Assistência familiar', 'Assistência material', 'Creches', 'Outros/Assistência', 'Desenvolvimento', 'Aconselhamento vocacional', 'Associações comunitárias', 'Associações de bairro', 'Moradia', 'Produção e comercialização coletiva', 'Profissionalização', 'Outros/Desenvolvimento', 'Direitos Humanos e Cidadania', 'Combate à violência', 'Direitos da mulher', 'Prevenção do crime', 'Promoção da cidadania', 'Proteção ao consumidor', 'Proteção dos direitos civis', 'Reabilitação de infratores e criminosos', 'Serviços jurídicos', 'Outros/Direitos Humanos', 'Educação e pesquisa', 'Associações científicas', 'Cultura', 'Educação', 'Esporte', 'Museus', 'Outros/Educação', 'Saúde', 'Ambulatório', 'Hospital', 'Sanatório', 'Saúde preventiva', 'Serviços médicos de reabilitação', 'Tratamento e Recuperação de Dependentes', 'Outros/Saúde')
        nomes = ('Gabriel', 'João', 'Maria', 'Joana', 'Joaquim', 'Carlos', 'Eduardo', 'Francisco', 'Gabriele', 'Priscila', 'Emannoel', 'Ricardo', 'Leticia', 'Marcos', 'Bruna', 'Miguel', 'Artur', 'Helena', 'Fátima', 'Maria', 'Eliza', 'Luisa', 'Luis', 'Heitor', 'Davi', 'Bernardo', 'Samuel', 'Heloísa', 'Sofia', 'Alice', 'Laura', 'Rafael', 'Lúcia')
        sobrenome = ('Silva', 'Santos', 'Pereira', 'Oliveira', 'Lima', 'Sampaio', 'Souza', 'Silva', 'Leite', 'Tavares', 'Bragança', 'Alves', 'Ribeiro', 'Gomes', 'Moraes', 'Azevedo', 'Almeida', 'Matos', 'Macedo', 'Ribeiro', 'Rocha', 'Siqueira', 'Serra', 'Guimarães', 'Costa', 'Campos', 'Cardoso', 'Teixeira')
        cargo = ('Assistente', 'Analista', 'Supervisor', 'Diretor')
        logradouro = ('Chácara', 'Fazenda', 'Casa', 'Condomínio', 'Prédio', 'Sítio', 'Vila', 'Rua', 'Residencial', 'Alameda')
       
       
        group_nome = []
        for x in range (5):
            nome_entidade = random.choice(categoria)+" "+random.choice(nome)
            group_nome.append(nome_entidade)

        group_estados = []
        for x in range(5):
            estados = random.choice(list(estados_cidades))
            group_estados.append(estados)
            
        group_cidades = []
        for x in range (5):
            cidade = random.choice(list(estados_cidades[group_estados[x]]))
            group_cidades.append(cidade)

        group_bairros = []
        for x in range (5):
            bairros = random.choice(estados_cidades[group_estados[x]][group_cidades[x]])
            group_bairros.append(bairros)

        group_fantasia = []
        for x in range(5):
            length = randint(2, 4)
            random_fantasia = ''.join(random.choices(string.ascii_uppercase, k=length))
            group_fantasia.append(random_fantasia)

        group_atuacao = []
        for x in range(5):
            atuacao = random.choice(areas_atuacao)
            group_atuacao.append(AreaAtuacao.objects.filter(nome=atuacao)[0])

        group_cep = []
        for x in range(5):
            cep = randint(10000000, 99999999)
            group_cep.append(cep)

        group_cnpj = []
        for x in range(5):
            cpnj = randint(10000000000000, 99999999999999)
            group_cnpj.append(cpnj)

        group_volnumatual = []
        for x in range(5):
            numerovol_atual = randint(1, 20)
            group_volnumatual.append(numerovol_atual)

        group_volnumnecessario = []
        for x in range(5):
            numerovol_necessario = randint(8, 30)
            group_volnumnecessario.append(numerovol_necessario)

        group_nomeresponsavel = []
        for x in range(5):
            nome_aleatorio = random.choice(nomes)
            group_nomeresponsavel.append(nome_aleatorio)

        group_sobrenoresponsavel = []
        for x in range(5):
            sobrenome_aleatorio = random.choice(sobrenome)
            group_sobrenoresponsavel.append(sobrenome_aleatorio)

        group_cargo = []
        for x in range(5):
            cargo_aleatorio = random.choice(cargo)
            group_cargo.append(cargo_aleatorio)

        group_logradouro = []
        for x in range(5):
            logradouro_aleatorio = random.choice(logradouro)
            group_logradouro.append(logradouro_aleatorio)

        group_email = []
        for x in range(5):
            length = randint(5, 10)
            email_aleatorio = ''.join(random.choices(string.ascii_letters, k=length))
            group_email.append(email_aleatorio + '@gmail.com')

        for x in range(5):
            entidade = Entidade(razao_social=group_nome[x], estado=group_estados[x], cidade=group_cidades[x], bairro=group_bairros[x], nome_fantasia=group_fantasia[x], cep=group_cep[x], area_atuacao=group_atuacao[x], cnpj=group_cnpj[x], num_vol=group_volnumatual[x], num_vol_ano=group_volnumnecessario[x], nome_resp=group_nomeresponsavel[x], sobrenome_resp=group_sobrenoresponsavel[x], cargo_resp=group_cargo[x], logradouro=group_logradouro[x])
            entidade.save()
