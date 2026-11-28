# 13 — Customer screens in OWL (v1.1)

Why the portal pages are built the way they are. Spec: US-16, BR-59, BR-60.

## One API for both clients

The pages do not get their own endpoints: every page is an OWL component that reads and writes
through the Story 12 API (`/api/v1/`). So the pages can show nothing the API would not give the
same customer with a key, and there is one place to secure, test and document.

## The auth method: a key, or the session + a CSRF header

Odoo 19's `auth="bearer"` reads the key from the `Authorization` header and, without a key, accepts
a session only for a top-level page navigation (`Sec-Fetch-Mode: navigate`, …). A `fetch()` from a
page is not a navigation, so it was refused. Three ways out were compared; the maintainer chose
the first:

1. **Our own auth method on the same routes (chosen).** `ir.http` picks the method by the route's
   `auth=` value (`_auth_method_<name>`), so `auth="re_portal_api"` is a few lines in
   `models/ir_http.py`:
   - an `Authorization` header present → Odoo's `_auth_method_bearer`, unchanged, so API-key clients
     and the Story 12 tests see no difference;
   - otherwise the session's user, refused with 401 when there is none (or it is the public user);
   - for any method but GET and HEAD, the session's **CSRF token** must be in the
     `X-CSRF-Token` header (`request.validate_csrf`), else **403** `csrf_failed`. OPTIONS too:
     Odoo adds it to every route and, as the routes have no CORS, sends it to the endpoint.
2. Separate jsonrpc routes for the pages: every endpoint twice, two sets of tests.
3. An API key stored in the browser: anyone who steals it (an extension, a shared computer) can use
   it anywhere until it is revoked.

**Why the CSRF header protects the POST.** A malicious site can make the customer's browser send
a request to our server with the session cookie, but it cannot read our pages, so it cannot know
the token. A custom header also cannot be sent cross-site without a CORS preflight, which Odoo does
not allow. Reads (GET) are safe without the token: they change nothing, and the other site cannot
read the answer (same-origin policy). The token is the one Odoo already prints in every page
(`odoo.csrf_token`), bound to the session: another session's token is refused (a test checks it).
Odoo's own CSRF check reads a `csrf_token` **form field**, which a cross-site form can carry if it
has the token; the routes keep `csrf=False` and the auth method checks only the header.

The refusal is a `werkzeug` `Forbidden`, not a `UserError`: Odoo logs a warning for each
`UserError` that leaves a request, and a warning fails CI. `_handle_error` turns it into the API's
JSON error, like the 401.

## OWL inside Odoo's portal, not a separate app

Each page is a normal portal page (`portal.portal_layout`: header, breadcrumbs, the customer's
language and company) holding one `<owl-component name="…" props="…"/>`. Odoo 19 mounts it with
the component registered under `public_components`
(`web/static/src/public/public_component_interaction.js`). No build step, no second server, the
login and the session are Odoo's. The server passes only what a page needs to start (the projects
for the filter, the unit types, the contract id); everything else is loaded through the API.

One page per screen (units, reservations, contracts, one contract) rather than one page with
client-side routing: each has a real URL, Odoo's breadcrumbs work, and the back button behaves.

**The API service.** `real_estate_eg_portal.api` (`static/src/js/api_service.js`) is the only code
that talks to the server: it adds `credentials: "same-origin"`, the CSRF header on POST, parses the
BR-58 error into an `ApiError` (status, code, message), and the components show its message as is.
The request form therefore needs no validation of its own: the server's messages (invalid national
ID, unit no longer available, too many open requests) appear in the dialog.

**The request form** is a small modal component (`ReserveForm`) that `UnitList` shows itself
(Bootstrap classes), not through Odoo's dialog service: it keeps the component independent of which overlay services the frontend
starts.

## Who sees what

- `/my/real-estate/...` routes are `auth="user"`: a visitor is sent to the login page by Odoo.
- They are for **portal users** only, as the API (BR-55): a staff user is sent back to `/my`, and
  the home cards are shown only to portal users. Their counters return 0 for staff.
- The contract page looks the contract up **as the customer**: another customer's contract is not
  found (404), the same answer as the API.
- Counts on the cards come from `search_count` as the customer, so the record rules apply.

## Testing without a browser

CI runs Odoo in the official Docker image, which has no Chrome. Odoo's browser tests (tours,
`browser_js`) log `Chrome executable not found` as a **WARNING** when Chrome is missing, and any
warning fails CI, so this story has no tour. CI checks instead, with `HttpCase` and real sessions:
the auth method in every case (session reads, POST without / with a wrong / with another session's
token, anonymous, staff, key unchanged), each page and who may open it, the home counters, and that
the frontend bundles served to the page contain the components, their templates and the compiled
styles. What runs in the browser (the form, the lists, the pager) is checked by hand on a local
Odoo before the release. Adding Chrome to the CI image would make tours possible; it is a separate
decision (bigger image, slower CI).
