import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Pager, formatMoney} from "./common";

/**
 * US-16 / AC-16.2: the request form, shown over the unit list. It sends
 * POST /api/v1/reservations (BR-57) and shows the server's refusal as is.
 */
export class ReserveForm extends Component {
  static template = "real_estate_eg_portal.ReserveForm";
  static props = {unit: Object, onSent: Function, onClose: Function};

  setup() {
    this.api = useService("real_estate_eg_portal.api");
    this.formatMoney = formatMoney;
    this.state = useState({
      nationality: "egyptian",
      nationalId: "",
      passport: "",
      note: "",
      sending: false,
      error: "",
    });
  }

  async send() {
    const state = this.state;
    state.sending = true;
    state.error = "";
    const egyptian = state.nationality === "egyptian";
    try {
      const reservation = await this.api.post("reservations", {
        unit_id: this.props.unit.id,
        nationality: state.nationality,
        national_id: egyptian ? state.nationalId.trim() : "",
        passport_number: egyptian ? "" : state.passport.trim(),
        note: state.note.trim(),
      });
      this.props.onSent(reservation);
    } catch (error) {
      state.error = error.message;
    } finally {
      state.sending = false;
    }
  }
}

/** AC-16.2: the available units, filtered, with a Request button each. */
export class UnitList extends Component {
  static template = "real_estate_eg_portal.UnitList";
  static components = {Pager, ReserveForm};
  static props = {projects: Array, unitTypes: Array};

  setup() {
    this.api = useService("real_estate_eg_portal.api");
    this.formatMoney = formatMoney;
    this.state = useState({
      filters: {project_id: "", unit_type: "", bedrooms: ""},
      page: 1,
      units: [],
      meta: {page: 1, limit: 12, total: 0},
      loading: true,
      error: "",
      selected: null,
      sent: null,
    });
    onWillStart(() => this.load());
  }

  unitTypeLabel(value) {
    const type = this.props.unitTypes.find((t) => t.value === value);
    return type ? type.label : value;
  }

  async load() {
    const state = this.state;
    state.loading = true;
    state.error = "";
    try {
      const result = await this.api.get("units", {
        ...state.filters,
        page: state.page,
        limit: 12,
      });
      state.units = result.data;
      state.meta = result.meta;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  onFilter() {
    this.state.page = 1;
    this.load();
  }

  onPage(page) {
    this.state.page = page;
    this.load();
  }

  open(unit) {
    this.state.sent = null;
    this.state.selected = unit;
  }

  close() {
    this.state.selected = null;
  }

  onSent(reservation) {
    this.state.selected = null;
    this.state.sent = reservation;
    window.scrollTo({top: 0});
    this.load();
  }
}

registry.category("public_components").add("real_estate_eg_portal.UnitList", UnitList);
