import os, codecs, re
from csv import reader
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vol.models import AreaTrabalho, AreaAtuacao, Voluntario, GetEnt, EntNec, Entidade, Necessidade, AreaInteresse

class Command(BaseCommand):
    help = u"Importa dados iniciais a partir de arquivos exportados dos bancos MS Access antigos."
    usage_str = "Uso: ./manage.py load_data -d diretorio"

    def add_arguments(self, parser):

        # Named (optional) arguments
        parser.add_argument(
            '-d',
            '--dir',
            dest='diretorio',
            help='Diretório onde estão os arquivos',
        )

    @transaction.atomic
    def handle(self, *args, **options):

        if options['diretorio'] in [None, '']:
            raise CommandError('Especifique um diretório!')

        if not os.path.exists(options['diretorio']):
            raise CommandError('Diretório inexistente!')

        # Área de trabalho
        importar_area_trabalho = AreaTrabalho.objects.all().count() == 0

        if importar_area_trabalho:

            self.stdout.write('Importando áreas de trabalho')
            self.stdout.write('----------------------------')

            nome_arquivo = 'tblAreaTrabalho.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            lines = f.readlines()
            for line in lines:
                val = line.split(',')
                if len(val) != 2:
                    continue
                nome = val[1].strip("\" \r\n")
                if nome in ['AreaTrabalho', '-', 'Não cadastrado']:
                    continue
                id_rec = int(val[0].strip("\" "))
                print(id_rec, nome)
                area = AreaTrabalho(id=id_rec, nome=nome)
                area.save()

            f.close()

        # Área de atuação
        importar_area_atuacao = AreaAtuacao.objects.all().count() == 0

        if importar_area_atuacao:

            self.stdout.write('Importando áreas de atuação')
            self.stdout.write('---------------------------')
            
            nome_arquivo = 'tblAreaAtuacao.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            lines = f.readlines()
            for line in lines:
                val = line.split(',')
                if len(val) != 4:
                    continue
                indice    = val[0].strip("\" ")
                categoria = val[1].strip("\" ")
                nome      = val[2].strip("\" ")
                id_antigo = val[3].strip("\" \r\n")
                if nome in ['AreaAtuacao', '-', 'Não Cadastrado']:
                    continue
                print(indice, categoria, nome)
                area = AreaAtuacao(indice=indice, categoria=categoria, nome=nome, id_antigo=id_antigo)
                area.save()

            f.close()

        # Voluntários
        importar_voluntarios = Voluntario.objects.all().count() == 0

        if importar_voluntarios:

            self.stdout.write('Importando voluntários')
            self.stdout.write('----------------------')
            
            nome_arquivo = 'tblVoluntarios.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            i = {}
            n = 1
            tz = datetime.timezone(-datetime.timedelta(hours=3))
            for line in reader(f):
                if n % 1000 == 0:
                    self.stdout.write(self.style.SUCCESS(str(n) + '...'))
                
                if n == 1:
                    j = 0
                    for field in line:
                        i[field] = j
                        j = j + 1
                    n = 2
                    continue
                if len(line) != 21:
                    continue
                n = n + 1
                id_vol              = int(line[i['IDVoluntario']])
                id_area_atuacao     = line[i['IDAreaAtuacao']]
                try:
                    area_interesse = AreaAtuacao.objects.get(id_antigo=id_area_atuacao)
                except:
                    area_interesse = None
                id_area_trabalho    = line[i['IDAreaTrabalho']]
                try:
                    area_trabalho = AreaTrabalho.objects.get(pk=id_area_trabalho)
                except:
                    area_trabalho = None
                nome                  = line[i['Nome']].strip()
                profissao             = line[i['Profissao']].strip()
                email                 = line[i['Email']].strip().lower()
                ddd                   = line[i['DDD']].strip()
                telefone              = line[i['Telefone']].strip()
                cidade                = line[i['IDCidade']]
                estado                = line[i['IDEstado']]
                empresa               = line[i['Empresa']].strip()
                foi_voluntario        = line[i['FoiVoluntario']] == '1'
                entidade_que_ajudou   = line[i['EntidadeQueAjudou']]
                descricao             = line[i['Descricao']].strip()
                newsletter            = line[i['NewsLetter']] == '1'
                fonte                 = line[i['Fonte']].strip()
                site                  = line[i['Site']] == '1'
                tipo_profissao        = line[i['TipoProfissao']] == '1'
                tipo_area             = line[i['TipoArea']] == '1'
                data_cadastro         = datetime.datetime.strptime(line[i['DataCadastro']], '%m/%d/%y %H:%M:%S')
                data_cadastro = data_cadastro.replace(tzinfo=tz)
                data_aniversario_orig = line[i['DataAniversario']]
                try:
                    data_aniversario = datetime.datetime.strptime(data_aniversario_orig, '%d/%m/%Y').date()
                except:
                    data_aniversario = None

                novo = False

                # Pode ter duplicidade só pra ter especificado áreas de interesse diferentes
                vols = Voluntario.objects.filter(email=email)

                if vols.count() > 0:

                    try:

                        # Faz a busca mais pesada
                        voluntario = Voluntario.objects.get(nome=nome, profissao=profissao, email=email, ddd=ddd, telefone=telefone, cidade=cidade, estado=estado, empresa=empresa, foi_voluntario=foi_voluntario, entidade_que_ajudou=entidade_que_ajudou, descricao=descricao, data_aniversario_orig=data_aniversario_orig, area_trabalho=area_trabalho)
                    except Voluntario.DoesNotExist:

                        novo = True
                    
                else:
                    
                    novo = True

                if novo:
                    
                    voluntario = Voluntario(id=id_vol, area_trabalho=area_trabalho, nome=nome, profissao=profissao, email=email, ddd=ddd, telefone=telefone, cidade=cidade, estado=estado, empresa=empresa, foi_voluntario=foi_voluntario, entidade_que_ajudou=entidade_que_ajudou, descricao=descricao, newsletter=newsletter, fonte=fonte, site=site, data_cadastro=data_cadastro, data_aniversario_orig = data_aniversario_orig, data_aniversario=data_aniversario, importado=True, confirmado=True, aprovado=True)

                    # Evita auto_now_add durante importação
                    for field in voluntario._meta.fields:
                        if field.name == 'data_cadastro':
                            field.auto_now_add = False

                    voluntario.save()
                    
                if area_interesse is not None:

                    try:
                        # Evita duplicidades
                        ai = AreaInteresse.objects.get(voluntario=voluntario, area_atuacao=area_interesse)
                    except AreaInteresse.DoesNotExist:
                        ai = AreaInteresse(voluntario=voluntario, area_atuacao=area_interesse)
                        ai.save()

            f.close()

        # GetEnt
        importar_getent = GetEnt.objects.all().count() == 0

        if importar_getent:

            self.stdout.write('Importando GetEnt')
            self.stdout.write('-----------------')
            
            nome_arquivo = 'tblEntidades-getent.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            i = {}
            n = 1
            tz = datetime.timezone(-datetime.timedelta(hours=3))
            for line in reader(f):
                if n == 1:
                    j = 0
                    for field in line:
                        i[field] = j
                        j = j + 1
                    n = 2
                    continue
                n = n + 1
                nomeguerra    = line[i['Nomeguerra']].strip()
                entidade      = line[i['Entidade']].strip()
                cgc           = line[i['cgc']].strip()
                despesas      = line[i['Despesas']].strip()
                beneficiados  = line[i['Beneficiados']].strip()
                voluntarios   = line[i['Voluntarios']].strip()
                auditores     = line[i['Auditores']].strip()
                premios       = line[i['Premios']].strip()
                data_cadastro = datetime.datetime.strptime(line[i['DataCadastro']], '%m/%d/%y %H:%M:%S')
                data_cadastro = data_cadastro.replace(tzinfo=tz)

                getent = GetEnt(entidade=entidade, nomeguerra=nomeguerra, cgc=cgc, despesas=despesas, beneficiados=beneficiados, voluntarios=voluntarios, auditores=auditores, premios=premios, data_cadastro=data_cadastro)

                getent.save()

            f.close()

        # EntNec
        importar_entnec = EntNec.objects.all().count() == 0

        now = datetime.datetime.now()

        if importar_entnec:

            self.stdout.write('Importando EntNec')
            self.stdout.write('-----------------')
            
            nome_arquivo = 'tblEntidades-entnec.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            i = {}
            n = 1
            tz = datetime.timezone(-datetime.timedelta(hours=3))
            for line in reader(f):
                if n == 1:
                    j = 0
                    for field in line:
                        i[field] = j
                        j = j + 1
                    n = 2
                    continue
                n = n + 1
                nomeguerra = line[i['Nomeguerra']].strip()
                entidade   = line[i['Entidade']].strip()
                cgc        = line[i['cgc']].strip()
                colocweb   = int(line[i['colocweb']].strip())
                mantenedor = line[i['mantenedor']].strip()
                reg_cnas   = line[i['reg_cnas']].strip()
                try:
                    fundacao = datetime.datetime.strptime(line[i['fundacao']], '%m/%d/%y %H:%M:%S')
                    fundacao = fundacao.replace(tzinfo=tz)

                    if fundacao.year >= now.year:
                        fundacao = fundacao.replace(year=fundacao.year-100)
                    
                except:
                    fundacao = None
                sede       = int(line[i['sede']].strip())
                endrec1    = line[i['endrec1']].strip()
                bairro     = line[i['bairro']].strip()
                cep        = line[i['cep']].strip()
                idcidade   = int(line[i['IDCidade']].strip())
                cidade     = line[i['cidade']].strip()
                estado     = line[i['estado']].strip()
                telefone   = line[i['telefone']].strip()
                e_mail     = line[i['e_mail']].strip()
                link       = line[i['link']].strip()
                banco      = line[i['banco']].strip()
                agencia    = line[i['agencia']].strip()
                conta      = line[i['conta']].strip()
                nome       = line[i['nome']].strip()
                sobrenome  = line[i['sobrenome']].strip()
                cargo      = line[i['cargo']].strip()
                contato1   = line[i['contato1']].strip()
                idsetor    = line[i['IDSetor']].strip()
                if idsetor == '':
                    idsetor = None
                else:
                    idsetor = int(idsetor)
                setor      = line[i['setor']].strip()
                ult_atuali = line[i['ult_atuali']].strip()

                entnec = EntNec(entidade=entidade, nomeguerra=nomeguerra, cgc=cgc, colocweb=colocweb, mantenedor=mantenedor, reg_cnas=reg_cnas, fundacao=fundacao, sede=sede, endrec1=endrec1, bairro=bairro, cep=cep, idcidade=idcidade, cidade=cidade, estado=estado, telefone=telefone, e_mail=e_mail, link=link, banco=banco, agencia=agencia, conta=conta, nome=nome, sobrenome=sobrenome, cargo=cargo, contato1=contato1, idsetor=idsetor, setor=setor, ult_atuali=ult_atuali)

                entnec.save()

            f.close()

        # Necessidade
        importar_necessidade = Necessidade.objects.all().count() == 0

        if importar_necessidade:

            self.stdout.write('Importando Necessidade')
            self.stdout.write('----------------------')
            
            nome_arquivo = 'tblNecessidades.csv'
            arquivo = os.path.join(options['diretorio'], nome_arquivo)

            if not os.path.exists(arquivo):
                raise CommandError('Diretório deve conter o arquivo ' + nome_arquivo + '!')

            f = codecs.open(arquivo, 'r', 'utf8')
            i = {}
            n = 1
            num_orfaos = 0
            tz = datetime.timezone(-datetime.timedelta(hours=3))
            for line in reader(f):
                if n == 1:
                    j = 0
                    for field in line:
                        i[field] = j
                        j = j + 1
                    n = 2
                    continue
                n = n + 1
                id_rec = int(float(line[i['IDNecessidade']].strip()))
                id_ong = line[i['IDOng']].strip()
                if id_ong == '':
                    num_orfaos = num_orfaos + 1
                    continue 
                id_ong = int(float(id_ong))
                qtde_orig  = line[i['Quantidade']].strip()
                descricao  = line[i['Descricao']].strip()
                valor_orig = line[i['Valor']].strip()
                try:
                    data_solicitacao = datetime.datetime.strptime(line[i['DataSolicitacao']], '%m/%d/%y %H:%M:%S')
                    data_solicitacao = data_solicitacao.replace(tzinfo=tz)
                except:
                    data_solicitacao = None

                necessidade = Necessidade(id=id_rec, id_ong=id_ong, qtde_orig=qtde_orig, descricao=descricao, valor_orig=valor_orig, data_solicitacao=data_solicitacao)

                # Evita auto_now_add durante importação
                for field in necessidade._meta.fields:
                    if field.name == 'data_solicitacao':
                        field.auto_now_add = False

                necessidade.save()

            f.close()

            if num_orfaos > 0:
                self.stdout.write(self.style.WARNING('Qtde de necessidades sem entidade: ' + str(num_orfaos)))

        # Entidades
        importar_entidade = Entidade.objects.all().count() == 0
        importar_entidade = importar_entidade and EntNec.objects.all().count() > 0
        importar_entidade = importar_entidade and Necessidade.objects.all().count() > 0

        if importar_entidade:

            self.stdout.write('Importando Entidades')
            self.stdout.write('--------------------')

            num_cgc = 0
            num_fantasia = 0
            num_razao = 0

            entnecs = EntNec.objects.all()

            for entnec in entnecs:

                area_atuacao = None

                if len(entnec.setor) > 0 and entnec.setor != '-':
                    
                    try:
                        area_atuacao = AreaAtuacao.objects.get(nome__iexact=entnec.setor.lower())
                    except AreaAtuacao.DoesNotExist:
                        self.stdout.write(self.style.WARNING('Área de atuação não encontrada: ' + entnec.setor))

                nome_resp = entnec.nome + u' ' + entnec.sobrenome

                ult_atuali = None
                if entnec.ult_atuali:
                    ult_atuali = entnec.ult_atuali

                ddd = None
                telefone = None
                m = re.search('\(0xx(\d{2})\)([0-9 ]+)', entnec.telefone)
                if m is not None and len(m.groups()) == 2:
                    ddd = m.group(1)
                    telefone = m.group(2).strip()

                data_fundacao = None
                if entnec.fundacao:
                    data_fundacao = entnec.fundacao.date()

                entidade = Entidade(id=entnec.colocweb, razao_social=entnec.entidade, nome_fantasia=entnec.nomeguerra, cnpj=entnec.cgc, reg_cnas=entnec.reg_cnas, fundacao=data_fundacao, logradouro=entnec.endrec1, bairro=entnec.bairro, cep=entnec.cep, cidade=entnec.cidade, estado=entnec.estado, ddd=ddd, telefone=telefone, email=entnec.e_mail, website=entnec.link, banco=entnec.banco, agencia=entnec.agencia, conta=entnec.conta, nome_resp=entnec.nome, sobrenome_resp=entnec.sobrenome, cargo_resp=entnec.cargo, nome_contato=entnec.contato1, area_atuacao=area_atuacao, ultima_atualizacao=ult_atuali, importado=True, confirmado=True, aprovado=True)

                # Evita auto_now_add/auto_now durante importação
                for field in entidade._meta.fields:
                    if field.name == 'data_cadastro':
                        field.auto_now_add = False
                    elif field.name == 'ultima_atualizacao':
                        field.auto_now = False

                entidade.save()

                Necessidade.objects.filter(id_ong=entnec.colocweb).update(entidade=entidade)

