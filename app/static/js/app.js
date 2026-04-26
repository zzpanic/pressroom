// app.js — Pressroom main application logic
// ─────────────────────────────────────────────────────────────────────────────
// Depends on api.js (fetch wrapper) and ui.js (DOM helpers), loaded first.
// ─────────────────────────────────────────────────────────────────────────────


// ── Global state ──────────────────────────────────────────────────────────────

let config          = {};   // from /api/config — author details, repo names
let currentSlug     = null; // slug of the selected paper
let currentFrontmatter = {}; // frontmatter loaded from GitHub for this paper
let pdfReady        = false; // true once a PDF has been generated for currentSlug


// ── Boot ──────────────────────────────────────────────────────────────────────

async function init() {
  // Load config (triggers bootstrap of zz-pressroom/ on first run)
  try {
    config = await api('/api/config');
    document.getElementById('repo-label').textContent = config.github_repo;
  } catch (e) {
    document.getElementById('repo-label').textContent = 'error loading config';
  }

  // Load template and license dropdowns
  await loadSelects();

  // Load the paper list
  await loadPapersList();

  // Wire up top navigation
  setupNav();
}

init();


// ── Navigation ────────────────────────────────────────────────────────────────

function setupNav() {
  // The two views are Workspace and Prompts.
  // Clicking a nav item shows its view and hides the other.
  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;

      // Update active tab
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      // Show the selected view, hide the other
      document.getElementById('view-workspace').classList.toggle('hidden', view !== 'workspace');
      document.getElementById('view-prompts').classList.toggle('hidden', view !== 'prompts');

      // Load prompts on first open
      if (view === 'prompts') loadPrompts();
    });
  });
}


// ── Selects (templates and licenses) ─────────────────────────────────────────

async function loadSelects() {
  // Fetch templates and licenses in parallel for speed
  const [templates, licenses] = await Promise.all([
    api('/api/templates').catch(() => []),
    api('/api/licenses').catch(() => []),
  ]);
  populateSelect('m-template', templates);
  populateSelect('m-license', licenses);
}


// ── Paper list ────────────────────────────────────────────────────────────────

async function loadPapersList() {
  // /api/papers now returns [{slug, title, gate, version}] with frontmatter metadata
  const list = document.getElementById('paper-list');
  list.innerHTML = '<li class="list-loading">Loading...</li>';

  let papers;
  try {
    papers = await api('/api/papers');
  } catch (e) {
    list.innerHTML = `<li class="list-empty">Error loading papers: ${e.message}</li>`;
    return;
  }

  if (!papers.length) {
    list.innerHTML = '<li class="list-empty">No papers found in ideas-workbench.</li>';
    return;
  }

  // Sort alphabetically by slug
  papers.sort((a, b) => a.slug.localeCompare(b.slug));

  list.innerHTML = papers.map(p => `
    <li class="paper-row" data-slug="${p.slug}" onclick="selectPaper('${p.slug}')">
      <div style="flex:1;min-width:0">
        <div class="paper-row-name">${p.slug}</div>
        ${p.title && p.title !== p.slug
          ? `<div class="paper-row-title">${escapeHtml(p.title)}</div>`
          : ''}
      </div>
      <span class="gate-badge ${gateBadgeClass(p.gate, p.version)}">${badgeLabel(p.gate, p.version)}</span>
    </li>
  `).join('');
}

function gateBadgeClass(gate, version) {
  // Pick a colour class based on the gate, or unpublished if no version yet
  if (!gate && (!version || version === 'unpublished')) return 'badge-unpublished';
  const map = {
    alpha: 'badge-alpha',
    exploratory: 'badge-exploratory',
    draft: 'badge-draft',
    review: 'badge-review',
    published: 'badge-published',
  };
  return map[gate] || 'badge-unpublished';
}

function badgeLabel(gate, version) {
  // Show the version string, or the gate name if version is missing, or "unpublished"
  if (version && version !== 'unpublished') return version;
  if (gate) return gate;
  return 'unpublished';
}

function escapeHtml(str) {
  // Prevent XSS when injecting paper titles into innerHTML
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}


