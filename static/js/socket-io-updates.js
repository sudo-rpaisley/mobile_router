// Handle Socket.IO updates from the server
// Reload the page when interface information changes

document.addEventListener('DOMContentLoaded', function() {
    var socket = io();
    socket.on('update_interfaces', function(data) {
        console.log('Interfaces updated', data);
        // Simple approach: reload the page to display new interfaces
        window.location.reload();
    });
});
