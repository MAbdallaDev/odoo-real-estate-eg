-- Story 07 (S07.1): about 1,000,000 schedule lines for a load test of the
-- collections screens. Run ONLY on the separate performance database:
--
--   psql -v ON_ERROR_STOP=1 -d re_perf -f scripts/perf/seed.sql
--
-- It writes rows with plain SQL (generate_series), so no ORM code runs:
-- every stored computed column is written here directly. Lines have no
-- invoice; this is load-test data for one query, not accounting data.
-- Never used by the test suite or CI.

\timing on

-- Refuse to run twice, or on a database that holds real contracts.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM real_estate_contract) THEN
        RAISE EXCEPTION 'real_estate_contract is not empty: use a fresh re_perf';
    END IF;
END
$$;

-- Same random numbers on every run (for one PostgreSQL version).
SELECT setseed(0.07);

-- 10 projects in the main company.
INSERT INTO real_estate_project (name, code, location, company_id, active,
                                 create_date, write_date)
SELECT 'Perf Project ' || p, 'PP' || lpad(p::text, 2, '0'), 'Perf City', 1, TRUE,
       now(), now()
FROM generate_series(1, 10) AS p;

-- 25,000 customers (fictional, numbered).
INSERT INTO res_partner (name, complete_name, phone, type, active, lang,
                         autopost_bills, create_date, write_date)
SELECT 'Perf Buyer ' || n, 'Perf Buyer ' || n,
       '+20 100 ' || lpad(n::text, 7, '0'), 'contact', TRUE, 'en_US', 'ask',
       now(), now()
FROM generate_series(1, 25000) AS n;

-- 25,000 units, 2,500 per project, 4.5M to 9M EGP.
INSERT INTO real_estate_unit (code, project_id, company_id, unit_type, bedrooms,
                              floor, area, list_price, state, active,
                              create_date, write_date)
SELECT 'PU-' || lpad(n::text, 6, '0'),
       (SELECT id FROM real_estate_project
        WHERE code = 'PP' || lpad((1 + (n - 1) / 2500)::text, 2, '0')),
       1, 'apartment', 2 + n % 3, n % 12, 120 + n % 80,
       4500000 + (n % 451) * 10000, 'available', TRUE, now(), now()
FROM generate_series(1, 25000) AS n;

-- One contract per unit: 85% confirmed, 10% delivered, 5% draft; dated
-- between 1 Jan 2021 and about two months ago (drafts: the last 60 days).
-- Every contract's agent is the admin user (2): the measured query runs as
-- a collections user, whose record rules do not look at the agent.
WITH numbered AS (
    SELECT u.id AS unit_id, u.project_id, u.list_price,
           row_number() OVER (ORDER BY u.id) AS n, random() AS r
    FROM real_estate_unit u
    WHERE u.code LIKE 'PU-%'
),
buyers AS (
    SELECT id AS partner_id, row_number() OVER (ORDER BY id) AS n
    FROM res_partner
    WHERE name LIKE 'Perf Buyer %'
)
INSERT INTO real_estate_contract (name, partner_id, unit_id, project_id, user_id,
                                  company_id, state, date, confirmation_date,
                                  price, at_risk, create_date, write_date)
SELECT 'NH-PERF-' || lpad(x.n::text, 6, '0'), b.partner_id, x.unit_id,
       x.project_id, 2, 1, x.state, x.day,
       CASE WHEN x.state <> 'draft' THEN x.day END,
       x.list_price, FALSE, now(), now()
FROM (
    SELECT numbered.*,
           CASE WHEN r < 0.85 THEN 'confirmed'
                WHEN r < 0.95 THEN 'delivered'
                ELSE 'draft' END AS state,
           CASE WHEN r < 0.95
                THEN DATE '2021-01-01'
                     + (random() * (current_date - 60 - DATE '2021-01-01'))::int
                ELSE current_date - (random() * 60)::int END AS day
    FROM numbered
) AS x
JOIN buyers b ON b.n = x.n;

UPDATE real_estate_unit u
SET state = CASE c.state WHEN 'draft' THEN 'reserved'
                         WHEN 'delivered' THEN 'delivered'
                         ELSE 'sold' END
FROM real_estate_contract c
WHERE c.unit_id = u.id;

