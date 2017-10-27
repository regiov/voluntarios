# coding=UTF-8

from django.conf import settings

from vol.models import Entidade, Necessidade

def general(request):
    # e-mail de contato
    context = dict(EMAIL_CONTATO=settings.NOTIFY_USER_FROM)

    # últimas entidades cadastradas
    query1 = Entidade.objects.filter(confirmado=True)
    if query1.count() > 4:
        entidades_recentes = query1.order_by('-data_cadastro')[:5]
    else:
        entidades_recentes = Entidade.objects.none()
    context['entidades_recentes'] = entidades_recentes

    # últimos pedidos de doações cadastrados
    query2 = Necessidade.objects.filter(entidade__isnull=False, data_solicitacao__isnull=False)
    if query2.count() > 2:
        pedidos_recentes = query2.prefetch_related('entidade').order_by('-data_solicitacao')[:3]
    else:
        pedidos_recentes = Necessidade.objects.none()
    context['pedidos_recentes'] = pedidos_recentes
    
    return context
 
