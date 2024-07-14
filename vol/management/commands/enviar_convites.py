# coding=UTF-8

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.conf import settings

from vol.models import ProcessoSeletivo, ConviteProcessoSeletivo, StatusProcessoSeletivo

from notification.models import Message
from notification.utils import notify_email_msg

class Command(BaseCommand):
    '''Linha de comando para ser colocado para rodar no cron de hora em hora.'''
    help = u"Envia e-mails de convites para participar em processos seletivos."
    usage_str = "Uso: ./manage.py enviar_convites"

    @transaction.atomic
    def handle(self, *args, **options):

        ###################################################
        # Envia convites pendentes para processos seletivos
        ###################################################
        data_ultimo_convite = Max('conviteprocessoseletivo__incluido_em', filter=Q(conviteprocessoseletivo__enviado_em__isnull=True))
        # Seleciona processos em aberto agrupando pela data/hora do último convite cadastrado
        vagas_com_convites_pendentes = ProcessoSeletivo.objects.filter(status=StatusProcessoSeletivo.ABERTO_A_INSCRICOES).annotate(data_ultimo_convite=data_ultimo_convite)

        i = 0

        current_tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(current_tz)

        msg = Message.objects.get(code='CONVITE_VAGA_V1')
        for processo in vagas_com_convites_pendentes:
            if processo.data_ultimo_convite is None:
                continue
            delta = now - processo.data_ultimo_convite
            # Só envia convites 1h depois que o último convite foi cadastrado,
            # para poder enviar vários ao mesmo tempo. O prazo de 1h supõe que
            # o usuário já terminou de cadastrar os convites que queria.
            if delta.total_seconds() < 60*60:
                continue
            self.stdout.write(self.style.NOTICE(processo.titulo + ' (' + str(delta.total_seconds()) + 's)'))
            convidados = []
            # Faz lock nos convites a serem enviados da vaga em questão
            # Obs: O exclude abaixo é para evitar o erro: FOR UPDATE cannot be applied
            # to the nullable side of an outer join
            convites = ConviteProcessoSeletivo.objects.select_related('voluntario', 'voluntario__usuario').filter(processo_seletivo=processo, enviado_em__isnull=True).select_for_update(nowait=True).exclude(voluntario=None).exclude(voluntario__usuario=None)
            with transaction.atomic():
                for convite in convites:
                    if convite.voluntario_id in list(processo.inscricoes().values_list('voluntario_id', flat=True)):
                        # Ignora voluntários que já fizeram inscrição nessa vaga
                        continue
                    convidados.append(convite.voluntario.usuario.email)
                    convite.enviado_em = now
                    convite.save(update_fields=['enviado_em'])
                if len(convidados) > 0:
                    # Ao invés de enviar e-mails individuais (que podem ser muitos) e ultrapassar a
                    # cota máxima de e-mails do provedor, enviamos lotes de e-mails com múltiplos
                    # destinatários no BCC, também não ultrapassando a cota máxima de destinatários
                    # por mensagem.
                    qtde_maxima_destinatarios = settings.EMAIL_MAX_RECIPIENTS - 1
                    for i in range(0, len(convidados), qtde_maxima_destinatarios):
                        chunk_convidados = convidados[i:i + qtde_maxima_destinatarios]
                        notify_email_msg(settings.NOTIFY_USER_FROM,
                                         msg,
                                         context={'codigo_processo': processo.codigo},
                                         content_obj=processo,
                                         bcc=chunk_convidados)
                        i = i + 1

        self.stdout.write(self.style.NOTICE(str(i) + ' lote(s) de convite(s) enviado(s).'))
