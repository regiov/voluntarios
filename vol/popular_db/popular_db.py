import random
from website.wsgi import *
from vol.models import *
from django.db.utils import IntegrityError
from allauth.account.models import EmailAddress
import csv


def salvar_usuario_com_email(usuario: Usuario, mail: EmailAddress):
    """Salva um usuário já com o email"""
    try:
        usuario.set_password(usuario.password)
        usuario.save()
        mail.save()
    except IntegrityError:
        pass


def salvar_voluntario_com_interesses(vol: Voluntario, interesses):
    """Cadastra todos os usuários como voluntários"""
    try:
        vol.save()
        for ai in interesses:
            aa = AreaAtuacao.objects.filter(nome=ai)
            if aa:
                AreaInteresse(voluntario=vol, area_atuacao=aa[0]).save()
    except IntegrityError:
        pass


def instanciar_voluntario(usuario: Usuario,
                          data_aniversario,
                          profissao,
                          area_trabalho,
                          ddd,
                          telefone,
                          estado,
                          cidade,
                          empregado,
                          empresa,
                          foi_voluntario,
                          entidade_que_ajudou,
                          descricao,
                          areas_interesse):
    """Instancia um voluntário com suas areas de interesse e os retorna"""
    vol = Voluntario(usuario=usuario,
                     data_aniversario_orig='',
                     data_aniversario=data_aniversario,
                     ciente_autorizacao=True,
                     profissao=profissao,
                     area_trabalho=area_trabalho,
                     ddd=ddd,
                     telefone=telefone,
                     estado=estado,
                     cidade=cidade,
                     empregado=empregado,
                     empresa=empresa,
                     foi_voluntario=foi_voluntario,
                     entidade_que_ajudou=entidade_que_ajudou,
                     descricao=descricao,
                     aprovado=True
                     )
    areas_interesse = areas_interesse.split(', ')
    return vol, areas_interesse


def instanciar_usuario_com_email(email, nome, senha):
    """Instancia um usuário e o seu email"""
    usuario = Usuario(email=email, nome=nome, password=senha, is_active=True)
    mail = EmailAddress(user=usuario, email=usuario.email, verified=True, primary=True)
    return usuario, mail


def rotina_salvar_voluntarios(arquivo='popular_db/voluntarios.csv'):
    """Realiza a rotina de ler o arquivo de voluntários e salvar todos no banco de dados"""
    with open(arquivo, 'r') as dados:
        leitor = csv.reader(dados)
        for i, n in enumerate(leitor):
            if i > 0:
                nome = n[0]
                email = n[1]
                senha = n[2]
                aniversario = n[3]
                ddd = n[4]
                telefone = n[5]
                cidade = n[6]
                estado = n[7]
                tem_area = False
                area = AreaTrabalho.objects.get(nome=n[8])
                if area:
                    tem_area = True
                if not tem_area:
                    area = AreaTrabalho.objects.all()[1]
                profissao = n[9]
                trabalhando = n[10]
                empresa = n[11]
                vol_veterano = n[12]
                instituicao = n[13]
                interesse = n[14]
                descricao = n[15]
                user, mail = instanciar_usuario_com_email(email, nome, senha)
                salvar_usuario_com_email(user, mail)
                vol, areas_interesse = instanciar_voluntario(usuario=user,
                                                             data_aniversario=aniversario,
                                                             profissao=profissao,
                                                             area_trabalho=area,
                                                             ddd=ddd,
                                                             telefone=telefone,
                                                             estado=estado,
                                                             cidade=cidade,
                                                             empregado=trabalhando,
                                                             empresa=empresa,
                                                             foi_voluntario=vol_veterano,
                                                             entidade_que_ajudou=instituicao,
                                                             descricao=descricao,
                                                             areas_interesse=interesse
                                                             )
                salvar_voluntario_com_interesses(vol=vol, interesses=areas_interesse)


def random_user():
    """Retorna um usuário aleatório cadastrado no banco de dados"""
    return random.choice(Usuario.objects.all())


def salvar_entidade(arquivo='popular_db/entidades.csv'):
    """Lê o arquivo de entidades e realiza o processo de salvar no banco de dados"""
    # TODO refatorar
    with open(arquivo, 'r') as ent:
        leitor = csv.reader(ent)
        for i, n in enumerate(leitor):
            if i > 0:
                nome_fantasia = n[0]
                razao_social = n[1]
                cnpj = n[2]
                tem_area_at = False
                area_atuacao = AreaAtuacao.objects.filter(nome=n[3])[0]
                if area_atuacao:
                    tem_area_at = True
                if not tem_area_at:
                    area_atuacao = AreaAtuacao.objects.all()[1]
                descricao = n[4]
                cep = n[5]
                logradouro = n[6]
                bairro = n[7]
                cidade = n[8]
                estado = n[9]
                website = n[10]
                facebook = n[11]
                instagram = n[12]
                telefone = n[13]
                youtube = n[14]
                fundacao = n[15]
                num_vol = n[16]
                num_vol_ano = n[17]
                nome_resp = n[18]
                sobrenome_resp = n[19]
                cargo_resp = n[20]
                nome_contato = n[21]
                num_doacoes = n[22]
                doacoes_str = n[23].split(', ')
                doacoes_lst = []
                for d in doacoes_str:
                    doacoes_lst.append(TipoArtigo.objects.filter(nome=d))
                obs_doacoes = n[24]
                email = n[25]
                ent = Entidade(
                    nome_fantasia=nome_fantasia,
                    razao_social=razao_social,
                    cnpj=cnpj,
                    area_atuacao=area_atuacao,
                    cep=cep,
                    logradouro=logradouro,
                    bairro=bairro,
                    cidade=cidade,
                    estado=estado,
                    website=website,
                    facebook=facebook,
                    instagram=instagram,
                    youtube=youtube,
                    fundacao=fundacao,
                    num_vol=num_vol,
                    num_vol_ano=num_vol_ano,
                    nome_resp=nome_resp,
                    sobrenome_resp=sobrenome_resp,
                    cargo_resp=cargo_resp,
                    nome_contato=nome_contato,
                )
                ent.save()
                mail = Email(entidade=ent,
                             endereco=email,
                             principal=True,
                             confirmado=True)
                mail.save()
                rd_user = random_user()
                vinculo = VinculoEntidade(usuario=rd_user, entidade=ent, confirmado=True)
                vinculo.save()
                ddd, tel = telefone.split()
                cel = Telefone(tipo='2', prefixo=ddd, numero=tel, entidade=ent, confirmado=True, contato=nome_contato)
                cel.save()
                for n in doacoes_lst:
                    artigo = NecessidadeArtigo(entidade=ent, tipoartigo=n[0], resp_cadastro=rd_user)
                    artigo.save()


rotina_salvar_voluntarios()
salvar_entidade()