// ── Select a paper ────────────────────────────────────────────────────────────

async function selectPaper(slug) {
  // Highlight the clicked row
  document.querySelectorAll('.paper-row').forEach(r => r.classList.remove('active'));
  const row = document.querySelector(`.paper-row[data-slug="${slug}"]`);
  if (row) row.classList.add('active');

  // Reset state
  currentSlug = slug;
  pdfReady    = false;
  document.getElementById('download-btn').disabled = true;
  clearPreview();
  setActionMsg('Loading...', 'info');

  try {
    const data = await api(`/api/papers/${slug}`);
    currentFrontmatter = data.frontmatter || {};
    populateForm(data.frontmatter || {});
    showForm();
    setActionMsg('', '');
  } catch (e) {
    setActionMsg(`Error loading paper: ${e.message}`, 'err');
  }
}

function showForm() {
  // Reveal the paper form and author strip below the paper list
  document.getElementById('paper-form').classList.remove('hidden');

  // Show the author details
  const display = document.getElementById('author-display');
  if (display) {
    display.textContent = [config.author_name, config.author_email, config.author_github]
      .filter(Boolean).join('  ·  ');
  }
}

function clearPreview() {
  // Reset the right pane to its blank state
  document.getElementById('preview-placeholder').classList.remove('hidden');
  document.getElementById('preview-content').classList.add('hidden');
  document.getElementById('preview-content').innerHTML = '';
  document.getElementById('preview-template-label').textContent = 'Preview';
}

function populateForm(fm) {
  // Fill every form field from the paper's frontmatter
  setValue('m-title',    fm.title    || '');
  setValue('m-subtitle', fm.subtitle || '');
  setValue('m-gate',     fm.gate     || 'exploratory');
  setValue('m-version',  fm.version  || gateToVersion(fm.gate || 'exploratory'));
  setValue('m-template', fm.template || 'whitepaper');
  setValue('m-license',  fm.license  || 'CC BY 4.0');

  const ai = fm.ai_assisted || {};
  setChecked('m-ai-ideation', !!ai.ideation);
  setChecked('m-ai-writing',  !!ai.writing);
  setChecked('m-ai-research', !!ai.research);
  setValue('m-ai-tool', fm.ai_tool || '');

  setValue('m-prior-art',   fm.prior_art_disclosure || '');
  setValue('m-github-repo', fm.github_repo          || '');
  setValue('m-zenodo-doi',  fm.zenodo_doi            || '');

  const chk = fm.checklist || {};
  setChecked('chk-content',      !!chk.content_reviewed);
  setChecked('chk-prior-art',    !!chk.prior_art_searched);
  setChecked('chk-placeholders', !!chk.placeholders_resolved);
  setChecked('chk-license',      !!chk.license_confirmed);
  setChecked('chk-refs',         !!chk.references_complete);
}

function buildFrontmatter() {
  // Read all form fields and return a frontmatter dict ready to send to the server
  return {
    title:    val('m-title'),
    subtitle: val('m-subtitle'),
    slug:     currentSlug,
    author: {
      name:   config.author_name,
      email:  config.author_email,
      github: config.author_github,
    },
    gate:     val('m-gate'),
    version:  val('m-version'),
    template: val('m-template'),
    license:  val('m-license'),
    ai_assisted: {
      ideation: checked('m-ai-ideation'),
      writing:  checked('m-ai-writing'),
      research: checked('m-ai-research'),
    },
    ai_tool:              val('m-ai-tool'),
    prior_art_disclosure: val('m-prior-art'),
    github_repo:          val('m-github-repo'),
    zenodo_doi:           val('m-zenodo-doi'),
    checklist: {
      content_reviewed:      checked('chk-content'),
      prior_art_searched:    checked('chk-prior-art'),
      placeholders_resolved: checked('chk-placeholders'),
      license_confirmed:     checked('chk-license'),
      references_complete:   checked('chk-refs'),
    },
  };
}

function onGateChange() {
  // When gate changes, auto-fill the version field
  setValue('m-version', gateToVersion(val('m-gate')));
}

