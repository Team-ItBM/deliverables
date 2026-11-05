# AWS Budgets: not managed by Terraform.
#
# The required budget already exists in the account (created by hand on
# 2026-11-05, read back with `aws budgets describe-budgets`):
#   name   dowon-total-20261109-20270112
#   type   COST, USD 300, time unit CUSTOM
#   period 2026-11-09 00:00 KST to 2027-01-12 23:59:59 KST
#   alerts ACTUAL > 80% and ACTUAL > 100%, both e-mail to teamitbm@gmail.com
#
# The pinned AWS provider (5.x, latest 5.100.0 checked on 2026-11-05) accepts
# only DAILY, MONTHLY, QUARTERLY or ANNUALLY for aws_budgets_budget.time_unit,
# so it cannot represent the CUSTOM period without replacing the budget with a
# different shape (e.g. monthly). Keeping the hand-made budget avoids that.
# Delete it by hand during teardown if it should not outlive the period.