##                 getents = []

##                 # Se tem cnpj e é único
##                 if len(entidade.cnpj) > 0 and Entidade.objects.filter(cnpj=entidade.cnpj).count() == 1:

##                     getents = GetEnt.objects.filter(cgc=entidade.cnpj).order_by('data_cadastro')
##                     if len(getents) > 0:
##                         num_cgc = num_cgc + 1

                # Não podemos confiar em nomes, pois existem entidades homônimas
                # Se tem nomeguerra e é único
##                 if len(getents) == 0 and len(entidade.nome_fantasia) > 0 and Entidade.objects.filter(nome_fantasia__iexact=entidade.nome_fantasia.lower()).count() == 1:

##                     getents = GetEnt.objects.filter(nomeguerra__iexact=entidade.nome_fantasia.lower()).order_by('data_cadastro')
##                     if len(getents) > 0:
##                         num_fantasia = num_fantasia + 1

                # Se tem nome e é único
##                 if len(getents) == 0 and len(entidade.razao_social) > 0 and Entidade.objects.filter(razao_social__iexact=entidade.razao_social.lower()).count() == 1:

##                     getents = GetEnt.objects.filter(entidade__iexact=entidade.razao_social.lower()).order_by('data_cadastro')
##                     if len(getents) > 0:
##                         num_razao = num_razao + 1

