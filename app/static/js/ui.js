/** Read the value of a form element by id. */
const val = id => document.getElementById(id).value;

/** Read the checked state of a checkbox by id. */
const checked = id => document.getElementById(id).checked;

/** Set the value of a form element by id (no-op if element not found). */
const setValue = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };

/** Set the checked state of a checkbox by id (no-op if element not found). */
const setChecked = (id, v) => { const el = document.getElementById(id); if (el) el.checked = v; };

/** Return today's date as YYYY-MM-DD. */
const today = () => new Date().toISOString().slice(0, 10);

/** Map a gate name to its canonical version string per the spec gate model. */
function gateToVersion(gate) {
  return {
    alpha:       'v0.1-alpha',
    exploratory: 'v0.1-exploratory',
    draft:       'v0.2-draft',
    review:      'v0.3-review',
    published:   'v1.0',
  }[gate] || 'v0.1-exploratory';
}

/** Render a status message into a container element. type: ok | err | info | warn */
function setMsg(id, text, type) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="msg msg-${type}">${text}</div>`;
}

/** Populate a <select> element with an array of string options. */
function populateSelect(id, items) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = items.map(i => `<option value="${i}">${i}</option>`).join('');
}
