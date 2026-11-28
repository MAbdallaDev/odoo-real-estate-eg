# 12 — Customer portal REST API (v1.1)

Why the API is built the way it is. Spec: US-15, BR-55–BR-58.

## A separate addon

`real_estate_eg_portal` depends on `real_estate_eg` and `portal`. The backend installs and works
without it, and not one file of `real_estate_eg` changes, so the v1 and Story 11 suites prove the
backend is untouched. The Odoo Apps release script copies only `real_estate_eg`; the portal addon
reaches the store only if that script is changed on purpose.

## Authentication: Odoo API keys, not JWT

Odoo 19 has `auth="bearer"` routes: Odoo reads `Authorization: Bearer <key>`, checks the key in
`res.users.apikeys` (stored hashed, with an expiry date, revocable from the user's preferences or
the portal's `/my/security` page) and runs the request as the key's owner. No library, no signing
secret, no token code of ours. JWT was rejected for the opposite reasons.

`auth="bearer"` also accepts a logged-in browser session, but only for a top-level page navigation
(Odoo checks the `Sec-Fetch-*` headers, against CSRF). A `fetch()` from a page does not pass that
check, so Story 13 must choose how its OWL screens call the API.

The API is for customers: the `api_endpoint` wrapper answers 403 to any user who is not a portal
user. A staff key therefore cannot use the API, even though it is valid in Odoo.

## Security through Odoo, not around it

Every read runs as the customer. Portal users get **read** access to projects, units,
reservations, contracts and schedule lines, and record rules (portal group only) limit the rows to
their own, with the domain Odoo uses for sale orders: `child_of [user.commercial_partner_id.id]`.
The unit rule shows the available units plus the units the customer has an **open** reservation or
a contract on, so a unit on hold for someone else disappears (BR-50), also once the customer's own
request on it is rejected or expired.

Because the boundary is the ACL and the rules, it also holds outside this API: a portal user who
calls Odoo's own JSON-RPC sees exactly the same rows, read only. Staff rules have no portal group,
so they are unchanged (a test checks that the agent still sees both customers' contracts).

Through that RPC a customer reads **every field** of their own rows, not only what the API
serializes. Most of it is theirs to know (their price, their cancellation reason, their agent).
Two fields are internal and get `groups="base.group_user"` in this addon: the reservation's
`note` (the agent's call notes) and the contract's `at_risk` flag (BR-31). Every employee is in
`base.group_user`, so staff see no change. Projects have no portal rule: name, location, agent and
reservation amount are public information.

A record the customer may not read answers **404, not 403**: the answer must not reveal that
customer B's contract 42 exists.

**The chatter.** Reservations and contracts let anyone who can read them post on their chatter
(`_mail_post_access = "read"`, so collections officers can log notes). With read access, customers
would have been able to post into the staff chatter too. The addon overrides Odoo's hook
`_mail_get_operation_for_mail_message_operation`: for a user who is not an employee, posting needs
**write** access, which customers do not have. Staff keep the `read` rule. Customers can still read
the non-internal messages of their own records and open their attachments (their own documents);
internal notes stay hidden by Odoo's own mail rules.

## The one `sudo()`

Customers have no create right on reservations, so `POST /reservations` creates the request as
superuser. Before that, as the customer, it checks that the unit is visible and available, and it
counts the customer's open reservations (one per unit, 5 in all), after locking the customer's
contact row so two requests sent at the same moment cannot both pass the counts. It passes only the customer,
the unit, the note and the identity fields; the model's own `create()` still refuses a unit that is
not available (BR-49), assigns the project's agent and schedules the to-do (BR-51). The reservation
is then read back as the customer, through the record rule. The customer is not made a follower
(`mail_create_nosubscribe`), so staff chatter sends them no e-mail.

## Identity on the request, not on the contact

The decision said the portal collects nationality and national ID or passport. Writing them to the
contact would need a second `sudo()` (portal users cannot edit contacts) and the contact's
uniqueness check (BR-46) would tell a stranger which national IDs are already known, and to whom.
So the values are stored on the request (three read-only fields shown to staff on the reservation
form); the agent checks them against the card when calling the customer and copies them to the
contact. The national ID is still checked with the contact's own BR-06 rule.

## Errors: JSON, the right code, no traceback

Two layers:

1. The `api_endpoint` wrapper answers the expected errors itself: its own `ApiError`
   (400 / 404 / 409 / 422), `AccessError` and `MissingError` (404), `UserError` from the business
   rules (422). It runs the endpoint in a **savepoint**, so a refused request leaves nothing behind.
   It catches them, rather than letting them leave the controller, because Odoo logs a warning for
   every `UserError` that leaves a controller, and a warning in the log fails CI.
2. `ir.http._handle_error`, inherited for `/api/v1/` paths only, turns what happens outside the
   endpoint into JSON: authentication (401 with `WWW-Authenticate: Bearer`), unknown paths (404)
   and bugs (500, logged by Odoo with the traceback; the client gets only "Internal server error").

## Pagination and OpenAPI

Lists take `page` (1–10,000) and `limit` (1–100, default 20) and answer `{"data": [...], "meta": {"page",
"limit", "total"}}`. The OpenAPI 3 file is a Python dict in `controllers/openapi.py`, served
publicly (it holds no data); a test compares its paths with the routing map, so a new endpoint
without documentation fails CI.
