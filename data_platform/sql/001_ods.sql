-- ODS 贴源层：保留源系统字段，按业务主键幂等 upsert
CREATE SCHEMA IF NOT EXISTS ods;

CREATE TABLE IF NOT EXISTS ods.loan_contract (
    contract_no   VARCHAR(32) PRIMARY KEY,
    customer_no   VARCHAR(32) NOT NULL,
    org_code      VARCHAR(8)  NOT NULL,
    product_type  VARCHAR(8)  NOT NULL,
    loan_amount   NUMERIC(20, 2) NOT NULL CHECK (loan_amount >= 0),
    loan_balance  NUMERIC(20, 2) NOT NULL CHECK (loan_balance >= 0),
    overdue_days  INTEGER NOT NULL CHECK (overdue_days BETWEEN 0 AND 3650),
    risk_class    VARCHAR(8) NOT NULL,
    updated_at    TIMESTAMP NOT NULL,
    etl_batch     VARCHAR(32) NOT NULL,
    etl_time      TIMESTAMP DEFAULT now()
);

-- 幂等写入：只有水位更新的变更才覆盖，重跑同一批次不产生重复、不改变结果
INSERT INTO ods.loan_contract AS t
    (contract_no, customer_no, org_code, product_type, loan_amount,
     loan_balance, overdue_days, risk_class, updated_at, etl_batch)
VALUES (%(contract_no)s, %(customer_no)s, %(org_code)s, %(product_type)s,
        %(loan_amount)s, %(loan_balance)s, %(overdue_days)s, %(risk_class)s,
        %(updated_at)s, %(etl_batch)s)
ON CONFLICT (contract_no) DO UPDATE SET
    customer_no  = EXCLUDED.customer_no,
    org_code     = EXCLUDED.org_code,
    product_type = EXCLUDED.product_type,
    loan_amount  = EXCLUDED.loan_amount,
    loan_balance = EXCLUDED.loan_balance,
    overdue_days = EXCLUDED.overdue_days,
    risk_class   = EXCLUDED.risk_class,
    updated_at   = EXCLUDED.updated_at,
    etl_batch    = EXCLUDED.etl_batch,
    etl_time     = now()
WHERE EXCLUDED.updated_at > t.updated_at;

CREATE TABLE IF NOT EXISTS ods.repayment (
    contract_no    VARCHAR(32) NOT NULL,
    period_no      INTEGER NOT NULL,
    principal_due  NUMERIC(20, 2) NOT NULL CHECK (principal_due >= 0),
    principal_paid NUMERIC(20, 2) NOT NULL CHECK (principal_paid >= 0),
    interest_due   NUMERIC(20, 2) NOT NULL CHECK (interest_due >= 0),
    interest_paid  NUMERIC(20, 2) NOT NULL CHECK (interest_paid >= 0),
    updated_at     TIMESTAMP NOT NULL,
    PRIMARY KEY (contract_no, period_no)
);
