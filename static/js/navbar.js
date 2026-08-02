$(document).ready(function () {
  $('[data-toggle="tooltip"]').tooltip();

  function closeNavigationDropdowns(exceptToggle) {
    $('[data-navigation-toggle="dropdown"]').each(function () {
      const toggle = $(this);
      if (exceptToggle && toggle.is(exceptToggle)) {
        return;
      }
      toggle.attr('aria-expanded', 'false');
      toggle.closest('.dropdown').removeClass('show');
      toggle.siblings('.dropdown-menu').removeClass('show');
    });
  }

  function openNavigationDropdown(toggle) {
    closeNavigationDropdowns(toggle);
    toggle.attr('aria-expanded', 'true');
    toggle.closest('.dropdown').addClass('show');
    toggle.siblings('.dropdown-menu').addClass('show');
  }

  $(document).on('click', '[data-navigation-toggle="dropdown"]', function (event) {
    event.preventDefault();
    event.stopPropagation();
    const toggle = $(this);
    const isOpen = toggle.attr('aria-expanded') === 'true';
    if (isOpen) {
      closeNavigationDropdowns();
    } else {
      openNavigationDropdown(toggle);
    }
  });

  $(document).on('keydown', '[data-navigation-toggle="dropdown"]', function (event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      const toggle = $(this);
      openNavigationDropdown(toggle);
      toggle.siblings('.dropdown-menu')
        .find('a:visible, button:visible')
        .first()
        .trigger('focus');
    }
  });

  $(document).on('keydown', '.app-navbar .dropdown-menu', function (event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      const toggle = $(this).siblings('[data-navigation-toggle="dropdown"]');
      closeNavigationDropdowns();
      toggle.trigger('focus');
    }
  });

  $(document).on('click', '.app-navbar .dropdown-menu a, .app-navbar .dropdown-menu button', function () {
    closeNavigationDropdowns();
  });

  $(document).on('click', function () {
    closeNavigationDropdowns();
  });

  $('#navbarCollapse').on('hidden.bs.collapse', function () {
    closeNavigationDropdowns();
  });

  function updateJobIndicator() {
    $.ajax({
      url: '/jobs/status',
      method: 'GET',
      success: function (resp) {
        const count = resp.running_count || 0;
        const label = count > 0
          ? `${count} background job(s) running`
          : 'No background jobs running';
        $('#job-activity-count').text(count);
        $('#job-activity-indicator')
          .toggleClass('is-active', count > 0)
          .attr('title', label)
          .attr('aria-label', label);
      },
      complete: function () {
        setTimeout(updateJobIndicator, 2000);
      }
    });
  }

  function updateAlertIndicator() {
    $.ajax({
      url: '/alerts/status',
      method: 'GET',
      success: function (resp) {
        const count = resp.unread_count || 0;
        const label = count > 0
          ? `${count} unread new device alert(s)`
          : 'No unread new device alerts';
        $('#new-device-alert-count').text(count);
        $('#new-device-alert-indicator')
          .toggleClass('has-alerts', count > 0)
          .attr('title', label)
          .attr('aria-label', label);
      },
      complete: function () {
        setTimeout(updateAlertIndicator, 3000);
      }
    });
  }

  updateJobIndicator();
  updateAlertIndicator();
});
