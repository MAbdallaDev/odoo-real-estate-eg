import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {
  Pager,
  contractState,
  formatDate,
  formatMoney,
  installmentState,
  reservationState,
} from "./common";

/**
 * US-16: the customer's own records, read through the API as the customer
 * (BR-56): reservations (AC-16.3), contracts and one contract's schedule
 * (AC-16.4).
 */

class ApiList extends Component {
  static props = {};
  /** The API path of the list and its page size. */
  path = "";
  limit = 20;

  setup() {
    this.api = useService("real_estate_eg_portal.api");
    this.formatMoney = formatMoney;
    this.formatDate = formatDate;
    this.state = useState({
      page: 1,
      records: [],
      meta: {page: 1, limit: this.limit, total: 0},
      loading: true,
      error: "",
      ...this.initialState(),
    });
    onWillStart(() => this.load());
  }

  initialState() {
    return {};
  }

  params() {
    return {};
  }

  async load() {
    const state = this.state;
    state.loading = true;
    state.error = "";
    try {
      const result = await this.api.get(this.path, {
        ...this.params(),
        page: state.page,
        limit: this.limit,
      });
      state.records = result.data;
      state.meta = result.meta;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.loading = false;
    }
  }

  onPage(page) {
    this.state.page = page;
    this.load();
  }
}

/** AC-16.3: my reservations and where each one stands. */
export class ReservationList extends ApiList {
  static template = "real_estate_eg_portal.ReservationList";
  static components = {Pager};
  path = "reservations";
  reservationState = reservationState;

  initialState() {
    return {stateFilter: ""};
  }

  params() {
    return {state: this.state.stateFilter};
  }

  get stateOptions() {
    return [
      "requested",
      "agent_confirmed",
      "reserved",
      "converted",
      "rejected",
      "expired",
    ].map((value) => ({value, label: reservationState(value).label}));
  }

  onFilter() {
    this.state.page = 1;
    this.load();
  }
}

/** AC-16.4: my contracts, with what is paid and what is left. */
export class ContractList extends ApiList {
  static template = "real_estate_eg_portal.ContractList";
  static components = {Pager};
  path = "contracts";
  contractState = contractState;

  paidPercent(contract) {
    return contract.price
      ? Math.round((100 * contract.amount_paid) / contract.price)
      : 0;
  }
}

/** AC-16.4: one contract and its installment schedule. */
export class ContractDetail extends ApiList {
  static template = "real_estate_eg_portal.ContractDetail";
  static components = {Pager};
  static props = {contractId: Number};
  path = "installments";
  limit = 50;
  contractState = contractState;
  installmentState = installmentState;

  initialState() {
    return {contract: null, overdueOnly: false, overdueTotal: 0};
  }

  params() {
    return {
      contract_id: this.props.contractId,
      overdue: this.state.overdueOnly ? "1" : "",
    };
  }

  async load() {
    if (!this.state.contract) {
      try {
        this.state.contract = await this.api.get(`contracts/${this.props.contractId}`);
        const overdue = await this.api.get("installments", {
          contract_id: this.props.contractId,
          overdue: "1",
          limit: 100,
        });
        this.state.overdueTotal = overdue.data.reduce(
          (total, line) => total + line.amount_residual,
          0
        );
      } catch (error) {
        this.state.error = error.message;
        this.state.loading = false;
        return;
      }
    }
    return super.load();
  }

  onToggleOverdue() {
    this.state.overdueOnly = !this.state.overdueOnly;
    this.state.page = 1;
    this.load();
  }
}

const components = registry.category("public_components");
components.add("real_estate_eg_portal.ReservationList", ReservationList);
components.add("real_estate_eg_portal.ContractList", ContractList);
components.add("real_estate_eg_portal.ContractDetail", ContractDetail);
