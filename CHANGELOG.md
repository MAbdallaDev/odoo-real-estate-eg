# Changelog

All notable changes to `real_estate_eg` are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow Odoo's module
numbering: `19.0.x.y.z` in the manifest, tagged `vx.y.z` in git.

## [1.0.0] - 2026-11-25

First release, for Odoo 19.0 Community. Every feature traces to the business requirements
(`docs/business-requirements.md`) and was built in its own reviewed pull request, with a
plan in `.squad/` and a design note in `docs/design-notes/`.

### Added

- **Environment** (Story 01): Odoo 19 from source in a venv, `make` targets, the OCA
  pre-commit stack, CI with Postgres 16 and the official Odoo 19 image, and a rule that a
  test run fails on any warning in the log.
- **Core models** (Story 02): projects, units, contracts with states draft → confirmed →
  delivered → closed or cancelled, contract references from a sequence, one live contract
  per unit enforced in the database, customers with nationality and national ID, groups and
  access rights for agents, managers, collections officers and accountants (US-01, US-09,
  US-10, US-11).
- **Payment plans and schedules** (Story 03): plan templates and a schedule generator in
  whole pounds, the rounding difference on the last line, the maintenance deposit as its
  own line (US-02).
- **Accounting link** (Story 04): one customer invoice per line on its due date, posted to
  customer advances or maintenance deposits with no tax; paid and outstanding read from
  accounting; closing paid contracts; retention and credit notes on cancellation (US-03,
  US-12).
- **Late fees** (Story 05): a nightly job flags overdue lines and computes late fees from the
  payment history (1 % a month, simple, capped at 10 %, after a 7-day grace), so re-running
  it never double-charges; an at-risk flag; billing late fees (US-05).
- **Record rules** (Story 06): agents see only their own contracts and schedules;
  multi-company rules on every model (US-06).
- **Collections** (Story 07): due-this-month, overdue, aging pivot and at-risk screens, with
  their query plans measured on one million lines (US-04).
- **Bilingual contract PDF** (Story 08): Arabic and English side by side, with an Arabic
  font in the CI image (US-07).
- **Post-dated cheques** (Story 09): cheques on schedule lines, held → deposited → cleared
  or bounced, replacement of bounced cheques, a "to deposit" list; status only (US-13).
- **Unit import** (Story 10): CSV or `.xlsx`, matched by unit code so it can be re-run, all
  or nothing, every bad row reported with its row number and reason (US-08).
- **Demo data** (Story 10): Nile Heights Developments with five users, three projects, 24
  units, five plans and contracts in every state, replayed from fifteen months of history;
  `make demo`.
- **Release checks** (Story 10): every user story named by a test (pre-commit hook),
  `make coverage` (97 %), screenshots and a 60-second demo GIF in the README.

[1.0.0]: https://github.com/MAbdallaDev/odoo-real-estate-eg/releases/tag/v1.0.0
