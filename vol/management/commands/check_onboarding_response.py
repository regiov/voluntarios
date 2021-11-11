# coding=UTF-8

from datetime import timedelta
import imaplib
import email
import re
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from django.utils import timezone

from vol.models import Entidade, Usuario

from notification.models import Message
from notification.utils import notify_user_msg, notify_support

class Command(BaseCommand):
    help = u"Verifica se já chegou alguma resposta de entidade à mensagem de boas vindas."
    usage_str = "Uso: ./manage.py check_onboarding_response"

    @transaction.atomic
    def handle(self, *args, **options):

        entidades_que_nao_responderam = Entidade.objects.filter(data_envio_onboarding__isnull=False, data_ret_envio_onboarding__isnull=True, data_envio_onboarding__gte=timezone.now()-timedelta(days=settings.ONBOARDING_MAX_DAYS_WAITING_RESPONSE))

        qtde_entidades_que_nao_responderam = len(entidades_que_nao_responderam)

        # Se tem pelo menos uma entidade que ainda estamos aguardando resposta
        if qtde_entidades_que_nao_responderam > 0:

            stop = False
            max_tentativas = 1
            tentativa = 0
            qtde_respostas = 0
            qtde_mensagens = 0

            while tentativa <= max_tentativas and not stop:

                tentativa = tentativa + 1

                try:
                    conn = imaplib.IMAP4_SSL(settings.ONBOARDING_IMAP_SERVER)
                    code, data = conn.login(settings.ONBOARDING_EMAIL_HOST_USER, settings.ONBOARDING_EMAIL_HOST_PASSWORD)
                    if code != 'OK':
                        raise RuntimeError('Failed to login: ' + code)
                    code, dummy = conn.select('INBOX', readonly=True)
                    if code != 'OK':
                        raise RuntimeError('Failed to select inbox: ' + code)
                    code, search_data = conn.search(None, 'ALL')
                    if code == 'OK':
                        msgid_list = search_data[0].split()
                    else:
                        raise RuntimeError('Failed to get message IDs')
                    p = re.compile(r'protocolo: oe-([\d]+)[^\d].*')
                    for msgid in msgid_list:
                        qtde_mensagens = qtde_mensagens + 1
                        code, msg_data = conn.fetch(msgid, '(RFC822)')
                        if code == 'OK':
                            msg = email.message_from_string(msg_data[0][1].decode('utf-8', errors='ignore'))
                            for part in msg.walk():
                                body = part.get_payload(decode=True)
                                if body:
                                    match = p.search(body.decode('utf-8', errors='ignore'))
                                    if match:
                                        id_entidade = int(match.group(1))
                                        entidade = Entidade.objects.get(pk=id_entidade)
                                        if entidade.data_ret_envio_onboarding is None:
                                            # Pega a data da mensagem
                                            raw = email.message_from_bytes(msg_data[0][1])
                                            datestring = raw['date']
                                            datetime_obj = email.utils.parsedate_to_datetime(datestring)
                                            entidade.data_ret_envio_onboarding = datetime_obj
                                            entidade.save(update_fields=['data_ret_envio_onboarding'])
                                            # Sinaliza detecção de resposta
                                            qtde_respostas = qtde_respostas + 1
                                        break
                            if qtde_respostas == qtde_entidades_que_nao_responderam:
                                # não processa as outras mensagens caso já tenha detectado
                                # o número máximo de respostas esperadas
                                break
                        else:
                            raise RuntimeError('Failed to fetch message: ' + code)
                    conn.close()
                    conn.logout()
                    stop = True
                except Exception as e:
                    if tentativa == max_tentativas:
                        notify_support(u'Falha na verificação da caixa postal de onboarding', traceback.format_exc())

            self.stdout.write(str(qtde_mensagens) + ' mensagens lidas.')
            self.stdout.write(str(qtde_respostas) + ' respostas detectadas.')

            if qtde_respostas > 0:
                msg = Message.objects.get(code='AVISO_RECEBIMENTO_RESPOSTA_ONBOARDING')
                try:
                    usuario = Usuario.objects.get(email=settings.ONBOARDING_NOTIFY_RESPONSE_ARRIVAL)
                    notify_user_msg(usuario, msg)
                except Usuario.DoesNotExist:
                    notify_support(u'Falha no envio de notificação de chegada de resposta de onboarding', str(e))

