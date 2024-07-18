// Connect to the Socket.IO server
var socket = io();

// Listen for updates from the server
socket.on('update_interfaces', function(data) {
    var interfaces = data.interfaces;

    // Update interface list in the main content
    var list = document.getElementById('interface-list');
    if (list) {
        list.innerHTML = '';
        interfaces.forEach(function(interface) {
            var li = document.createElement('li');
            li.innerHTML = '<a href="/' + interface.interface_type.toLowerCase() + '/' + interface.name + '">' + interface.interface_type + ' - ' + interface.name + '</a>';
            list.appendChild(li);
        });
    }

    // Update the dropdown menu in the navbar
    var dropdowns = document.querySelectorAll('.nav-item.dropdown');
    dropdowns.forEach(function(dropdown) {
        var dropdownMenu = dropdown.querySelector('.dropdown-menu');
        var technology = dropdown.querySelector('.nav-link').innerText.trim();
        dropdownMenu.innerHTML = '';
        interfaces.forEach(function(interface) {
            if (interface.interface_type === technology) {
                var a = document.createElement('a');
                a.className = 'dropdown-item';
                a.href = '/' + interface.interface_type.toLowerCase() + '/' + interface.name;
                a.innerText = interface.name;
                dropdownMenu.appendChild(a);
            }
        });
    });
});
