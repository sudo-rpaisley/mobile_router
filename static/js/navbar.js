$(document).ready(function () {
  $('[data-toggle="tooltip"]').tooltip();

  const mainContent = document.getElementById('main-content') || document.querySelector('main');
  if (mainContent && !mainContent.id) {
    mainContent.id = 'main-content';
    mainContent.setAttribute('tabindex', '-1');
  }

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

  $(document).on('click', '.app-navbar .dropdown-menu a', function () {
    closeNavigationDropdowns();
  });

  $(document).on('click', function () {
    closeNavigationDropdowns();
  });

  $('#navbarCollapse').on('hidden.bs.collapse', function () {
    closeNavigationDropdowns();
  });

  const searchPanel = $('#navigation-search-panel');
  const searchToggle = $('#navigation-search-toggle');
  const searchInput = $('#navigation-search-input');
  let searchPreviousFocus = null;

  function visibleSearchItems() {
    return $('[data-navigation-search-item]:visible');
  }

  function filterNavigationSearch() {
    const query = String(searchInput.val() || '').trim().toLowerCase();
    let matchCount = 0;
    $('[data-navigation-search-item]').each(function () {
      const item = $(this);
      const matches = !query || String(item.data('search-text') || '').includes(query);
      item.toggle(matches).removeClass('is-selected');
      if (matches) {
        matchCount += 1;
      }
    });
    $('#navigation-search-empty').prop('hidden', matchCount > 0);
  }

  function openNavigationSearch() {
    if (!searchPanel.length) {
      return;
    }
    searchPreviousFocus = document.activeElement;
    closeNavigationDropdowns();
    searchPanel.prop('hidden', false).attr('aria-hidden', 'false');
    searchToggle.attr('aria-expanded', 'true');
    $('body').addClass('navigation-search-open');
    searchInput.val('');
    filterNavigationSearch();
    window.setTimeout(function () { searchInput.trigger('focus'); }, 0);
  }

  function closeNavigationSearch() {
    if (!searchPanel.length || searchPanel.prop('hidden')) {
      return;
    }
    searchPanel.prop('hidden', true).attr('aria-hidden', 'true');
    searchToggle.attr('aria-expanded', 'false');
    $('body').removeClass('navigation-search-open');
    if (searchPreviousFocus && typeof searchPreviousFocus.focus === 'function') {
      searchPreviousFocus.focus();
    }
  }

  searchToggle.on('click', openNavigationSearch);
  $(document).on('click', '[data-navigation-search-close]', closeNavigationSearch);
  searchInput.on('input', filterNavigationSearch);
  searchInput.on('keydown', function (event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      visibleSearchItems().first().trigger('focus').addClass('is-selected');
    }
  });

  $(document).on('keydown', '[data-navigation-search-item]', function (event) {
    const items = visibleSearchItems();
    const index = items.index(this);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      const nextIndex = (index + direction + items.length) % items.length;
      items.removeClass('is-selected').eq(nextIndex).addClass('is-selected').trigger('focus');
    } else if (event.key === 'Home') {
      event.preventDefault();
      items.removeClass('is-selected').first().addClass('is-selected').trigger('focus');
    } else if (event.key === 'End') {
      event.preventDefault();
      items.removeClass('is-selected').last().addClass('is-selected').trigger('focus');
    }
  });

  $(document).on('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === 'k') {
      event.preventDefault();
      if (searchPanel.prop('hidden')) {
        openNavigationSearch();
      } else {
        closeNavigationSearch();
      }
      return;
    }
    if (event.key === 'Escape' && !searchPanel.prop('hidden')) {
      event.preventDefault();
      closeNavigationSearch();
    }
  });

  function prepareSectionNavigation() {
    const automotiveHeadings = {
      'Saved vehicles': 'automotive-vehicles',
      'New diagnostic / work report': 'automotive-reports',
      'Local databases': 'automotive-databases'
    };
    $('.theme-section-title').each(function () {
      const heading = $(this);
      const sectionId = automotiveHeadings[String(heading.text() || '').trim()];
      if (sectionId) {
        heading.closest('section').attr('id', sectionId).addClass('navigation-section-target');
      }
    });

    function syncActiveSectionLink() {
      const hash = window.location.hash || (window.location.pathname === '/account' ? '#profile' : '');
      if (!hash) {
        return;
      }
      $('.section-navigation-link').each(function () {
        const link = $(this);
        const linkHash = this.hash || '';
        const active = linkHash && linkHash === hash;
        if (linkHash) {
          link.toggleClass('active', active);
          if (active) {
            link.attr('aria-current', 'page');
          } else {
            link.removeAttr('aria-current');
          }
        }
      });
      let target = null;
      try {
        target = document.querySelector(hash);
      } catch (error) {
        target = null;
      }
      if (target && window.location.pathname === '/automotive') {
        window.setTimeout(function () {
          target.scrollIntoView({block: 'start'});
        }, 0);
      }
    }

    $(window).on('hashchange', syncActiveSectionLink);
    syncActiveSectionLink();
  }

  prepareSectionNavigation();

  function navPreviewItem(primary, secondary, href) {
    const item = $('<a>', {class: 'nav-preview-item', href: href || '#'});
    $('<strong>').text(primary || 'Activity').appendTo(item);
    if (secondary) {
      $('<small>').text(secondary).appendTo(item);
    }
    return item;
  }

  function renderJobPreview(jobs) {
    const container = $('#job-preview-list').empty();
    const activeJobs = (jobs || []).filter(function (job) {
      return ['queued', 'running'].includes(String(job.status || '').toLowerCase());
    });
    const displayed = (activeJobs.length ? activeJobs : (jobs || [])).slice(0, 4);
    if (!displayed.length) {
      $('<p>', {class: 'nav-preview-empty', text: 'No jobs have been recorded.'}).appendTo(container);
      return;
    }
    displayed.forEach(function (job) {
      const label = job.label || job.host || job.type || job.kind || 'Background job';
      const status = String(job.status || 'unknown');
      const progress = job.progress !== undefined && job.progress !== null ? ` · ${job.progress}%` : '';
      container.append(navPreviewItem(label, `${status}${progress}`, '/jobs'));
    });
  }

  function renderAlertPreview(alerts) {
    const container = $('#alert-preview-list').empty();
    const unread = (alerts || []).filter(function (alert) { return !alert.read; }).slice(0, 4);
    if (!unread.length) {
      $('<p>', {class: 'nav-preview-empty', text: 'No unread alerts.'}).appendTo(container);
      return;
    }
    unread.forEach(function (alert) {
      const label = alert.title || alert.message || alert.device || 'Device alert';
      const detail = alert.source || alert.interface || alert.created_at_label || '';
      container.append(navPreviewItem(label, detail, '/alerts'));
    });
  }

  function updateJobIndicator() {
    if (!$('#job-activity-indicator').length) {
      return;
    }
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
        renderJobPreview(resp.jobs || []);
      },
      complete: function () {
        window.setTimeout(updateJobIndicator, 4000);
      }
    });
  }

  function updateAlertIndicator() {
    if (!$('#new-device-alert-indicator').length) {
      return;
    }
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
        renderAlertPreview(resp.alerts || []);
      },
      complete: function () {
        window.setTimeout(updateAlertIndicator, 5000);
      }
    });
  }

  $(document).on('click', '[data-favourite-action]', function (event) {
    event.preventDefault();
    event.stopPropagation();
    const button = $(this);
    const navbar = $('.app-navbar');
    $.ajax({
      url: '/account/favourites',
      method: 'POST',
      headers: {'X-Requested-With': 'XMLHttpRequest'},
      data: {
        csrf_token: navbar.data('csrf-token') || '',
        action: button.data('favourite-action'),
        url: button.data('favourite-url'),
        label: button.data('favourite-label')
      },
      success: function () {
        window.location.reload();
      },
      error: function (xhr) {
        const response = xhr.responseJSON || {};
        window.alert(response.error || response.message || 'Unable to update favourites.');
      }
    });
  });

  updateJobIndicator();
  updateAlertIndicator();
});
