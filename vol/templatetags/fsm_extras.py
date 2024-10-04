# coding=UTF-8

from django import template

register = template.Library()

@register.simple_tag()
def status_name(class_obj, state_code):
    '''Usado para retornar o nome de um status.
    Recebe como parâmetro a classe que gerencia os nomes/códigos e
    o código em questão que desejamos saber o nome. A classe deve
    possuir um método "nome" para retornar o nome dado um código.
    ex: {% status_name classe codigo_status %}'''
    return class_obj.nome(int(state_code))
