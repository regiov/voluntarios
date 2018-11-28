from django import template

register = template.Library()

@register.filter
def htmlattributes(value, arg):
    '''Usado em campos de formulários para adicionar atributos HTML
    Exemplo: {{ form.openid_identifier|htmlattributes:"class : something, id: openid_identifier" }}
    Fonte: https://stackoverflow.com/questions/4951810/django-how-to-add-html-attributes-to-forms-on-templates'''
    attrs = value.field.widget.attrs

    data = arg.replace(' ', '')   

    kvs = data.split(',') 

    for string in kvs:
        kv = string.split(':')
        attrs[kv[0]] = kv[1]

    rendered = str(value)

    return rendered

@register.simple_tag(takes_context=True)
def delsessionkey(context, key):
    '''Usado para remover um item da sessão'''
    request = context['request']
    if key in request.session:
        del request.session[key]
        request.session.modified = True

    return ''
