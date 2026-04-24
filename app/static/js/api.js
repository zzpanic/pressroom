/**
 * Fetch wrapper for all API calls.
 * Throws an Error with status + body text on non-2xx responses.
 */
async function api(url, options = {}) {
  const r = await fetch(url, options);
  if (!r.ok) {
    const err = await r.text();
    throw new Error(`${r.status}: ${err}`);
  }
  return r.json();
}
