=================================================
Real Estate Installments (Egypt): Customer Portal
=================================================

Customer pages in Odoo's portal and a JSON REST API under ``/api/v1/`` for the customers of a developer that uses
``real_estate_eg``: they list the available units, ask for a reservation and
follow their reservations, contracts and installments.

Customers are Odoo **portal users** linked to their contact. They call the API
with an Odoo **API key** (``Authorization: Bearer <key>``), made on their
``/my/security`` page once the setting *Customer Account: API keys* is on, or by
an administrator. Every read goes through Odoo access rights and record rules,
so a customer sees only their own data.

The OpenAPI description is served at ``/api/v1/openapi.json``.

The same customers also get pages in Odoo's portal, linked from their portal
home page (``/my``): the available units with a reservation request form
(``/my/real-estate/units``), their reservations, their contracts and each
contract's installment schedule. The pages are OWL components that call the
same API with the browser session instead of a key; a request that changes data
also sends the page's CSRF token in the ``X-CSRF-Token`` header.

Business rules: US-15, US-16, BR-55 to BR-60 in ``docs/business-requirements.md``.

License
=======

LGPL-3
