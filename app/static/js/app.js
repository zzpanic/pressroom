// app.js
// ─────────────────────────────────────────────────────────────────────────────
// Main application logic for Pressroom.
//
// This file depends on api.js (the fetch wrapper) and ui.js (DOM helpers),
// both of which must be loaded before this file in index.html.
//
// Structure:
//   - Global state variables
//   - Startup (init, loadSelects, setupNav)
//   - New paper prompt panel
//   - QA & Publish panel (load paper, populate form, save, preview, publish)
//   - Papers list panel
// ─────────────────────────────────────────────────────────────────────────────


// ── Global state ──────────────────────────────────────────────────────────────
// These variables are shared across functions in this file.

// Config loaded from /api/config on startup (author details, repo names)
let config = {};

// The slug of the currently loaded paper (e.g. "my-great-idea")
let currentSlug = null;

// The full frontmatter of the currently loaded paper
// Used to preserve fields not shown in the UI (e.g. zenodo_doi if not editable)
let currentFrontmatter = {};


// ── Startup ───────────────────────────────────────────────────────────────────

/**
 * Called once when the page loads.
 * Fetches config from the server and sets up the UI.
 */
async function init() {
  // Load author details and repo names from the server
  config = await api('/api/config');

  // Show the repo name in the header bar
  document.getElementById('repo-label').textContent = config.github_repo;

  // Populate the template and license dropdown selects
  await loadSelects();

  // Wire up the sidebar navigation clicks
  setupNav();
}

/**
 * Fetch the list of templates and licenses and populate the dropdown selects.
 * Runs two API calls in parallel for speed.
 */
async function loadSelects() {
  const [templates, licenses] = await Promise.all([
    api('/api/templates'),
    api('/api/licenses'),
  ]);
  // Populate both the new-paper panel and the publish panel template selects
  populateSelect('np-template', templates);
  populateSelect('m-template', templates);
  populateSelect('m-license', licenses);
}

/**
 * Set up click handlers on the sidebar navigation items.
 * Clicking an item shows its panel and hides all others.
 */
function setupNav() {
  document.querySelectorAll('.nav-item[data-panel]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      // Hide all panels, then show the one matching the clicked item
      const panelId = item.dataset.panel;
      document.querySelectorAll('[id^="panel-"]').forEach(p => p.classList.add('hidden'));
      document.getElementById(`panel-${panelId}`).classList.remove('hidden');

      // The papers list loads its content on demand when the panel opens
      if (panelId === 'papers') loadPapersList();
    });
  });
}


// ── New paper prompt ──────────────────────────────────────────────────────────

/**
 * Generate an AI prompt based on the selected template.
 * The prompt tells the AI to write a structured paper using [PLACEHOLDER: ...]
 * markers for anything incomplete.
 */
async function generatePrompt() {
  const slug     = document.getElementById('np-slug').value.trim();
  const template = document.getElementById('np-template').value;

  if (!slug) { alert('Enter a slug first'); return; }

  // Fetch the template content and its section headers from the server
  const tmpl = await api(`/api/templates/${template}`);

  // Format the section headers as an indented list for the prompt
  const headers = tmpl.headers
    .filter(h => !h.startsWith('!') && h.length > 0)
    .map(h => `  ${h}`)
    .join('\n');

  // Build the prompt text that will be pasted into Claude or another AI
  const prompt =
`Based on our discussion, produce a paper using the structure below.

Rules:
- Output clean markdown only — no commentary, no preamble
- Use [PLACEHOLDER: description] for ANYTHING incomplete, uncertain, or undecided
- Use [PLACEHOLDER: prior art search needed — topic] where prior art should be checked
- Use [PLACEHOLDER: reference needed — source] for any citations not yet confirmed
- Match the exact section headers below
- Include a References section with all sources discussed

Slug     : ${slug}
Template : ${template}

Template structure:
${headers}

Begin the paper now.`;

  // Show the prompt in the output box
  document.getElementById('prompt-output').textContent = prompt;
  document.getElementById('prompt-panel').classList.remove('hidden');
}

