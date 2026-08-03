(function () {
  'use strict';

  const MIN_SECTIONS = 5;

  function slugify(value) {
    return String(value || 'section')
      .trim()
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'section';
  }

  function storageKey() {
    return `mobile-router:long-page-tab:${window.location.pathname}`;
  }

  function readActiveSection() {
    try {
      return String(window.localStorage.getItem(storageKey()) || '');
    } catch (error) {
      return '';
    }
  }

  function writeActiveSection(sectionId) {
    try {
      window.localStorage.setItem(storageKey(), sectionId);
    } catch (error) {
      // Tabs remain usable when browser storage is disabled.
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

  function prepareSection(card, index, usedIds) {
    const titleInfo = sectionTitle(card, index);
    if (!titleInfo.heading) return null;

    const sectionId = card.id || uniqueSectionId(titleInfo.title, usedIds);
    const tabId = `tab-${sectionId}`;

    card.id = sectionId;
    card.setAttribute('data-long-page-tab-panel', '');
    card.setAttribute('role', 'tabpanel');
    card.setAttribute('aria-labelledby', tabId);
    card.setAttribute('tabindex', '-1');

    const tab = document.createElement('button');
    tab.type = 'button';
    tab.id = tabId;
    tab.className = 'long-page-tab';
    tab.textContent = titleInfo.title;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', sectionId);
    tab.setAttribute('aria-selected', 'false');
    tab.setAttribute('tabindex', '-1');

    const option = document.createElement('option');
    option.value = sectionId;
    option.textContent = titleInfo.title;

    return {
      card: card,
      heading: titleInfo.heading,
      id: sectionId,
      index: index,
      option: option,
      tab: tab,
      title: titleInfo.title,
    };
  }

  function sectionForHash(sections) {
    const hashId = decodeURIComponent(window.location.hash.replace(/^#/, ''));
    if (!hashId) return null;

    const target = document.getElementById(hashId);
    if (!target) return null;

    const panel = target.matches('[data-long-page-tab-panel]')
      ? target
      : target.closest('[data-long-page-tab-panel]');
    if (!panel) return null;

    return sections.find(function (section) {
      return section.card === panel;
    }) || null;
  }

  function buildTabs(container, sections) {
    const shell = document.createElement('section');
    shell.className = 'long-page-tabs-shell';
    shell.setAttribute('aria-label', 'Page sections');
    shell.innerHTML = `
      <div class="long-page-tabs-header">
        <div>
          <strong>Page sections</strong>
          <span class="long-page-section-count">${sections.length} tabs</span>
        </div>
        <small class="text-muted">Only the selected section is shown.</small>
      </div>
      <div class="long-page-tablist" role="tablist" aria-label="Page sections"></div>
      <div class="long-page-tab-select-group">
        <label for="long-page-tab-select">Section</label>
        <select id="long-page-tab-select" class="form-control long-page-tab-select" aria-label="Choose page section"></select>
      </div>
    `;

    const tablist = shell.querySelector('.long-page-tablist');
    const select = shell.querySelector('.long-page-tab-select');
    sections.forEach(function (section) {
      tablist.appendChild(section.tab);
      select.appendChild(section.option);
    });

    const hero = Array.from(container.children).find(function (child) {
      return child.classList && child.classList.contains('page-hero');
    });
    if (hero) {
      hero.insertAdjacentElement('afterend', shell);
    } else {
      container.insertBefore(shell, sections[0].card);
    }

    return { shell: shell, select: select, tablist: tablist };
  }

  function initialise() {
    const container = pageContainer();
    if (!container || container.hasAttribute('data-long-page-disabled')) return;

    const cards = topLevelCards(container);
    if (cards.length < MIN_SECTIONS) return;

    const usedIds = new Set();
    const sections = cards.map(function (card, index) {
      return prepareSection(card, index, usedIds);
    }).filter(Boolean);
    if (sections.length < MIN_SECTIONS) return;

    container.setAttribute('data-long-page-enhanced', 'tabs');
    const controls = buildTabs(container, sections);
    let activeSection = null;

    function activate(section, options) {
      if (!section) return;
      const settings = Object.assign({
        focusPanel: false,
        scrollTarget: null,
        updateHash: true,
      }, options || {});

      sections.forEach(function (candidate) {
        const active = candidate === section;
        candidate.card.hidden = !active;
        candidate.card.classList.toggle('long-page-tab-panel-active', active);
        candidate.tab.classList.toggle('active', active);
        candidate.tab.setAttribute('aria-selected', active ? 'true' : 'false');
        candidate.tab.setAttribute('tabindex', active ? '0' : '-1');
      });

      activeSection = section;
      controls.select.value = section.id;
      section.tab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
      writeActiveSection(section.id);

      if (settings.updateHash) {
        window.history.replaceState(null, '', `#${section.id}`);
      }

      const target = settings.scrollTarget || section.card;
      if (settings.scrollTarget) {
        window.setTimeout(function () {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 0);
      }

      if (settings.focusPanel) {
        section.card.focus({ preventScroll: true });
      }
    }

    sections.forEach(function (section) {
      section.tab.addEventListener('click', function () {
        activate(section, { focusPanel: true });
      });
    });

    controls.select.addEventListener('change', function () {
      const section = sections.find(function (candidate) {
        return candidate.id === controls.select.value;
      });
      activate(section, { focusPanel: true });
    });

    controls.tablist.addEventListener('keydown', function (event) {
      if (!activeSection) return;
      const currentIndex = sections.indexOf(activeSection);
      let nextIndex = null;

      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        nextIndex = (currentIndex + 1) % sections.length;
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        nextIndex = (currentIndex - 1 + sections.length) % sections.length;
      } else if (event.key === 'Home') {
        nextIndex = 0;
      } else if (event.key === 'End') {
        nextIndex = sections.length - 1;
      }

      if (nextIndex === null) return;
      event.preventDefault();
      activate(sections[nextIndex], { updateHash: true });
      sections[nextIndex].tab.focus();
    });

    function activateHashTarget() {
      const section = sectionForHash(sections);
      if (!section) return false;
      const hashId = decodeURIComponent(window.location.hash.replace(/^#/, ''));
      const target = document.getElementById(hashId);
      activate(section, {
        scrollTarget: target && target !== section.card ? target : null,
        updateHash: false,
      });
      return true;
    }

    const savedId = readActiveSection();
    const savedSection = sections.find(function (section) {
      return section.id === savedId;
    });

    if (!activateHashTarget()) {
      activate(savedSection || sections[0], { updateHash: false });
    }

    window.addEventListener('hashchange', activateHashTarget);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialise);
  } else {
    initialise();
  }
}());
