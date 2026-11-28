# 14 — Unit photos, plans offered and unit page (v1.1)

Why the unit page is built the way it is. Spec: US-17, BR-61–BR-63.

## Everything in the portal addon

Photos, the floor plan, the project's description and the plans offered are needed only to show
units to customers, so `real_estate_eg_portal` adds them with `_inherit` on the project and the
unit, and a new model `real.estate.image`. `real_estate_eg` installs and works without them, and
none of its files change. Staff fill them on a new tab, *Customer Portal*, of the project and unit
forms.

## One photo model for projects and units

`real.estate.image` (with `image.mixin`, so Odoo stores the sizes 1920 to 128) belongs to exactly
one project or one unit (a constraint). Order is a `sequence`; the first photo is the cover. One
model rather than two keeps one ACL, one rule, one endpoint and one form. A unit without photos
shows its project's: developers usually photograph the model flat or the compound, not each unit,
and a manager should not have to upload the same photos 500 times.

The floor plan is a single image field on the unit: in practice it is the engineer's drawing,
exported as an image. Drawing it from room data would be a project of its own for little gain.

## Who may see a photo

A project's photos are public, like the project itself (BR-56). A unit's photos must not show a
unit the customer may not see (a unit on hold for someone else, BR-50), so the photo rule for
portal users is the **unit rule copied through `unit_id`**. The two must stay the same; the rule's
comment says so, as the unit rule's comment does for `OPEN_STATES`. The floor plan is a field of
the unit, so the unit rule covers it directly. Photos also get the multi-company rule the other
real-estate models have, on a stored `company_id` taken from the unit or project.

Managers add photos; agents, collections and accounting users read them; customers read them.

## Serving the images through the API

Odoo's `/web/image/...` would work for the portal pages (it reads as the session's user), but not
for a client with an API key, which `/web/image` does not accept. So the API serves them:
`/api/v1/images/<id>?size=1024` and `/api/v1/units/<id>/floor-plan`. They use the same auth method
as the rest of the API (key or session, BR-59), look the record up as the customer (not found
otherwise, like every other record), and answer with `ir.binary._get_image_stream_from()`, which
handles the mimetype, the ETag and the cache headers. A record without an image is a 404 instead of
Odoo's placeholder, so a client can tell. `size` takes only the sizes `image.mixin` stores.

The JSON gives URLs, not image data: a list of units stays small and the browser loads and caches
each photo once.

## Plans offered and their preview

Plan templates were not linked to projects; a contract's plan is chosen by the agent. To show a
customer only what a project is sold with, a project now lists **Plans Offered** (a many2many to
plan templates; the maintainer chose this over showing every plan). Portal users get read access
to plan templates: their terms are what the page shows anyway.

The preview runs `compute_schedule()`, the same pure function the contract's **Generate schedule**
runs (BR-15–BR-18), on the unit's list price with today as the contract date. So the down payment,
the installment, the last installment that absorbs the rounding and the total are exactly what a
contract signed today would get; a test generates a real contract schedule at the same price and
compares. Nothing is stored. A plan that would give a line of 0 or less at that price (the case the
generator refuses) is left out.

## The pages

- The units page gets the projects' **banners** (from `/api/v1/projects`: projects with an
  available unit, cover, count; a click filters the list) and a **cover photo** on each card, with
  *View details* and *Request*.
- The unit page `/my/real-estate/units/<id>` is one OWL component, `UnitDetail`, loading
  `/api/v1/units/<id>`: gallery, facts, floor plan, plan tabs with a bar of down payment /
  installments / maintenance, the project (its description is HTML from an `Html` field, sanitized
  by Odoo, rendered with OWL's `markup`), and a box with the price, the lowest down payment, the
  reservation amount and the request form shared with the list (`ReserveForm`, `RequestSent`).
- The page route looks the unit up as the customer, so a unit held for someone else is not found,
  as in the API.

As in Story 13, CI has no Chrome: the tests check the API, the rights and the page's server side;
the gallery and the tabs are checked by hand on a local Odoo.
