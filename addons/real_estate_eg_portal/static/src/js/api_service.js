import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

/**
 * US-16 / BR-59: the one door of the portal pages to the /api/v1/ API.
 *
 * Every call carries the browser's session cookie (same origin). A call that
 * changes data also sends the page's CSRF token in the X-CSRF-Token header;
 * the server refuses it without one. No API key is ever kept in the browser.
 */

const API_ROOT = "/api/v1/";

/** BR-58: an API error, with its HTTP status and its error code. */
export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function call(method, path, {params, body} = {}) {
  const url = new URL(API_ROOT + path, window.location.origin);
  for (const [name, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(name, value);
    }
  }
  const headers = {Accept: "application/json"};
  const init = {method, headers, credentials: "same-origin"};
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRF-Token"] = odoo.csrf_token;
    init.body = JSON.stringify(body || {});
  }
  let response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(0, "network_error", _t("The server cannot be reached."));
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (data && data.error) || {};
    throw new ApiError(
      response.status,
      error.code || "error",
      error.message || response.statusText
    );
  }
  return data;
}

export const realEstateApiService = {
  start() {
    return {
      /** GET a list ({data, meta}) or one record. */
      get: (path, params) => call("GET", path, {params}),
      /** POST a JSON body; answers the created record. */
      post: (path, body) => call("POST", path, {body}),
    };
  },
};

registry.category("services").add("real_estate_eg_portal.api", realEstateApiService);