function onTemplateChange() {
  // When template changes, re-render the HTML preview if one exists
  const content = document.getElementById('preview-content');
  if (!content.classList.contains('hidden')) {
    // Preview already showing — re-render with new template CSS
    const template = val('m-template');
    content.className = `preview-content preview-${template}`;
    document.getElementById('preview-template-label').textContent = `Preview — ${template}`;
  }
}


// ── Save (internal, called before generate/snapshot/release) ─────────────────

async function savePaper() {
  // Writes the current form state back to {slug}/publish/{slug}.md on GitHub.
  // Returns true on success, false on failure.
  try {
    await api(`/api/papers/${currentSlug}/save`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(buildFrontmatter()),
    });
    return true;
  } catch (e) {
    setActionMsg(`Save failed: ${e.message}`, 'err');
    return false;
  }
}


// ── Generate Preview ──────────────────────────────────────────────────────────

async function generatePreview() {
  if (!currentSlug) return;

  setActionMsg('Saving and generating preview...', 'info');

  // Always save the form state first so preview and file are in sync
  const saved = await savePaper();
  if (!saved) return;

  // ── Step 1: HTML preview (fast, ~1s, no LaTeX) ────────────────────────────
  try {
    const result = await api(`/api/preview/html/${currentSlug}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ frontmatter: buildFrontmatter() }),
    });

    const template = val('m-template');
    const content  = document.getElementById('preview-content');

    // DOMPurify sanitises the Pandoc HTML before injecting into the page
    content.innerHTML = DOMPurify.sanitize(result.html);
    content.className = `preview-content preview-${template}`;
    document.getElementById('preview-placeholder').classList.add('hidden');
    content.classList.remove('hidden');
    document.getElementById('preview-template-label').textContent = `Preview — ${template}`;

    setActionMsg('Preview generated. Generating PDF in background...', 'info');
  } catch (e) {
    setActionMsg(`Preview failed: ${e.message}`, 'err');
    return;
  }

  // ── Step 2: PDF (slow, ~20-30s, runs in background) ──────────────────────
  // We fire this off without awaiting so the user can see the HTML preview
  // immediately.  The download button enables when the PDF is ready.
  generatePDFBackground();
}

async function generatePDFBackground() {
  try {
    const r = await fetch(`/api/preview/${currentSlug}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ frontmatter: buildFrontmatter() }),
    });

    if (!r.ok) {
      const err = await r.text();
      setActionMsg(`PDF failed: ${err}`, 'warn');
      return;
    }

    // PDF is ready — enable the download button
    pdfReady = true;
    document.getElementById('download-btn').disabled = false;

    // Surface any pre-flight warnings from the PDF generation
    const warnings     = JSON.parse(r.headers.get('X-Pressroom-Warnings') || '[]');
    const placeholders = parseInt(r.headers.get('X-Pressroom-Placeholder-Count') || '0');

    if (warnings.length) {
      setActionMsg(`Preview ready ⚠ ${warnings.join(' | ')}`, 'warn');
    } else if (placeholders > 0) {
      setActionMsg(`Preview ready — ${placeholders} placeholder(s) remain`, 'warn');
    } else {
      setActionMsg('Preview ready. PDF saved to GitHub.', 'ok');
    }
  } catch (e) {
    setActionMsg(`PDF generation error: ${e.message}`, 'warn');
  }
}

function downloadPDF() {
  if (!pdfReady || !currentSlug) return;
  // Use {slug}-{version}.pdf as the download filename so it's identifiable
  const version = val('m-version') || 'preview';
  const a       = document.createElement('a');
  a.href        = `/api/preview/${currentSlug}/download`;
  a.download    = `${currentSlug}-${version}.pdf`;
  a.click();
}


// ── Snapshot (private — ideas-workbench only) ─────────────────────────────────

