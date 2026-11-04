# API endpoint index (generated)

283 operations. Full schema: [`openapi.json`](openapi.json) (OpenAPI 3).

## admin

| method | path | summary |
|---|---|---|
| GET | `/api/v1/admin/ads` | Ads |
| POST | `/api/v1/admin/ads` | Create Ad |
| PUT | `/api/v1/admin/ads/{aid}` | Update Ad |
| GET | `/api/v1/admin/audit` | Audit Logs |
| POST | `/api/v1/admin/brands` | Create Brand |
| PUT | `/api/v1/admin/brands/{bid}` | Update Brand |
| GET | `/api/v1/admin/businesses` | Businesses |
| GET | `/api/v1/admin/businesses/{bid}` | Business Detail |
| POST | `/api/v1/admin/businesses/{bid}/status` | Business Status |
| POST | `/api/v1/admin/businesses/{bid}/verification` | Verify Business |
| POST | `/api/v1/admin/categories` | Create Category |
| PUT | `/api/v1/admin/categories/{cid}` | Update Category |
| GET | `/api/v1/admin/commissions` | Commissions |
| GET | `/api/v1/admin/complaints` | Complaints |
| POST | `/api/v1/admin/complaints/{cid}` | Complaint Action |
| GET | `/api/v1/admin/contact-messages` | Contact Messages |
| GET | `/api/v1/admin/dashboard` | Dashboard |
| GET | `/api/v1/admin/data-requests` | Data Requests |
| POST | `/api/v1/admin/data-requests/{rid}` | Handle Data Request |
| POST | `/api/v1/admin/languages/{code}` | Toggle Language |
| GET | `/api/v1/admin/orders` | Orders |
| GET | `/api/v1/admin/orders/{oid}` | Order Detail |
| GET | `/api/v1/admin/pages` | Pages |
| PUT | `/api/v1/admin/pages` | Upsert Page |
| GET | `/api/v1/admin/plans` | Plans |
| POST | `/api/v1/admin/plans` | Upsert Plan |
| GET | `/api/v1/admin/products` | Products |
| POST | `/api/v1/admin/products/{pid}/status` | Product Status |
| GET | `/api/v1/admin/ratings` | Ratings |
| POST | `/api/v1/admin/ratings/{rid}` | Moderate |
| GET | `/api/v1/admin/representatives` | Representatives |
| POST | `/api/v1/admin/representatives/{rid}/active` | Rep Active |
| POST | `/api/v1/admin/representatives/{rid}/verification` | Verify Rep |
| GET | `/api/v1/admin/settings` | Get Settings |
| PUT | `/api/v1/admin/settings/{key}` | Put Setting |
| GET | `/api/v1/admin/subscriptions` | Subscriptions |
| POST | `/api/v1/admin/subscriptions` | Create Subscription |
| GET | `/api/v1/admin/system` | System |
| GET | `/api/v1/admin/translations` | Translations |
| PUT | `/api/v1/admin/translations` | Upsert Translation |
| DELETE | `/api/v1/admin/translations/{oid}` | Delete Translation |
| GET | `/api/v1/admin/users` | Users |
| GET | `/api/v1/admin/users/{uid}` | User Detail |
| POST | `/api/v1/admin/users/{uid}/activate` | Activate User |
| POST | `/api/v1/admin/users/{uid}/platform-role` | Platform Role |
| POST | `/api/v1/admin/users/{uid}/suspend` | Suspend User |

## ai

| method | path | summary |
|---|---|---|
| GET | `/api/v1/ai/alternatives/{product_id}` | Alternatives |
| POST | `/api/v1/ai/ask` | Ask |
| POST | `/api/v1/ai/parse-order` | Parse Order |
| GET | `/api/v1/ai/reorder-forecast` | Reorder |
| GET | `/api/v1/ai/rep/opportunities` | Rep Opps |
| POST | `/api/v1/ai/rep/parse-order` | Rep Parse Order |
| GET | `/api/v1/ai/rep/performance` | Rep Perf |
| GET | `/api/v1/ai/search` | Smart Search |
| GET | `/api/v1/ai/status` | Status |
| GET | `/api/v1/ai/supplier/coverage-gaps` | Gaps |
| GET | `/api/v1/ai/supplier/summary` | Summary |

## auth

