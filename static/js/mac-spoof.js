$(document).ready(function() {
  $('.edit-mac').on('click', function(event) {
    event.preventDefault();
    const iface = $(this).data('interface');
    const current = $(this).data('current');
    const newMac = prompt('Enter new MAC address', current);
    if (newMac && newMac !== current) {
      $.ajax({
        url: '/spoof-mac',
        method: 'POST',
        data: { interface: iface, mac: newMac },
        success: function() {
          location.reload();
        },
        error: function() {
          alert('Failed to update MAC');
        }
      });
    }
  });
});