async function snapshotPaper() {
  if (!currentSlug) return;

  setActionMsg('Saving and creating snapshot...', 'info');

  const saved = await savePaper();
  if (!saved) return;

  const version = val('m-version');
  const gate    = val('m-gate');

  if (!confirm(`Create snapshot "${currentSlug}" at ${version}?\n\nThis saves a versioned copy to ideas-workbench (private). It will NOT be public.`)) {
    setActionMsg('', '');
    return;
  }

  try {
    const result = await api(`/api/papers/${currentSlug}/snapshot`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ version, gate }),
    });
    setActionMsg(result.message, 'ok');
    // Refresh the paper list so the badge updates
    await loadPapersList();
  } catch (e) {
    setActionMsg(`Snapshot failed: ${e.message}`, 'err');
  }
}


// ── Release (public — pressroom-pubs) ─────────────────────────────────────────

async function releasePaper() {
  if (!currentSlug) return;

  // All checklist items must be ticked before releasing publicly
  const allChecked = ['chk-content','chk-prior-art','chk-placeholders','chk-license','chk-refs']
    .every(id => checked(id));

  if (!allChecked) {
    setActionMsg('Complete all checklist items before releasing', 'warn');
    return;
  }

  const version = val('m-version');
  const gate    = val('m-gate');

  if (!confirm(`Release "${currentSlug}" as ${version} (${gate})?\n\nThis publishes to pressroom-pubs and makes it publicly visible.`)) {
    return;
  }

  setActionMsg('Saving and releasing...', 'info');

  const saved = await savePaper();
  if (!saved) return;

  try {
    const result = await api(`/api/papers/${currentSlug}/publish`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ version, gate }),
    });
    setActionMsg(result.message, 'ok');
    await loadPapersList();
  } catch (e) {
    setActionMsg(`Release failed: ${e.message}`, 'err');
  }
}


// ── Action message helper ─────────────────────────────────────────────────────

function setActionMsg(text, type) {
  const el = document.getElementById('action-msg');
  if (!el) return;
  if (!text) { el.innerHTML = ''; return; }
  el.innerHTML = `<span class="msg-${type}">${text}</span>`;
}


// ── Prompts ───────────────────────────────────────────────────────────────────

let promptsLoaded = false;

async function loadPrompts() {
  if (promptsLoaded) return; // Only fetch once per session

  const grid = document.getElementById('prompts-grid');
  grid.innerHTML = '<div class="list-loading">Loading prompts...</div>';

  let prompts;
  try {
    prompts = await api('/api/prompts');
  } catch (e) {
    grid.innerHTML = `<div class="list-empty">Error loading prompts: ${e.message}</div>`;
    return;
  }

  if (!prompts.length) {
    grid.innerHTML = `
      <div class="prompts-empty">
        No prompts found.<br>
        Add <code>.md</code> files to <code>zz-pressroom/prompts/</code> in your workbench repo.
      </div>`;
    return;
  }

  // Render each prompt as a card with a 4-5 line preview and a copy button.
  // The full content is stored in a data attribute so Copy works without an API call.
  grid.innerHTML = prompts.map(p => `
    <div class="prompt-card">
      <div class="prompt-card-header">
        <div class="prompt-card-name">${escapeHtml(p.name)}</div>
        <button class="prompt-copy-btn" onclick="copyPrompt(this, '${escapeHtml(p.name)}')">
          &#9112; Copy
        </button>
      </div>
      <div class="prompt-preview">${escapeHtml(p.preview)}</div>
    </div>
  `).join('');

  // Store full content on each card for clipboard access
  prompts.forEach((p, i) => {
    grid.children[i]._promptContent = p.content;
  });

  promptsLoaded = true;
}

async function copyPrompt(btn, name) {
  // Get the full prompt content — stored on the card element
  const card    = btn.closest('.prompt-card');
  let content   = card._promptContent;

  // If content somehow isn't cached, fetch it
  if (!content) {
    try {
      const data = await api(`/api/prompts/${name}`);
      content = data.content;
    } catch (e) {
      btn.textContent = 'Error';
      return;
    }
  }

  try {
    await navigator.clipboard.writeText(content);
    btn.classList.add('copied');
    btn.innerHTML = '&#10003; Copied';
    setTimeout(() => {
      btn.classList.remove('copied');
      btn.innerHTML = '&#9112; Copy';
    }, 1500);
  } catch (e) {
    btn.textContent = 'Failed';
  }
}
