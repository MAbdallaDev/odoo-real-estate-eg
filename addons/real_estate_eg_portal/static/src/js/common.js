import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";

/** US-16: what the portal pages share: formats, labels, the pager. */

function locale() {
  // A lang Intl does not know (e.g. "sr@latin") would throw: use the default.
  const lang = (document.documentElement.lang || "").replace("_", "-");
  try {
    return Intl.NumberFormat.supportedLocalesOf(lang).length ? lang : undefined;
  } catch {
    return undefined;
  }
}

/** An amount in whole units, e.g. "EGP 6,525,000". */
export function formatMoney(amount, currency) {
  const number = new Intl.NumberFormat(locale(), {maximumFractionDigits: 0}).format(
    amount || 0
  );
  return currency ? `${currency} ${number}` : number;
}

/** A date or datetime from the API ("2026-11-28" or "2026-11-28 10:00:00"). */
export function formatDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return date.toLocaleDateString(locale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** BR-48: a reservation's state, its label and its badge colour. */
export function reservationState(state) {
  const states = {
    requested: [_t("Requested"), "text-bg-secondary"],
    agent_confirmed: [_t("Agent Confirmed"), "text-bg-info"],
    reserved: [_t("Reserved"), "text-bg-warning"],
    converted: [_t("Converted"), "text-bg-success"],
    rejected: [_t("Rejected"), "text-bg-light border"],
    expired: [_t("Expired"), "text-bg-light border"],
  };
  const [label, badge] = states[state] || [state, "text-bg-light"];
  return {label, badge};
}

/** BR-09: a contract's state. */
export function contractState(state) {
  const states = {
    draft: [_t("Draft"), "text-bg-secondary"],
    confirmed: [_t("Confirmed"), "text-bg-primary"],
    delivered: [_t("Delivered"), "text-bg-info"],
    closed: [_t("Closed"), "text-bg-success"],
    cancelled: [_t("Cancelled"), "text-bg-light border"],
  };
  const [label, badge] = states[state] || [state, "text-bg-light"];
  return {label, badge};
}

/** A schedule line: paid, overdue or still to pay. */
export function installmentState(line) {
  if (line.state === "cancelled") {
    return {label: _t("Cancelled"), badge: "text-bg-light border"};
  }
  if (line.amount_residual <= 0) {
    return {label: _t("Paid"), badge: "text-bg-success"};
  }
  if (line.is_overdue) {
    return {label: _t("Overdue"), badge: "text-bg-danger"};
  }
  if (line.amount_paid > 0) {
    return {label: _t("Partly paid"), badge: "text-bg-warning"};
  }
  return {label: _t("To pay"), badge: "text-bg-light border"};
}

/** BR-58: Previous / Next over a paginated list ({page, limit, total}). */
export class Pager extends Component {
  static template = "real_estate_eg_portal.Pager";
  static props = {meta: Object, onChange: Function};

  get pageCount() {
    return Math.max(1, Math.ceil(this.props.meta.total / this.props.meta.limit));
  }
}
