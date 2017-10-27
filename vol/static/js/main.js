jQuery(function($) {'use strict';

    //Responsive Nav
    $('li.dropdown').find('.fa-angle-down').each(function(){
        $(this).on('click', function(){
            if( $(window).width() < 768 ) {
                $(this).parent().next().slideToggle();
            }
            return false;
        });
    });

    // Slider Height (only index page)
    var slideHeight = $(window).height();
    $('#home .carousel-inner .item').css('height',slideHeight);

    $(window).resize(function(){'use strict',
        $('#home .carousel-inner .item').css('height',slideHeight);
    });
});
