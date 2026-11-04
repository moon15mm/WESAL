---
title: Data Retention Policy
version: "1.0"
---
# Data Retention Policy

> Draft requiring legal and accounting review; financial record retention is subject to the applicable tax and commercial regulations.

| Data | Retention | After the period | How |
|---|---|---|---|
| Orders, approvals, commissions, returns | For the life of the account, and at least the statutory commercial-record period | Archived; on account closure personal data is anonymised and financial records kept | Documented admin procedure |
| Security audit log | At least 5 years | Deleted by a documented admin procedure (the log is append-only for the application) | Admin procedure |
| Login sessions | 90 days after session expiry | Deleted | Automatic daily job |
| Verification codes (OTP) | 7 days after expiry | Deleted | Automatic daily job |
| In-app notifications | 12 months | Deleted | Automatic daily job |
| Notification delivery log (email/SMS) | 90 days after sending or failure | Deleted | Automatic daily job |
| Visit GPS coordinates | 24 months | Coordinates removed, visit record kept | Automatic daily job |
| Contact form messages | 24 months | Deleted | Automatic daily job |
| Account on deletion request | Until the request is processed by an administrator | Personal data (name, mobile, email) anonymised, sessions revoked | Deletion request processing |
| Backups | Per the backup schedule (default 14 daily copies) | Rotated automatically | Backup script |

## User rights
From **Settings → Privacy** users can download a copy of their data or submit a deletion request, unless a legal obligation (such as keeping financial records) prevents it, in which case only personal data is anonymised.