/**
 * Copy the generated prompt text to the clipboard.
 */
function copyPrompt() {
  const text = document.getElementById('prompt-output').textContent;
  navigator.clipboard.writeText(text).then(() => {
    setMsg('copy-msg', 'Copied to clipboard', 'ok');
    // Clear the message after 2 seconds
    setTimeout(() => document.getElementById('copy-msg').innerHTML = '', 2000);
  });
}


// ── Load paper ────────────────────────────────────────────────────────────────

/**
 * Load a paper by slug from the server.
 * Reads the slug from the input field, fetches the paper's frontmatter,
 * and populates the metadata form.
 */
async function loadPaper() {
  const slug = document.getElementById('pub-slug').value.trim();
  if (!slug) { alert('Enter a paper slug'); return; }

  setMsg('load-msg', 'Loading...', 'info');
  try {
    // GET /api/papers/{slug} returns { slug, frontmatter, paper_exists }
    const data = await api(`/api/papers/${slug}`);

    currentSlug        = slug;
    currentFrontmatter = data.frontmatter || {};

    // Fill the form fields with the paper's frontmatter values
    populatePublishForm(data);

    // Show author strip
    const authorDisplay = document.getElementById('author-display');
    if (authorDisplay) {
      authorDisplay.textContent = [config.author_name, config.author_email, config.author_github]
        .filter(Boolean).join('  ·  ');
    }

    // Show the rest of the form and the bottom action bar
    document.getElementById('publish-form').classList.remove('hidden');
    document.getElementById('action-bar').classList.remove('hidden');

    if (!data.paper_exists) {
      setMsg('load-msg', `Warning: ${slug}/publish/${slug}.md not found. Add the file before previewing.`, 'warn');
    } else {
      setMsg('load-msg', `Loaded: ${slug}`, 'ok');
    }
  } catch (e) {
    setMsg('load-msg', `Error: ${e.message}`, 'err');
  }
}

/**
 * Populate all the metadata form fields from a paper's frontmatter.
 *
 * The frontmatter may have a nested 'author' object {name, email, github}
 * or may be missing fields entirely — we fall back to the config defaults
 * (from author.yaml) so the form is never blank on a new paper.
 *
 * @param {object} data - the response from GET /api/papers/{slug}
 */
function populatePublishForm(data) {
  const fm = data.frontmatter;

  // Paper identity
  setValue('m-title',    fm.title    || '');
  setValue('m-subtitle', fm.subtitle || '');

  // Gate and version
  setValue('m-gate',    fm.gate    || 'exploratory');
  setValue('m-version', fm.version || gateToVersion(fm.gate || 'exploratory'));

  // Template and license
  setValue('m-template', fm.template || 'whitepaper');
  setValue('m-license',  fm.license  || 'CC BY 4.0');

  // AI disclosure — stored under ai_assisted in the spec schema
  const ai = fm.ai_assisted || {};
  setChecked('m-ai-ideation', ai.ideation || false);
  setChecked('m-ai-writing',  ai.writing  || false);
  setChecked('m-ai-research', ai.research || false);
  // ai_tool is an extra field Pressroom adds (not in spec but useful)
  setValue('m-ai-tool', fm.ai_tool || '');

  // Prior art and publication links
  setValue('m-prior-art',   fm.prior_art_disclosure || '');
  setValue('m-github-repo', fm.github_repo          || '');
  setValue('m-zenodo-doi',  fm.zenodo_doi            || '');

  const chk = fm.checklist || {};
  setChecked('chk-content',      chk.content_reviewed      || false);
  setChecked('chk-prior-art',    chk.prior_art_searched    || false);
  setChecked('chk-placeholders', chk.placeholders_resolved || false);
  setChecked('chk-license',      chk.license_confirmed     || false);
  setChecked('chk-refs',         chk.references_complete   || false);
}

