"""US-16: the customer's pages under /my/real-estate/ (BR-60).

Each page is Odoo's portal layout with one OWL component in it
(``<owl-component>``, mounted by Odoo's frontend). The component reads and
writes through the /api/v1/ API with the browser session (BR-59), so these
routes only check who is asking and pass the few values a page needs to start.
"""

import json

from werkzeug.exceptions import NotFound

from odoo.http import request, route

from odoo.addons.portal.controllers.portal import CustomerPortal

# BR-60: the counters of the cards on the portal home page (/my).
RESERVATION_COUNTER = "re_reservation_count"
CONTRACT_COUNTER = "re_contract_count"


class RealEstatePortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        """BR-60: the number of the customer's reservations and contracts on
        their cards. Counted as the customer, so the record rules apply; a
        card with 0 stays hidden, as Odoo's own cards."""
        values = super()._prepare_home_portal_values(counters)
        env = request.env
        is_customer = env.user._is_portal()
        if RESERVATION_COUNTER in counters:
            values[RESERVATION_COUNTER] = (
                env["real.estate.reservation"].search_count([]) if is_customer else 0
            )
        if CONTRACT_COUNTER in counters:
            values[CONTRACT_COUNTER] = (
                env["real.estate.contract"].search_count([]) if is_customer else 0
            )
        return values

    def _re_page(self, page_name, component, props=None, **values):
        """One portal page holding one OWL component. The pages are for
        customers (BR-55): any other user is sent back to /my."""
        if not request.env.user._is_portal():
            return request.redirect("/my")
        page = self._prepare_portal_layout_values()
        page.update(
            values,
            page_name=page_name,
            re_component=component,
            re_props=json.dumps(props or {}),
        )
        return request.render("real_estate_eg_portal.portal_my_real_estate", page)

    @route(
        "/my/real-estate/units", type="http", auth="user", website=True, readonly=True
    )
    def portal_my_re_units(self, **kwargs):
        """The available units, with the request dialog (AC-16.2)."""
        env = request.env
        if not env.user._is_portal():
            return request.redirect("/my")
        Unit = env["real.estate.unit"]
        # The filter offers the projects that have an available unit, read as
        # the customer (the unit record rule applies).
        projects = env["real.estate.project"].union(
            *(
                project
                for (project,) in Unit._read_group(
                    [("state", "=", "available")], ["project_id"]
                )
            )
        )
        return self._re_page(
            "re_units",
            "real_estate_eg_portal.UnitList",
            {
                "projects": [
                    {"id": project.id, "name": project.name}
                    for project in projects.sorted("name")
                ],
                "unitTypes": self._unit_types(),
            },
        )

    @route(
        "/my/real-estate/units/<int:unit_id>",
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_re_unit(self, unit_id, **kwargs):
        """BR-63: one unit's page. A unit the customer may not see (e.g. on
        hold for someone else) is not found, read as the customer."""
        env = request.env
        if not env.user._is_portal():
            return request.redirect("/my")
        unit = env["real.estate.unit"].search([("id", "=", unit_id)])
        if not unit:
            raise NotFound()
        return self._re_page(
            "re_unit",
            "real_estate_eg_portal.UnitDetail",
            {"unitId": unit.id, "unitTypes": self._unit_types()},
            re_unit=unit,
        )

    @staticmethod
    def _unit_types():
        env = request.env
        return [
            {"value": value, "label": label}
            for value, label in env["real.estate.unit"]
            ._fields["unit_type"]
            ._description_selection(env)
        ]

    @route(
        "/my/real-estate/reservations",
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_re_reservations(self, **kwargs):
        return self._re_page("re_reservations", "real_estate_eg_portal.ReservationList")

    @route(
        "/my/real-estate/contracts",
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_re_contracts(self, **kwargs):
        return self._re_page("re_contracts", "real_estate_eg_portal.ContractList")

    @route(
        "/my/real-estate/contracts/<int:contract_id>",
        type="http",
        auth="user",
        website=True,
        readonly=True,
    )
    def portal_my_re_contract(self, contract_id, **kwargs):
        """One contract and its installment schedule. A contract that is not
        the customer's is not found (BR-58), read as the customer."""
        if not request.env.user._is_portal():
            return request.redirect("/my")
        contract = request.env["real.estate.contract"].search(
            [("id", "=", contract_id)]
        )
        if not contract:
            raise NotFound()
        return self._re_page(
            "re_contract",
            "real_estate_eg_portal.ContractDetail",
            {"contractId": contract.id},
            re_contract=contract,
        )