-- 40 lines per contract = 1,000,000: a 10% down payment on the contract
-- date, then 39 quarterly installments. A line already due is paid,
-- unless it is unpaid: 25% of the lines due in the last 120 days, 2% of
-- older ones (customers who stopped paying). Drafts: all scheduled.
INSERT INTO real_estate_installment (
    contract_id, sequence, number, company_id, line_type, amount, date_due,
    invoice_date, date_effective_due, state, amount_residual, amount_paid,
    days_past_due, is_overdue, aging_bucket, late_fee_accrued,
    late_fee_billed, late_fee_unbilled, late_fee_final, create_date, write_date)
SELECT contract_id, 10 + k, k, 1, line_type, amount, date_due,
       CASE WHEN state <> 'scheduled' THEN date_due END,
       date_due, state,
       CASE state WHEN 'invoiced' THEN amount
                  WHEN 'partially_paid' THEN round(amount / 2) ELSE 0 END,
       CASE state WHEN 'paid' THEN amount
                  WHEN 'partially_paid' THEN amount - round(amount / 2) ELSE 0 END,
       dpd, dpd > 7,
       CASE WHEN dpd <= 7 THEN NULL
            WHEN dpd <= 30 THEN '1_30'
            WHEN dpd <= 60 THEN '31_60'
            WHEN dpd <= 90 THEN '61_90'
            ELSE 'over_90' END,
       fee, 0, fee, state = 'paid', now(), now()
FROM (
    SELECT l.*,
           CASE WHEN l.state IN ('invoiced', 'partially_paid')
                THEN current_date - l.date_due ELSE 0 END AS dpd,
           CASE WHEN l.state IN ('invoiced', 'partially_paid')
                     AND current_date - l.date_due > 7
                THEN least(l.amount * 0.01 / 30 * (current_date - l.date_due),
                           l.amount * 0.10)::double precision
                ELSE 0 END AS fee
    FROM (
        SELECT c.id AS contract_id, k,
               CASE WHEN k = 0 THEN 'down_payment' ELSE 'installment' END
                   AS line_type,
               CASE WHEN k = 0 THEN round(c.price * 0.10)
                    ELSE round(c.price * 0.90 / 39) END AS amount,
               (c.date + make_interval(months => 3 * k))::date AS date_due,
               CASE
                   WHEN c.state = 'draft'
                        OR (c.date + make_interval(months => 3 * k))::date
                           > current_date
                       THEN 'scheduled'
                   WHEN random() < CASE
                            WHEN current_date
                                 - (c.date + make_interval(months => 3 * k))::date
                                 <= 120
                            THEN 0.25 ELSE 0.02 END
                       THEN CASE WHEN random() < 0.3 THEN 'partially_paid'
                                 ELSE 'invoiced' END
                   ELSE 'paid'
               END AS state
        FROM real_estate_contract c
        CROSS JOIN generate_series(0, 39) AS k
        WHERE c.name LIKE 'NH-PERF-%'
    ) AS l
) AS m;

-- BR-31: at risk = a live contract with an unpaid line over 60 days late.
UPDATE real_estate_contract c
SET at_risk = TRUE
WHERE c.state IN ('confirmed', 'delivered')
  AND EXISTS (SELECT 1 FROM real_estate_installment i
              WHERE i.contract_id = c.id
                AND i.state IN ('invoiced', 'partially_paid')
                AND i.days_past_due > 60);

ANALYZE res_partner;
ANALYZE real_estate_project;
ANALYZE real_estate_unit;
ANALYZE real_estate_contract;
ANALYZE real_estate_installment;

-- What was made (copied into the design note).
SELECT count(*) AS lines,
       count(*) FILTER (WHERE is_overdue) AS overdue,
       round(100.0 * count(*) FILTER (WHERE is_overdue) / count(*), 2)
           AS overdue_pct
FROM real_estate_installment;
SELECT state, count(*) FROM real_estate_installment GROUP BY state ORDER BY state;
SELECT aging_bucket, count(*) FROM real_estate_installment
WHERE is_overdue GROUP BY aging_bucket ORDER BY aging_bucket;
SELECT count(*) FILTER (WHERE at_risk) AS at_risk_contracts, count(*) AS contracts
FROM real_estate_contract;
