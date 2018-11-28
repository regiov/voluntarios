# coding=UTF-8

def my_user_signed_up(request, user, **kwargs):
    fields = ['is_active']
    # Ativa usuário que acaba de se registrar, do contrário
    # será exibida tela de usuário inativo
    user.is_active = True
    if 'link' in request.session:
        # Armazena origem do cadastro, para posteriormente
        # direcionar usuário corretamente após login
        user.link = request.session['link']
        fields.append('link')
    user.save(update_fields=fields)
