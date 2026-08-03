(function () {
  'use strict';

  const MIN_SECTIONS = 5;
  const DEFAULT_OPEN_SECTIONS = 2;

  function slugify(value) {
    return String(value || 'section')
      .trim()
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'section';
  }

  function storageKey() {
    return `mobile-router:long-page:${window.location.pathname}`;
  }

  function readState() {
    try {
      const value = JSON.parse(window.localStorage.getItem(storageKey()) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (error) {
      return {};
    }
  }

  function writeState(state) {
    try {
      window.localStorage.setItem(storageKey(), JSON.stringify(state));
    } catch (error) {
      // Page organisation must still work when storage is unavailable.
    }
  }

  function pageContainer() {
    return document.querySelector('main.page-shell, main.theme-page, #main-content.content');
  }

  function topLevelCards(container) {
    return Array.from(container.querySelectorAll('.theme-card')).filter(function (card) {
      if (card.classList.contains('d-none') || card.hasAttribute('data-long-page-skip')) {
        return false;
      }
      const parentCard = card.parentElement && card.parentElement.closest('.theme-card');
      return !parentCard;
    });
  }

  function sectionTitle(card, index) {
    const heading = card.querySelector('.theme-section-title, h2, h3');
    return {
      heading: heading,
      title: heading ? heading.textContent.trim() : `Section ${index + 1}`,
    };
  }

  function directChildContaining(body, element) {
    let current = element;
    while (current && current.parentElement && current.parentElement !== body) {
      current = current.parentElement;
    }
    return current && current.parentElement === body ? current : null;
  }

  function uniqueSectionId(title, used) {
    const base = `section-${slugify(title)}`;
    let candidate = base;
    let suffix = 2;
    while (used.has(candidate) || document.getElementById(candidate)) {
      candidate = `${base}-${suffix}`;
      suffix += 1;
    }
    used.add(candidate);
    return candidate;
  }

  function createToggle() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-sm btn-outline-secondary long-page-section-toggle';
    button.innerHTML = '<i class="fa-solid fa-chevron-up" aria-hidden="true"></i><span>Collapse</span>';
    return button;
  }

  function setCollapsed(section, collapsed, state, persist) {
    section.card.classList.toggle('long-page-section-collapsed', collapsed);
    section.content.hidden = collapsed;
    section.toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    section.toggle.setAttribute('aria-label', `${collapsed ? 'Expand' : 'Collapse'} ${section.title}`);
    section.toggle.querySelector('span').textContent = collapsed ? 'Expand' : 'Collapse';
    section.toggle.querySelector('i').className = `fa-solid ${collapsed ? 'fa-chevron-down' : 'fa-chevron-up'}`;
    section.nav.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    if (persist) {
      state[section.id] = collapsed;
      writeState(state);
    }
  }

  function enhanceCard(card, index, usedIds, state, defaultOpen) {
    const titleInfo = sectionTitle(card, index);
    if (!titleInfo.heading) return null;

    const body = titleInfo.heading.closest('.card-body') || card;
    let header = directChildContaining(body, titleInfo.heading);
    if (!header) return null;

    if (header === titleInfo.heading) {
      const wrapper = document.createElement('div');
      body.insertBefore(wrapper, titleInfo.heading);
      wrapper.appendChild(titleInfo.heading);
      header = wrapper;
    }

    header.classList.add('long-page-section-heading');
    titleInfo.heading.classList.add('long-page-section-title');

    const id = card.id || uniqueSectionId(titleInfo.title, usedIds);
    card.id = id;
    card.setAttribute('data-long-page-section', '');
    card.setAttribute('tabindex', '-1');

    const toggle = createToggle();
    toggle.setAttribute('aria-controls', `${id}-content`);
    header.appendChild(toggle);

    const content = document.createElement('div');
    content.id = `${id}-content`;
    content.className = 'long-page-section-content';
    while (header.nextSibling) {
      content.appendChild(header.nextSibling);
    }
    body.appendChild(content);

    const nav = document.createElement('button');
    nav.type = 'button';
    nav.className = 'long-page-nav-link';
    nav.textContent = titleInfo.title;
    nav.setAttribute('aria-controls', id);

    const section = {
      card: card,
      content: content,
      id: id,
      index: index,
      nav: nav,
      title: titleInfo.title,
      toggle: toggle,
    };

    const hasSavedState = Object.prototype.hasOwnProperty.call(state, id);
    const collapsed = hasSavedState ? Boolean(state[id]) : index >= defaultOpen;
    setCollapsed(section, collapsed, state, false);

    toggle.addEventListener('click', function () {
      setCollapsed(section, !section.content.hidden, state, true);
    });

    nav.addEventListener('click', function () {
      setCollapsed(section, false, state, true);
      section.card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.history.replaceState(null, '', `#${section.id}`);
      section.card.focus({ preventScroll: true });
    });

    return section;
  }

  function buildToolbar(container, sections, state) {
    const toolbar = document.createElement('section');
    toolbar.className = 'long-page-tools';
    toolbar.setAttribute('aria-label', 'Page section controls');
    toolbar.innerHTML = `
      <div class="long-page-tools-header">
        <div>
          <strong>On this page</strong>
          <span class="long-page-section-count">${sections.length} sections</span>
        </div>
        <div class="long-page-tools-actions" role="group" aria-label="Section display controls">
          <button type="button" class="btn btn-sm btn-outline-secondary" data-long-page-action="essentials">Essentials</button>
          <button type="button" class="btn btn-sm btn-outline-secondary" data-long-page-action="expand">Expand all</button>
          <button type="button" class="btn btn-sm btn-outline-secondary" data-long-page-action="collapse">Collapse all</button>
        </div>
      </div>
      <label class="sr-only" for="long-page-section-search">Filter page sections</label>
      <input id="long-page-section-search" class="form-control form-control-sm long-page-section-search" type="search" placeholder="Find a section" autocomplete="off">
      <nav class="long-page-nav" aria-label="Sections on this page"></nav>
    `;

    const nav = toolbar.querySelector('.long-page-nav');
    sections.forEach(function (section) {
      nav.appendChild(section.nav);
    });

    const hero = Array.from(container.children).find(function (child) {
      return child.classList && child.classList.contains('page-hero');
    });
    if (hero) {
      hero.insertAdjacentElement('afterend', toolbar);
    } else {
      container.insertBefore(toolbar, sections[0].card);
    }

    toolbar.querySelector('[data-long-page-action="expand"]').addEventListener('click', function () {
      sections.forEach(function (section) { setCollapsed(section, false, state, false); state[section.id] = false; });
      writeState(state);
    });

    toolbar.querySelector('[data-long-page-action="collapse"]').addEventListener('click', function () {
      sections.forEach(function (section) { setCollapsed(section, true, state, false); state[section.id] = true; });
      writeState(state);
    });

    toolbar.querySelector('[data-long-page-action="essentials"]').addEventListener('click', function () {
      sections.forEach(function (section) {
        const collapsed = section.index >= DEFAULT_OPEN_SECTIONS;
        setCollapsed(section, collapsed, state, false);
        state[section.id] = collapsed;
      });
      writeState(state);
      sections[0].card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    const search = toolbar.querySelector('.long-page-section-search');
    const count = toolbar.querySelector('.long-page-section-count');
    search.addEventListener('input', function () {
      const query = search.value.trim().toLowerCase();
      let matches = 0;
      sections.forEach(function (section) {
        const visible = !query || section.title.toLowerCase().includes(query);
        section.nav.hidden = !visible;
        if (visible) matches += 1;
      });
      count.textContent = query ? `${matches} matching sections` : `${sections.length} sections`;
    });

    return toolbar;
  }

  function observeSections(sections) {
    if (!('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        sections.forEach(function (section) {
          section.nav.classList.toggle('active', section.card === entry.target);
        });
      });
    }, { rootMargin: '-25% 0px -65% 0px', threshold: 0 });
    sections.forEach(function (section) { observer.observe(section.card); });
  }

  function openHashTarget(sections, state) {
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ''));
    if (!id) return;
    const section = sections.find(function (item) { return item.id === id; });
    if (!section) return;
    setCollapsed(section, false, state, true);
    window.setTimeout(function () {
      section.card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
  }

  function initialise() {
    const container = pageContainer();
    if (!container || container.hasAttribute('data-long-page-disabled')) return;

    const cards = topLevelCards(container);
    if (cards.length < MIN_SECTIONS) return;

    container.setAttribute('data-long-page-enhanced', '');
    const defaultOpen = Number(container.getAttribute('data-long-page-open') || DEFAULT_OPEN_SECTIONS);
    const state = readState();
    const usedIds = new Set();
    const sections = cards.map(function (card, index) {
      return enhanceCard(card, index, usedIds, state, defaultOpen);
    }).filter(Boolean);

    if (sections.length < MIN_SECTIONS) return;
    buildToolbar(container, sections, state);
    observeSections(sections);
    openHashTarget(sections, state);
    window.addEventListener('hashchange', function () { openHashTarget(sections, state); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialise);
  } else {
    initialise();
  }
}());
