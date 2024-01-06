/* Funções para gerenciamento de combos estado/cidade 
   Uso: init_combos_estado_cidade(url_retorna_cidades, inclui_estado_vazio, cidade_default);
   Elementos na página:
   - Combo de estados: #id_estado (valores devem ser as siglas)
   - Combo de cidades: #id_cidade (valores devem ser os nomes)
   - Imagem para indicar atualização da lista de cidades: #id_cidade_loader 
*/

function carrega_cidades(url_retorna_cidades, cidade_default) {
    const estado = $('#id_estado option:selected').val();
    var cidades = $("#id_cidade");
    cidades.empty();
    if (estado.length > 0) {
        $('#id_cidade_loader').show();
        $.ajax({
          url: url_retorna_cidades,
          data: {
            'estado': estado
          },
          success: function (response) {
            cidades.append('<option value=""></option>');
            for (var i = 0; i < response.length; i++) {
                var cidade = response[i];
                var selected = (cidade_default === cidade.nome) ? ' selected=""' : '';
                cidades.append('<option value="' + cidade.nome + '"' + selected + '>' + cidade.nome + '</option>');
            }
            $('#id_cidade_loader').hide();
          },
          error: function (response) {
            $('#id_cidade_loader').hide();
          }
        });
    }
}

function init_combos_estado_cidade(url_retorna_cidades, inclui_estado_vazio, cidade_default) {

    if (inclui_estado_vazio) {
        // Acrescenta opção vazia no combo estado caso não haja nenhuma
        $("#id_estado").prepend('<option value="" selected=""></option>');
    }

    // Inicialização do combo cidades
    if ($('#id_estado option:selected').val() !== '') {
        carrega_cidades(url_retorna_cidades, cidade_default);
    }

    $("#id_estado").change(function () {
        carrega_cidades(url_retorna_cidades, '');
    });
}
