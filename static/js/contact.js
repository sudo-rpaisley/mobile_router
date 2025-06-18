$(document).ready(function() {
  $('#contact-form').on('submit', function(e) {
    e.preventDefault();
    $.ajax({
      url: '/submit-contact',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        name: $('#name').val(),
        email: $('#email').val(),
        message: $('#message').val()
      }),
      success: function() {
        $('#contact-response').text('Message sent!');
        $('#contact-form')[0].reset();
      },
      error: function() {
        $('#contact-response').text('Failed to send message');
      }
    });
  });
});