##                 if len(getents) > 0:

##                     # Não vamos importar nada desta tabela, exceto data_cadastro
##                     entidade.data_cadastro = getents.first().data_cadastro

##                     ok = False

##                     for getent in getents:
##                         # Só usa valores se ao menos um estiver preenchido
##                         if len(getent.beneficiados) > 0 or len(getent.voluntarios) > 0 or len(getent.premios) > 0 or len(getent.auditores) > 0 or len(getent.despesas) > 0:
##                             ok = True
##                             beneficiados = getent.beneficiados
##                             premios      = getent.premios
##                             despesas     = getent.despesas
##                             voluntarios  = getent.voluntarios
##                             auditores    = getent.auditores
                    
##                     if ok:
##                         # Obs: se houver vários registros, todos eles preenchidos com alguma coisa,
##                         # vamos ficar com os valores do registro mais recente
##                         entidade.beneficiados = beneficiados
##                         entidade.premios      = premios
##                         entidade.despesas     = despesas
##                         entidade.voluntarios  = voluntarios
##                         entidade.auditores    = auditores

##                     entidade.save()

            self.stdout.write(self.style.WARNING('Qtde correspondências CGC: ' + str(num_cgc)))
            self.stdout.write(self.style.WARNING('Qtde correspondências Nome Fantasia: ' + str(num_fantasia)))
            self.stdout.write(self.style.WARNING('Qtde correspondências Razão Social: ' + str(num_razao)))

        self.stdout.write(self.style.SUCCESS('Importação concluída!'))
