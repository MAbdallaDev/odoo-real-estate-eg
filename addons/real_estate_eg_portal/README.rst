=====================================================
Real Estate Installments (Egypt): Customer Portal API
=====================================================

A JSON REST API under ``/api/v1/`` for the customers of a developer that uses
``real_estate_eg``: they list the available units, ask for a reservation and
follow their reservations, contracts and installments.

Customers are Odoo **portal users** linked to their contact. They call the API
with an Odoo **API key** (``Authorization: Bearer <key>``), made on their
``/my/security`` page once the setting *Customer Account: API keys* is on, or by
an administrator. Every read goes through Odoo access rights and record rules,
so a customer sees only their own data.

The OpenAPI description is served at ``/api/v1/openapi.json``.
Business rules: US-15, BR-55 to BR-58 in ``docs/business-requirements.md``.

License
=======

LGPL-3
