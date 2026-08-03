$(document).ready(function () {
  const tools = $('[data-ip-client-tools]');
  const host = tools.data('host');
  if (!host || $('[data-host-facts-link]').length) {
    return;
  }
  const actions = $('[data-ip-client-intelligence]').closest('.theme-actions');
  if (!actions.length) {
    return;
  }
  const link = $('<a>', {
    class: 'btn btn-outline-primary',
    href: `/clients/${encodeURIComponent(host)}/host-facts`,
    text: 'Host facts & capabilities',
    'data-host-facts-link': 'true'
  });
  actions.append(link);
});
