$(document).ready(function(){
  $(".dropdown").hover(function(){
      var dropdownMenu = $(this).children(".dropdown-menu");
      if(dropdownMenu.is(":visible")){
          dropdownMenu.parent().toggleClass("open");
      }
  });

  // Prevent dropdown from staying open when a link is clicked
  $(".dropdown .dropdown-menu a").on('click', function(e) {
      e.stopPropagation();
  });

  $('.nav-item.dropdown a').on('click', function(e) {
      e.preventDefault();
      var link = $(this).attr('href');
      window.location.href = link;
  });
});