/**
 * Read all the form fields and build the frontmatter object to send to the server.
 *
 * This is the reverse of populatePublishForm.
 * The server (routers/papers.py) will auto-fill derived fields like status,
 * license_url, and date before writing back to GitHub.
 *
 * @returns {object} frontmatter fields ready to POST to /api/papers/{slug}/save
 */
function buildFrontmatter() {
  return {
    // Paper identity
    title:    val('m-title'),
    subtitle: val('m-subtitle'),
    slug:     currentSlug,

    // Author always comes from config (env vars) in single-user mode
    author: {
      name:   config.author_name,
      email:  config.author_email,
      github: config.author_github,
    },

    // Gate and version
    gate:    val('m-gate'),
    version: val('m-version'),

    // Template and license
    template: val('m-template'),
    license:  val('m-license'),

    // AI disclosure (spec field name: ai_assisted)
    ai_assisted: {
      ideation: checked('m-ai-ideation'),
      writing:  checked('m-ai-writing'),
      research: checked('m-ai-research'),
    },
    // Extra field — the specific tool used (not in spec but useful to record)
    ai_tool: val('m-ai-tool'),

    // Prior art and publication links (spec field names)
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

/**
 * When the gate dropdown changes, automatically update the version field
 * to the canonical version string for that gate (e.g. "draft" → "v0.2-draft").
 * The user can still manually override the version after this.
 */
function updateVersion() {
  setValue('m-version', gateToVersion(val('m-gate')));
}


// ── Actions ───────────────────────────────────────────────────────────────────

/**
 * Save the current form state back to {slug}/publish/{slug}.md on GitHub.
 * This updates the frontmatter metadata without touching the paper body.
 */
async function savePaper() {
  setMsg('action-msg', 'Saving...', 'info');
  try {
    await api(`/api/papers/${currentSlug}/save`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(buildFrontmatter()),
    });
    setMsg('action-msg', 'Metadata saved to GitHub', 'ok');
  } catch (e) {
    setMsg('action-msg', `Error: ${e.message}`, 'err');
  }
}

/**
 * Generate a PDF for the current paper and show it in the browser.
 *
 * This runs the full preview workflow (spec §7.4 steps 1–4):
 *   1. Fetches {slug}.md from GitHub
 *   2. Generates the PDF via Pandoc
 *   3. Pushes the review copy back to {slug}/publish/{slug}.pdf on GitHub
 *   4. Displays the PDF in the iframe below the actions panel
 *
 * This can take 20–30 seconds depending on paper length.
 */
async function previewPDF() {
  setMsg('action-msg', 'Generating PDF — this may take 20–30 seconds...', 'info');
  try {
    // The preview endpoint returns the PDF as a binary blob, not JSON,
    // so we use raw fetch() instead of the api() wrapper
    const r = await fetch(`/api/preview/${currentSlug}`);
    if (!r.ok) {
      const err = await r.text();
      setMsg('action-msg', `PDF generation failed: ${err}`, 'err');
      return;
    }

    // Create a temporary browser URL for the PDF blob and load it in the iframe
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    document.getElementById('pdf-frame').src = url;
    document.getElementById('pdf-panel').classList.remove('hidden');

    // Surface any pre-flight warnings returned in response headers
    const warnings = JSON.parse(r.headers.get('X-Pressroom-Warnings') || '[]');
    const placeholders = parseInt(r.headers.get('X-Pressroom-Placeholder-Count') || '0');

    if (warnings.length) {
      const warnText = warnings.join(' | ');
      setMsg('action-msg', `PDF generated ⚠ ${warnText}`, 'warn');
    } else if (placeholders > 0) {
      setMsg('action-msg', `PDF generated — ${placeholders} placeholder(s) remain`, 'warn');
    } else {
      setMsg('action-msg', 'PDF generated and saved to GitHub as review copy', 'ok');
    }
  } catch (e) {
    setMsg('action-msg', `Error: ${e.message}`, 'err');
  }
}

/**
 * Trigger a browser download of the last generated PDF.
 * Does not regenerate — use "Preview PDF" first.
 */
async function downloadPDF() {
  // Create a temporary <a> tag and click it to trigger the download
  const a      = document.createElement('a');
  a.href       = `/api/preview/${currentSlug}/download`;
  a.download   = `${currentSlug}-preview.pdf`;
  a.click();
}

/**
 * Publish the current paper to GitHub.
 *
 * Before publishing:
 *   - All checklist items must be ticked
 *   - The user must confirm the version string and gate in a dialog
 *
 * This runs spec §7.4 steps 5–7:
 *   5. Saves the current frontmatter
 *   6. Creates a versioned snapshot in ideas-workbench
 *   7. Mirrors the snapshot to pressroom-pubs
 *
 * Note: "Preview PDF" must have been run first — the publish step reads
 * the review PDF from GitHub, not from the local /tmp folder.
 */
async function publishPaper() {
  // Guard: all checklist items must be ticked
  const allChecked = [
    'chk-content', 'chk-prior-art',
    'chk-placeholders', 'chk-license', 'chk-refs',
  ].every(id => checked(id));

  if (!allChecked) {
    setMsg('action-msg', 'Complete all checklist items before publishing', 'warn');
    return;
  }

  // Ask the user to confirm before doing anything irreversible
  const version = val('m-version');
  const gate    = val('m-gate');
  if (!confirm(`Publish "${currentSlug}" as ${version} (${gate})?\n\nThis will create a versioned snapshot in ideas-workbench and push it to pressroom-pubs.`)) {
    return;
  }

  setMsg('action-msg', 'Saving metadata and publishing...', 'info');
  try {
    // Save the latest form state first so the snapshot includes current metadata
    await savePaper();

    // Trigger the snapshot + mirror
    const result = await api(`/api/papers/${currentSlug}/publish`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ version }),
    });

    setMsg('action-msg', result.message, 'ok');
  } catch (e) {
    setMsg('action-msg', `Error: ${e.message}`, 'err');
  }
}


