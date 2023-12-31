from django import template

register = template.Library()

@register.filter
def startswith(value, arg):
    '''Usado para saber se uma string começa com determinado conteúdo
    Exemplo: {% if myvar|startswith:"teste" %}sim{% else %}não{% endif %}'''
    return value.startswith(arg)