| method | path | summary |
|---|---|---|
| GET | `/api/v1/auth/csrf` | Csrf |
| GET | `/api/v1/auth/locales` | Locales |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/logout-all` | Logout All |
| GET | `/api/v1/auth/me` | Me |
| PATCH | `/api/v1/auth/me` | Update Me |
| POST | `/api/v1/auth/mfa/disable` | Mfa Disable |
| POST | `/api/v1/auth/mfa/enable` | Mfa Enable |
| POST | `/api/v1/auth/mfa/setup` | Mfa Setup |
| POST | `/api/v1/auth/mfa/verify` | Mfa Verify |
| POST | `/api/v1/auth/otp/login` | Otp Login |
| POST | `/api/v1/auth/otp/request` | Otp Request |
| POST | `/api/v1/auth/password/change` | Change Password |
| POST | `/api/v1/auth/password/forgot` | Forgot |
| POST | `/api/v1/auth/password/reset` | Reset |
| POST | `/api/v1/auth/register` | Register |
| GET | `/api/v1/auth/sessions` | Sessions |
| DELETE | `/api/v1/auth/sessions/{session_id}` | Revoke Session |
| POST | `/api/v1/auth/verify/confirm` | Verify Confirm |
| POST | `/api/v1/auth/verify/request` | Verify Request |

## authorizations

| method | path | summary |
|---|---|---|
| GET | `/api/v1/ref/authorization-types` | Authorization Types |
| GET | `/api/v1/rep/authorizations` | Rep List |
| POST | `/api/v1/rep/authorizations` | Rep Request |
| GET | `/api/v1/rep/authorizations/{auth_id}` | Rep Get |
| POST | `/api/v1/rep/authorizations/{auth_id}/accept` | Rep Accept |
| POST | `/api/v1/rep/authorizations/{auth_id}/decline` | Rep Decline |
| GET | `/api/v1/supplier/authorizations` | Supplier List |
| POST | `/api/v1/supplier/authorizations` | Supplier Create |
| GET | `/api/v1/supplier/authorizations/{auth_id}` | Supplier Get |
| PUT | `/api/v1/supplier/authorizations/{auth_id}` | Supplier Update Terms |
| POST | `/api/v1/supplier/authorizations/{auth_id}/cancel` | Handler |
| POST | `/api/v1/supplier/authorizations/{auth_id}/decline` | Handler |
| POST | `/api/v1/supplier/authorizations/{auth_id}/issue` | Supplier Issue |
| POST | `/api/v1/supplier/authorizations/{auth_id}/renew` | Supplier Renew |
| POST | `/api/v1/supplier/authorizations/{auth_id}/resume` | Handler |
| POST | `/api/v1/supplier/authorizations/{auth_id}/suspend` | Handler |
| GET | `/api/v1/supplier/commission-agreements` | List Agreements |
| POST | `/api/v1/supplier/commission-agreements` | Create Agreement |
| PUT | `/api/v1/supplier/commission-agreements/{agreement_id}` | Update Agreement |

## business

| method | path | summary |
|---|---|---|
| GET | `/api/v1/business/addresses` | List Addresses |
| POST | `/api/v1/business/addresses` | Add Address |
| DELETE | `/api/v1/business/addresses/{address_id}` | Delete Address |
| GET | `/api/v1/business/documents` | List Documents |
| POST | `/api/v1/business/documents` | Upload Document |
| POST | `/api/v1/business/logo` | Upload Logo |
| GET | `/api/v1/business/profile` | Get Profile |
| PATCH | `/api/v1/business/profile` | Update Profile |
| GET | `/api/v1/business/roles` | List Roles |
| POST | `/api/v1/business/roles` | Create Role |
| GET | `/api/v1/business/team` | List Team |
| POST | `/api/v1/business/team` | Add Member |
| PATCH | `/api/v1/business/team/{member_id}` | Update Member |
| POST | `/api/v1/business/verification/submit` | Submit Verification |
| GET | `/api/v1/retailer/branches` | List Branches |
| POST | `/api/v1/retailer/branches` | Create Branch |
| PATCH | `/api/v1/retailer/branches/{branch_id}` | Update Branch |
| GET | `/api/v1/supplier/coverage` | Get Coverage |
| PUT | `/api/v1/supplier/coverage` | Set Coverage |

## catalog

| method | path | summary |
|---|---|---|
| GET | `/api/v1/catalog/brands` | List Brands |
| GET | `/api/v1/market/offers` | Market Offers |
| GET | `/api/v1/market/products` | Market Products |
| GET | `/api/v1/market/products/{product_id}` | Market Product |
| GET | `/api/v1/market/suppliers` | Market Suppliers |
| GET | `/api/v1/market/suppliers/{supplier_id}` | Market Supplier |
| GET | `/api/v1/rep/catalog` | Rep Catalog |
| POST | `/api/v1/supplier/brands` | Create Brand |
| GET | `/api/v1/supplier/price-lists` | List Price Lists |
| POST | `/api/v1/supplier/price-lists` | Create Price List |
| DELETE | `/api/v1/supplier/price-lists/{pl_id}` | Delete Price List |
| PUT | `/api/v1/supplier/price-lists/{pl_id}` | Update Price List |
| GET | `/api/v1/supplier/products` | My Offers |
| POST | `/api/v1/supplier/products` | Create Offer |
| POST | `/api/v1/supplier/products/import` | Import Offers |
| POST | `/api/v1/supplier/products/stock` | Bulk Stock |
| GET | `/api/v1/supplier/products/{offer_id}` | Get Offer |
| PATCH | `/api/v1/supplier/products/{offer_id}` | Update Offer |
| POST | `/api/v1/supplier/products/{offer_id}/image` | Upload Product Image |
| GET | `/api/v1/supplier/promotions` | List Promotions |
| POST | `/api/v1/supplier/promotions` | Create Promotion |
| PUT | `/api/v1/supplier/promotions/{promo_id}` | Update Promotion |

## commissions

| method | path | summary |
|---|---|---|
| GET | `/api/v1/rep/commission-payments` | Rep Payments |
| POST | `/api/v1/rep/commission-payments/{pid}/acknowledge` | Rep Ack |
| GET | `/api/v1/rep/commissions` | Rep List |
| POST | `/api/v1/rep/commissions/{cid}/dispute` | Rep Dispute |
| POST | `/api/v1/supplier/commission-disputes/{did}/resolve` | Resolve |
| GET | `/api/v1/supplier/commission-payments` | Supplier Payments |
| POST | `/api/v1/supplier/commission-payments` | Record Payment |
| GET | `/api/v1/supplier/commissions` | Supplier List |
| POST | `/api/v1/supplier/commissions/approve` | Approve |
| POST | `/api/v1/supplier/commissions/{cid}/adjust` | Adjust |

## complaints

| method | path | summary |
|---|---|---|
| GET | `/api/v1/complaints` | Mine |
| POST | `/api/v1/complaints` | Create |
| GET | `/api/v1/complaints/{cid}` | Get One |
| POST | `/api/v1/complaints/{cid}/messages` | Reply |

## crm

| method | path | summary |
|---|---|---|
| GET | `/api/v1/rep/customers` | R List |
| POST | `/api/v1/rep/customers` | R Create |
| GET | `/api/v1/rep/customers/{cid}` | R Get |
| PATCH | `/api/v1/rep/customers/{cid}` | R Update |
| POST | `/api/v1/rep/customers/{cid}/contacts` | R Contact |
| POST | `/api/v1/rep/customers/{cid}/notes` | R Note |
| GET | `/api/v1/rep/discover` | Discover Stores |
| GET | `/api/v1/rep/opportunities` | R Opps |
| POST | `/api/v1/rep/opportunities` | R Opp Create |
| PATCH | `/api/v1/rep/opportunities/{oid}` | R Opp Update |
| GET | `/api/v1/rep/sales-opportunities` | Sales Opportunities |
| GET | `/api/v1/supplier/customers` | S List |
| POST | `/api/v1/supplier/customers` | S Create |
| GET | `/api/v1/supplier/customers/{cid}` | S Get |
| PATCH | `/api/v1/supplier/customers/{cid}` | S Update |
| POST | `/api/v1/supplier/customers/{cid}/contacts` | S Contact |
| POST | `/api/v1/supplier/customers/{cid}/notes` | S Note |
| POST | `/api/v1/supplier/customers/{cid}/source` | S Change Source |
| GET | `/api/v1/supplier/opportunities` | S Opps |
| POST | `/api/v1/supplier/opportunities` | S Opp Create |

## files

| method | path | summary |
|---|---|---|
| GET | `/api/v1/files/{file_id}` | Download |

## health

| method | path | summary |
|---|---|---|
| GET | `/api/v1/health/live` | Live |
| GET | `/api/v1/health/ready` | Ready |

## notifications

| method | path | summary |
|---|---|---|
| GET | `/api/v1/notifications` | List Notifications |
| GET | `/api/v1/notifications/preferences` | Get Prefs |
| PUT | `/api/v1/notifications/preferences` | Set Prefs |
| GET | `/api/v1/notifications/push/public-key` | Vapid Key |
| POST | `/api/v1/notifications/push/subscribe` | Push Subscribe |
| POST | `/api/v1/notifications/push/unsubscribe` | Push Unsubscribe |
| POST | `/api/v1/notifications/read-all` | Read All |
| GET | `/api/v1/notifications/unread-count` | Unread Count |
| POST | `/api/v1/notifications/{nid}/read` | Mark Read |

## orders

| method | path | summary |
|---|---|---|
| GET | `/api/v1/rep/orders` | Rep Orders |
| POST | `/api/v1/rep/orders` | Create Rep Order |
| GET | `/api/v1/rep/orders/{oid}` | Rep Order |
| PUT | `/api/v1/rep/orders/{oid}/items` | Rep Edit |
| POST | `/api/v1/rep/orders/{oid}/submit` | Rep Submit |
| POST | `/api/v1/rep/orders/{oid}/withdraw` | Rep Withdraw |
| GET | `/api/v1/retailer/carts` | List Carts |
| DELETE | `/api/v1/retailer/carts/{supplier_id}` | Clear Cart |
| POST | `/api/v1/retailer/carts/{supplier_id}/checkout` | Checkout |
| PUT | `/api/v1/retailer/carts/{supplier_id}/items` | Set Cart Item |
| GET | `/api/v1/retailer/orders` | Retailer Orders |
| POST | `/api/v1/retailer/orders` | Create Retailer Order |
| GET | `/api/v1/retailer/orders/{oid}` | Retailer Order |
| POST | `/api/v1/retailer/orders/{oid}/accept-offer` | Accept Offer |
| POST | `/api/v1/retailer/orders/{oid}/approval-otp` | Send Approval Otp |
| POST | `/api/v1/retailer/orders/{oid}/approve` | Retailer Approve |
| POST | `/api/v1/retailer/orders/{oid}/approve-change` | Approve Change |
| POST | `/api/v1/retailer/orders/{oid}/cancel` | Retailer Cancel |
| POST | `/api/v1/retailer/orders/{oid}/confirm-delivery` | Confirm Delivery |
| PUT | `/api/v1/retailer/orders/{oid}/items` | Retailer Edit |
| POST | `/api/v1/retailer/orders/{oid}/reject` | Retailer Reject |
| POST | `/api/v1/retailer/orders/{oid}/reject-change` | Reject Change |
| POST | `/api/v1/retailer/orders/{oid}/reject-offer` | Reject Offer |
| POST | `/api/v1/retailer/orders/{oid}/reorder` | Reorder |
| POST | `/api/v1/retailer/orders/{oid}/request-changes` | Retailer Request Changes |
| POST | `/api/v1/retailer/orders/{oid}/submit` | Retailer Submit |
| GET | `/api/v1/supplier/orders` | Supplier Orders |
| GET | `/api/v1/supplier/orders-summary` | Supplier Summary |
| GET | `/api/v1/supplier/orders/{oid}` | Supplier Order |
| POST | `/api/v1/supplier/orders/{oid}/accept` | Supplier Accept |
| POST | `/api/v1/supplier/orders/{oid}/cancel` | Supplier Cancel |
| POST | `/api/v1/supplier/orders/{oid}/collections` | Record Collection |
| POST | `/api/v1/supplier/orders/{oid}/deliver` | Deliver |
| POST | `/api/v1/supplier/orders/{oid}/dispatch` | Dispatch |
| POST | `/api/v1/supplier/orders/{oid}/invoice` | Upload Invoice |
| POST | `/api/v1/supplier/orders/{oid}/modify` | Supplier Modify |
| POST | `/api/v1/supplier/orders/{oid}/offer` | Supplier Offer |
| POST | `/api/v1/supplier/orders/{oid}/prepare` | Prepare |
| POST | `/api/v1/supplier/orders/{oid}/ready` | Ready |
| POST | `/api/v1/supplier/orders/{oid}/reject` | Supplier Reject |
| POST | `/api/v1/supplier/orders/{oid}/start-review` | Start Review |

## privacy

| method | path | summary |
|---|---|---|
| GET | `/api/v1/ads` | Active Ads |
| GET | `/api/v1/privacy/export` | Export Now |
| GET | `/api/v1/privacy/requests` | My Requests |
| POST | `/api/v1/privacy/requests` | Create Request |

## public

| method | path | summary |
|---|---|---|
| POST | `/api/v1/public/contact` | Contact |
| GET | `/api/v1/public/pages/{slug}` | Page |
| GET | `/api/v1/public/stats` | Stats |

## ratings

| method | path | summary |
|---|---|---|
| GET | `/api/v1/ratings` | List Ratings |
| GET | `/api/v1/rep/ratings` | Rep Ratings |
| POST | `/api/v1/rep/ratings/{rid}/report` | Rep Report |
| POST | `/api/v1/retailer/orders/{oid}/ratings` | Rate |
| GET | `/api/v1/supplier/ratings` | Supplier Ratings |
| POST | `/api/v1/supplier/ratings/{rid}/reply` | Supplier Reply |
| POST | `/api/v1/supplier/ratings/{rid}/report` | Supplier Report |

## reference

| method | path | summary |
|---|---|---|
| GET | `/api/v1/ref/categories` | Categories |
| GET | `/api/v1/ref/cities` | Cities |
| GET | `/api/v1/ref/languages` | Languages |
| GET | `/api/v1/ref/plans` | Plans |
| GET | `/api/v1/ref/regions` | Regions |
| GET | `/api/v1/ref/settings` | Public Settings |
| GET | `/api/v1/ref/translations/{locale}` | Translation Overrides |

## reports

| method | path | summary |
|---|---|---|
| GET | `/api/v1/orders/{oid}/document.pdf` | Order Document |
| GET | `/api/v1/reports/rep` | Rep Report |
| GET | `/api/v1/reports/retailer` | Retailer Report |
| GET | `/api/v1/reports/supplier` | Supplier Report |

## representatives

| method | path | summary |
|---|---|---|
| GET | `/api/v1/market/representatives` | Directory |
| GET | `/api/v1/market/representatives/{rep_id}` | Directory Profile |
| GET | `/api/v1/rep/companies` | My Companies |
| GET | `/api/v1/rep/documents` | List Documents |
| POST | `/api/v1/rep/documents` | Upload Document |
| GET | `/api/v1/rep/profile` | Get Profile |
| PATCH | `/api/v1/rep/profile` | Update Profile |
| GET | `/api/v1/rep/targets` | Rep Targets |
| GET | `/api/v1/rep/tasks` | Rep Tasks |
| PATCH | `/api/v1/rep/tasks/{task_id}` | Rep Task Status |
| POST | `/api/v1/rep/verification/submit` | Submit Verification |
| GET | `/api/v1/supplier/reps` | Supplier Reps |
| POST | `/api/v1/supplier/reps/company` | Add Company Rep |
| POST | `/api/v1/supplier/reps/{rep_id}/end` | End Relation |
| GET | `/api/v1/supplier/targets` | Supplier Targets |
| POST | `/api/v1/supplier/targets` | Create Target |
| GET | `/api/v1/supplier/tasks` | Supplier Tasks |
| POST | `/api/v1/supplier/tasks` | Create Task |
| PATCH | `/api/v1/supplier/tasks/{task_id}` | Supplier Task Status |

## returns

| method | path | summary |
|---|---|---|
| POST | `/api/v1/retailer/orders/{oid}/returns` | Request Return |
| GET | `/api/v1/retailer/returns` | Retailer Returns |
| POST | `/api/v1/retailer/returns/{rid}/cancel` | Retailer Cancel Return |
| GET | `/api/v1/supplier/returns` | Supplier Returns |
| GET | `/api/v1/supplier/returns/{rid}` | Supplier Return |
| POST | `/api/v1/supplier/returns/{rid}/decide` | Decide |
| POST | `/api/v1/supplier/returns/{rid}/receive` | Receive |
| POST | `/api/v1/supplier/returns/{rid}/settle` | Settle |

## visits

| method | path | summary |
|---|---|---|
| GET | `/api/v1/rep/visits` | List Visits |
| POST | `/api/v1/rep/visits` | Create Visit |
| POST | `/api/v1/rep/visits/{vid}/cancel` | Cancel Visit |
| POST | `/api/v1/rep/visits/{vid}/end` | End Visit |
| POST | `/api/v1/rep/visits/{vid}/start` | Start Visit |
| GET | `/api/v1/supplier/visits` | Supplier Visits |
