# coding=UTF-8

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from vol.models import ProcessoSeletivo, StatusProcessoSeletivo, ParticipacaoEmProcessoSeletivo, StatusParticipacaoEmProcessoSeletivo, Entidade

from notification.models import Message
from notification.utils import notify_email_msg

class Command(BaseCommand):
    '''Linha de comando para ser colocado para rodar no cron todos os dias logo após a meia-noite.'''
    help = u"Encerra processos seletivos cujo limite de inscrições já passou mas que ainda se encontram ABERTO_A_INSCRICOES, bem como abre para inscrições processos seletivos cujo início de inscrições já começõu mas que ainda se encontram AGUARDANDO_PUBLICACAO."
    usage_str = "Uso: ./manage.py atualizar_processos_seletivos"

    @transaction.atomic
    def handle(self, *args, **options):

        ########################################################################
        # Encerra processos em aberto cujo limite de inscrições já tenha passado
        ########################################################################
        processos_em_aberto = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES, limite_inscricoes__date__lt=timezone.now().date())

        i = 0

        msg = Message.objects.get(code='AVISO_ENCERRAMENTO_INSCRICOES_SELECAO_V1')
        for processo in processos_em_aberto:
            processo.encerrar_inscricoes()
            processo.save()
            notify_email_msg(processo.cadastrado_por.email,
                             msg,
                             context={'processo': processo},
                             content_obj=processo)
            i = i + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' processo(s) seletivo(s) encerrado(s).'))

        ##########################################################
        # Publica processos após a data de abertura das inscrições
        ##########################################################
        processos_nao_iniciados = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.AGUARDANDO_PUBLICACAO, inicio_inscricoes__date__lte=timezone.now().date())

        i = 0

        msg = Message.objects.get(code='AVISO_INSCRICOES_INICIADAS_SELECAO_V1')
        for processo in processos_nao_iniciados:
            processo.publicar()
            processo.save()
            notify_email_msg(processo.cadastrado_por.email,
                             msg,
                             context={'processo': processo},
                             content_obj=processo)
            i = i + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' processo(s) seletivo(s) iniciado(s).'))

        ###########################################
        # Notifica entidades sobre novas inscrições
        ###########################################
        entidades_com_processos_em_aberto = Entidade.objects.filter(processoseletivo_set__status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES).distinct()

        current_tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(current_tz)

        i = 0

        msg_novas_inscricoes = Message.objects.get(code='AVISO_NOVAS_INSCRICOES_V1')
        for entidade in entidades_com_processos_em_aberto:

            ultimo_aviso = entidade.ultimo_aviso_de_novas_inscricoes()

            if ultimo_aviso is not None:

                delta = now - ultimo_aviso

                if delta.days < 7:
                    # Evitamos notificar novamente entidades que já receberam
                    # essa notificação nos últimos 7 dias
                    continue

            novas_inscricoes = ParticipacaoEmProcessoSeletivo.objects.filter(processo_seletivo__entidade=entidade, processo_seletivo__status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES, status=StatusParticipacaoEmProcessoSeletivo.AGUARDANDO_SELECAO)

            if entidade.ultimo_acesso_proc is not None:
                # Somente inscrições feitas após o último acesso da entidade na
                # interface de processos são contabilizadas aqui
                novas_inscricoes = novas_inscricoes.filter(data_inscricao__gt=entidade.ultimo_acesso_proc)

            if ultimo_aviso is not None:
                # Somente inscrições feitas após a última notificação
                # são contabilizadas aqui
                novas_inscricoes = novas_inscricoes.filter(data_inscricao__gt=ultimo_aviso)

            qtde_novas_inscricoes = novas_inscricoes.count()

            email_para_notificacoes = entidade.email_para_notificacoes()

            if qtde_novas_inscricoes > 0 and email_para_notificacoes:
                notify_email_msg(email_para_notificacoes,
                                 msg_novas_inscricoes,
                                 context={'entidade': entidade,
                                          'link_processos_seletivos_entidade': reverse('processos_seletivos_entidade', kwargs={'id_entidade': entidade.id})},
                                 content_obj=entidade)
                i = i + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' entidade(s) notificada(s) sobre novas inscrições em processos seletivos.'))

        ####################################################################
        # Notifica entidades sobre processos seletivos sem nenhuma inscrição
        ####################################################################
        processos_em_aberto = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES)

        msg_ausencia_inscricoes = Message.objects.get(code='AVISO_AUSENCIA_INSCRICOES_V1')

        now = timezone.now().astimezone(current_tz)

        i = 0

        for processo in processos_em_aberto:

            delta = now - processo.inicio_inscricoes

            intervalo_em_dias = delta.days

            if intervalo_em_dias < 10:
                # Evitamos enviar a notificação antes de 10 dias desde a publicação da vaga
                continue

            if processo.inscricoes_validas().count() == 0:

                ultima_notificacao = processo.ultima_notificacao_sobre_ausencia_de_inscricoes()

                if ultima_notificacao is not None:
                    # Evitamos enviar a mesma notificação outra vez
                    continue

                email_para_notificacoes = processo.entidade.email_para_notificacoes()
                
                notify_email_msg(email_para_notificacoes,
                                 msg_ausencia_inscricoes,
                                 context={'intervalo_em_dias': intervalo_em_dias,
                                          'titulo_vaga': processo.titulo,
                                          'link_vaga': reverse('exibe_processo_seletivo', kwargs={'codigo_processo': processo.codigo}),
                                          'link_busca_voluntarios': reverse('busca_voluntarios')},
                                 content_obj=processo)
                i = i + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' notificações(s) sobre ausência inscrições em processos seletivos.'))

        ############################################################
        # Encerra processos cujas inscrições terminaram há 10 dias
        # (tempo suficiente pra entidade decidir estender o prazo)
        # e que não tiveram nenhuma inscrição.
        ############################################################
        processos_com_limite_aguardando_selecao = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.AGUARDANDO_SELECAO, limite_inscricoes__isnull=False)

        now = timezone.now().astimezone(current_tz)

        i = 0
        j = 0

        for processo in processos_com_limite_aguardando_selecao:

            delta = now - processo.limite_inscricoes

            intervalo_em_dias = delta.days

            if intervalo_em_dias > 10:

                num_inscricoes_validas = processo.inscricoes_validas().count()

                if num_inscricoes_validas == 0:

                    # Não especifica responsável, indicando que foi transição automática
                    processo.concluir()
                    processo.save()
                    i = i + 1
                else:

                    num_selecionados = processo.selecionados().count()
                    num_nao_selecionados = processo.nao_selecionados().count()

                    if num_inscricoes_validas == num_selecionados + num_nao_selecionados:

                        # Não especifica responsável, indicando que foi transição automática
                        processo.concluir()
                        processo.save()
                        j = j + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' processo(s) seletivo(s) concluídos(s) por falta de inscrição.'))
        self.stdout.write(self.style.NOTICE(str(j) + ' processo(s) seletivo(s) concluídos(s) tempo transcorrido após seleção de todos os candidatos.'))
