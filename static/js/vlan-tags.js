(function () {
  'use strict';

  const pending = new Map();
  const cache = new Map();
  let timer = null;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function badgeMarkup(vlan) {
    return `<a class="vlan-tag-badge" href="${escapeHtml(vlan.url)}" title="${escapeHtml(vlan.subnet)}" data-vlan-tag="${vlan.tag === null || vlan.tag === undefined ? '' : escapeHtml(vlan.tag)}"><i class="fa-solid fa-layer-group" aria-hidden="true"></i><span>${escapeHtml(vlan.label)}</span></a>`;
  }

  function targetFor(element) {
    if (element.matches('[data-device-workspace]')) {
      return element.querySelector('.device-compact-summary');
    }
    if (element.matches('[data-network-device-card]')) {
      return element.querySelector('.wireless-network-badges');
    }
    return element.querySelector('[data-vlan-badge-target]') || element;
  }

  function apply(element, vlan) {
    if (!element || !vlan || element.querySelector('.vlan-tag-badge')) return;
    const target = targetFor(element);
    if (!target) return;
    target.insertAdjacentHTML('afterbegin', badgeMarkup(vlan));
    element.dataset.vlanId = vlan.id;
    element.dataset.vlanTag = vlan.tag === null || vlan.tag === undefined ? '' : String(vlan.tag);
    element.dataset.vlanLabel = vlan.label;
  }

  function queueElement(element) {
    const host = String(element.getAttribute('data-host') || '').trim();
    if (!host || element.dataset.vlanLookupQueued === 'true' || element.querySelector('.vlan-tag-badge')) return;
    element.dataset.vlanLookupQueued = 'true';
    if (cache.has(host)) {
      apply(element, cache.get(host));
      return;
    }
    if (!pending.has(host)) pending.set(host, []);
    pending.get(host).push(element);
    window.clearTimeout(timer);
    timer = window.setTimeout(flush, 80);
  }

  async function flush() {
    const batch = Array.from(pending.keys()).slice(0, 256);
    if (!batch.length) return;
    const elements = new Map();
    batch.forEach(function (host) {
      elements.set(host, pending.get(host) || []);
      pending.delete(host);
    });
    try {
      const response = await fetch(`/api/v1/vlans/lookup?ips=${encodeURIComponent(batch.join(','))}`, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) return;
      const payload = await response.json();
      batch.forEach(function (host) {
        const vlan = (payload.vlans || {})[host] || null;
        cache.set(host, vlan);
        (elements.get(host) || []).forEach(function (element) { apply(element, vlan); });
      });
    } catch (error) {
      // VLAN badges are supplemental; network pages remain functional offline.
    }
    if (pending.size) timer = window.setTimeout(flush, 80);
  }

  function scan(root) {
    const source = root || document;
    if (source.matches && source.matches('[data-device-workspace][data-host], [data-network-device-card][data-host], [data-vlan-host][data-host]')) queueElement(source);
    source.querySelectorAll('[data-device-workspace][data-host], [data-network-device-card][data-host], [data-vlan-host][data-host]').forEach(queueElement);
  }

  scan(document);
  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType === Node.ELEMENT_NODE) scan(node);
      });
    });
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
}());
