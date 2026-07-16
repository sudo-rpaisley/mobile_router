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

  $('[data-toggle="tooltip"]').tooltip();
});


$(document).ready(function () {
  function updateJobIndicator() {
    $.ajax({
      url: '/jobs/status',
      method: 'GET',
      success: function (resp) {
        const count = resp.running_count || 0;
        $('#job-activity-count').text(count);
        $('#job-activity-indicator').toggleClass('is-active', count > 0);
        $('#job-activity-indicator').attr('title', count > 0 ? `${count} background job(s) running` : 'No background jobs running');
      },
      complete: function () {
        setTimeout(updateJobIndicator, 2000);
      }
    });
  }

  updateJobIndicator();
});
