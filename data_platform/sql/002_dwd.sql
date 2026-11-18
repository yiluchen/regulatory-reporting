-- DWD 明细层：清洗与标准化，异常数据沉到 dwd.reject 而不是直接丢弃
CREATE SCHEMA IF NOT EXISTS dwd;

CREATE TABLE IF NOT EXISTS dwd.loan_contract_clean (
    contract_no   VARCHAR(32) PRIMARY KEY,
    customer_no   VARCHAR(32) NOT NULL,
    org_code      VARCHAR(8)  NOT NULL,
    product_type  VARCHAR(8)  NOT NULL,
    loan_amount   NUMERIC(20, 2) NOT NULL,
    loan_balance  NUMERIC(20, 2) NOT NULL,
    overdue_days  INTEGER NOT NULL,
    risk_class    VARCHAR(8)  NOT NULL,
    updated_at    TIMESTAMP NOT NULL
);

INSERT INTO dwd.loan_contract_clean (contract_no, customer_no, org_code, product_type,
                                     loan_amount, loan_balance, overdue_days, risk_class, updated_at)
SELECT DISTINCT ON (contract_no)
       contract_no,
       btrim(customer_no)                          AS customer_no,
       upper(btrim(org_code))                      AS org_code,
       lpad(btrim(product_type), 3, '0')           AS product_type,
       loan_amount,
       loan_balance,
       overdue_days,
       risk_class,
       updated_at
FROM ods.loan_contract
WHERE customer_no IS NOT NULL
  AND loan_balance >= 0
  AND overdue_days BETWEEN 0 AND 3650
  AND risk_class IN ('正常', '关注', '次级', '可疑', '损失')
ORDER BY contract_no, updated_at DESC
ON CONFLICT (contract_no) DO UPDATE SET
    customer_no  = EXCLUDED.customer_no,
    org_code     = EXCLUDED.org_code,
    product_type = EXCLUDED.product_type,
    loan_amount  = EXCLUDED.loan_amount,
    loan_balance = EXCLUDED.loan_balance,
    overdue_days = EXCLUDED.overdue_days,
    risk_class   = EXCLUDED.risk_class,
    updated_at   = EXCLUDED.updated_at
WHERE EXCLUDED.updated_at >= dwd.loan_contract_clean.updated_at;

-- 表内校验：已还本金 / 利息不得超过应还
SELECT contract_no, period_no,
       principal_paid - principal_due AS principal_gap,
       interest_paid  - interest_due  AS interest_gap
FROM ods.repayment
WHERE principal_paid > principal_due + 0.01
   OR interest_paid  > interest_due  + 0.01;
