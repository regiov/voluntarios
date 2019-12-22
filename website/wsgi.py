# coding=UTF-8

"""
WSGI config for website project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os

em_manutencao = False

def exibe_em_manutencao(environ, start_response):

    wsgi_dir = os.path.dirname(os.path.abspath(__file__))

    template_manut_html = os.path.join(wsgi_dir, '..', 'vol', 'templates', 'em_manutencao.html')

    if os.path.exists(template_manut_html):
        response_headers = [('Content-type','text/html')]
        import codecs
        response = codecs.open(template_manut_html, 'r', 'latin1').read()
    else:
        response_headers = [('Content-type','text/plain')]
        response = u'Site em manutenção... favor recarregar a página dentro de alguns minutos.'
    
    if environ['REQUEST_METHOD'] == 'GET':
        status = '503 Service Unavailable'
    else:
        status = '405 Method Not Allowed'

    start_response(status, response_headers)
    return [response.encode('latin-1')]


if em_manutencao:

    application = exibe_em_manutencao

else:

    from django.core.wsgi import get_wsgi_application
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website.settings")
    application = get_wsgi_application()