// ── Papers list ───────────────────────────────────────────────────────────────

/**
 * Load and display the list of all papers from ideas-workbench.
 * Called when the Papers panel is opened.
 */
async function loadPapersList() {
  const el = document.getElementById('papers-list');
  el.innerHTML = '<div class="loading">Loading...</div>';

  try {
    const papers = await api('/api/papers');

    if (!papers.length) {
      el.innerHTML = '<p style="color:var(--gray);font-size:13px">No papers found in ideas-workbench.</p>';
      return;
    }

    // Render each paper as a row with an Open button
    el.innerHTML = papers.map(p => `
      <div style="padding:10px 0;border-bottom:1px solid #eee;display:flex;align-items:center;gap:12px">
        <span style="font-weight:500">${p}</span>
        <button class="btn btn-secondary" style="padding:4px 10px;font-size:12px"
          onclick="openPaper('${p}')">Open</button>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = `<div class="msg msg-err">Error: ${e.message}</div>`;
  }
}

/**
 * Open a paper from the Papers list directly into the QA & Publish panel.
 * Switches to the Publish panel and loads the selected paper.
 *
 * @param {string} slug - the paper slug to open
 */
function openPaper(slug) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelector('[data-panel="publish"]').classList.add('active');

  // Show the publish panel, hide all others
  document.querySelectorAll('[id^="panel-"]').forEach(p => p.classList.add('hidden'));
  document.getElementById('panel-publish').classList.remove('hidden');

  // Pre-fill the slug input and trigger load
  document.getElementById('pub-slug').value = slug;
  loadPaper();
}


// ── Boot ──────────────────────────────────────────────────────────────────────
// Start the app when the page finishes loading
init();
