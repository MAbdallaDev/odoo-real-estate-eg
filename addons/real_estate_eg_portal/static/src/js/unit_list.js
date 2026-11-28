import {Component, markup, onWillStart, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Pager, formatDate, formatMoney} from "./common";

/**
 * US-16 / AC-16.2: the request form, shown over the unit list or the unit
 * page. It sends POST /api/v1/reservations (BR-57) and shows the server's
 * refusal as is.
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

/** The message shown once a request is sent (list and unit page). */
export class RequestSent extends Component {
  static template = "real_estate_eg_portal.RequestSent";
  static props = {reservation: Object};
}

/**
 * AC-16.2 / US-17: the available units, filtered, with a photo each (BR-61),
 * and the projects' banners on top.
 */
export class UnitList extends Component {
  static template = "real_estate_eg_portal.UnitList";
  static components = {Pager, ReserveForm, RequestSent};
  static props = {projects: Array, unitTypes: Array};

  setup() {
    this.api = useService("real_estate_eg_portal.api");
    this.formatMoney = formatMoney;
    this.state = useState({
      filters: {project_id: "", unit_type: "", bedrooms: ""},
      page: 1,
      units: [],
      banners: [],
      meta: {page: 1, limit: 12, total: 0},
      loading: true,
      error: "",
      selected: null,
      sent: null,
    });
    onWillStart(() => Promise.all([this.load(), this.loadBanners()]));
  }

  unitTypeLabel(value) {
    const type = this.props.unitTypes.find((t) => t.value === value);
    return type ? type.label : value;
  }

  async loadBanners() {
    try {
      this.state.banners = (await this.api.get("projects", {limit: 6})).data;
    } catch {
      // The banners are an extra: the list works without them.
      this.state.banners = [];
    }
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

  filterProject(project) {
    this.state.filters.project_id = String(project.id);
    this.onFilter();
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

/** BR-62: how often a plan's installments fall due. */
export function frequencyLabel(frequency) {
  return (
    {
      monthly: _t("every month"),
      quarterly: _t("every 3 months"),
      semi_annual: _t("every 6 months"),
      annual: _t("every year"),
    }[frequency] || ""
  );
}

/**
 * US-17 / BR-63: one unit's page: photos, facts, floor plan, the project's
 * plans worked out on its price, the project, and the request form.
 */
export class UnitDetail extends Component {
  static template = "real_estate_eg_portal.UnitDetail";
  static components = {ReserveForm, RequestSent};
  static props = {unitId: Number, unitTypes: Array};

  setup() {
    this.api = useService("real_estate_eg_portal.api");
    this.formatMoney = formatMoney;
    this.formatDate = formatDate;
    this.frequencyLabel = frequencyLabel;
    this.state = useState({
      unit: null,
      photo: 0,
      plan: 0,
      loading: true,
      error: "",
      requesting: false,
      sent: null,
    });
    onWillStart(() => this.load());
  }

  async load() {
    try {
      this.state.unit = await this.api.get(`units/${this.props.unitId}`);
    } catch (error) {
      this.state.error = error.message;
    } finally {
      this.state.loading = false;
    }
  }

  get unitTypeLabel() {
    const value = this.state.unit.unit_type;
    const type = this.props.unitTypes.find((t) => t.value === value);
    return type ? type.label : value;
  }

  /** The project's description: HTML sanitized by Odoo (Html field). */
  get description() {
    const html = this.state.unit.project.description;
    return html ? markup(html) : "";
  }

  get currentPlan() {
    return this.state.unit.plans[this.state.plan];
  }

  /** The cheapest start among the plans, for the summary box. */
  get lowestDownPayment() {
    const plans = this.state.unit.plans;
    return plans.length ? Math.min(...plans.map((p) => p.down_payment)) : null;
  }

  /** BR-62: the share of each part of a plan's total, for the bar. */
  planShares(plan) {
    const total = plan.total || 1;
    const installments = plan.total - plan.down_payment - plan.maintenance;
    return [
      ["o_re_bar_down", (100 * plan.down_payment) / total],
      ["o_re_bar_installments", (100 * installments) / total],
      ["o_re_bar_maintenance", (100 * plan.maintenance) / total],
    ];
  }

  showPhoto(index) {
    this.state.photo = index;
  }

  showPlan(index) {
    this.state.plan = index;
  }

  openRequest() {
    this.state.sent = null;
    this.state.requesting = true;
  }

  closeRequest() {
    this.state.requesting = false;
  }

  onSent(reservation) {
    this.state.requesting = false;
    this.state.sent = reservation;
    window.scrollTo({top: 0});
  }
}

const components = registry.category("public_components");
components.add("real_estate_eg_portal.UnitList", UnitList);
components.add("real_estate_eg_portal.UnitDetail", UnitDetail);
