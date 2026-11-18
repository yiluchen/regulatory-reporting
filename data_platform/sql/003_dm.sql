-- DM 集市层：信贷主题宽表，EAST / 1104 / 人行报送统一取数
CREATE SCHEMA IF NOT EXISTS dm;

CREATE TABLE IF NOT EXISTS dm.credit_wide (
    stat_date          DATE        NOT NULL,
    org_code           VARCHAR(8)  NOT NULL,
    loan_count         INTEGER     NOT NULL,
    loan_balance       NUMERIC(20, 2) NOT NULL,
    npl_balance        NUMERIC(20, 2) NOT NULL,
    npl_ratio          NUMERIC(10, 6) NOT NULL,
    overdue_balance    NUMERIC(20, 2) NOT NULL,
    overdue_ratio      NUMERIC(10, 6) NOT NULL,
    provision_amount   NUMERIC(20, 2) NOT NULL,
    provision_coverage NUMERIC(10, 6) NOT NULL,
    PRIMARY KEY (stat_date, org_code)
);

WITH loan AS (
    SELECT org_code,
           count(*)                                        AS loan_count,
           sum(loan_balance)                               AS loan_balance,
           sum(loan_balance) FILTER (
               WHERE risk_class IN ('次级', '可疑', '损失')) AS npl_balance,
           sum(loan_balance) FILTER (WHERE overdue_days > 0) AS overdue_balance
    FROM dwd.loan_contract_clean
    GROUP BY org_code
), prov AS (
    SELECT org_code, sum(provision_amount) AS provision_amount
    FROM dwd.provision
    GROUP BY org_code
)
INSERT INTO dm.credit_wide AS t
SELECT DATE '2026-03-01',
       l.org_code,
       l.loan_count,
       l.loan_balance,
       coalesce(l.npl_balance, 0),
       CASE WHEN l.loan_balance = 0 THEN 0 ELSE l.npl_balance / l.loan_balance END,
       coalesce(l.overdue_balance, 0),
       CASE WHEN l.loan_balance = 0 THEN 0 ELSE l.overdue_balance / l.loan_balance END,
       coalesce(p.provision_amount, 0),
       CASE WHEN coalesce(l.npl_balance, 0) = 0 THEN 0
            ELSE p.provision_amount / l.npl_balance END
FROM loan l
LEFT JOIN prov p USING (org_code)
ON CONFLICT (stat_date, org_code) DO UPDATE SET
    loan_count         = EXCLUDED.loan_count,
    loan_balance       = EXCLUDED.loan_balance,
    npl_balance        = EXCLUDED.npl_balance,
    npl_ratio          = EXCLUDED.npl_ratio,
    overdue_balance    = EXCLUDED.overdue_balance,
    overdue_ratio      = EXCLUDED.overdue_ratio,
    provision_amount   = EXCLUDED.provision_amount,
    provision_coverage = EXCLUDED.provision_coverage;

-- 表间勾稽：DM 汇总必须与 DWD 明细逐笔加总一致
SELECT (SELECT sum(loan_balance) FROM dwd.loan_contract_clean) AS dwd_total,
       (SELECT sum(loan_balance) FROM dm.credit_wide WHERE stat_date = DATE '2026-03-01') AS dm_total;
