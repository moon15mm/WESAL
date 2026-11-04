# Database schema reference (generated)

Generated from the SQLAlchemy models (`backend/app/models`). Column types are PostgreSQL types.
RLS = row-level security policy enforced for the runtime role `wesal_app`.

## identity

### `permissions`

| column | type | null | notes |
|---|---|---|---|
| code | VARCHAR(80) | no | PK |
| module | VARCHAR(40) | no |  |
| scope | VARCHAR(40) | no |  |

### `role_permissions`

| column | type | null | notes |
|---|---|---|---|
| role_id | UUID | no | PK, → roles.id |
| permission_code | VARCHAR(80) | no | PK, → permissions.code |

### `roles`

| column | type | null | notes |
|---|---|---|---|
| code | VARCHAR(60) | no |  |
| scope | VARCHAR(40) | no |  |
| name | JSONB | no |  |
| is_system | BOOLEAN | no |  |
| business_id | UUID | yes | → businesses.id |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (code, business_id)

### `sessions`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, indexed |
| token_hash | VARCHAR(64) | no | unique |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| last_seen_at | TIMESTAMP WITH TIME ZONE | no |  |
| expires_at | TIMESTAMP WITH TIME ZONE | no |  |
| revoked_at | TIMESTAMP WITH TIME ZONE | yes |  |
| mfa_verified | BOOLEAN | no |  |
| mfa_pending | BOOLEAN | no |  |
| ip | VARCHAR(64) | yes |  |
| user_agent | VARCHAR(400) | yes |  |
| device_label | VARCHAR(120) | yes |  |
| id | UUID | no | PK |

### `user_roles`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | PK, → users.id |
| role_id | UUID | no | PK, → roles.id |
| granted_by | UUID | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |

### `users`

| column | type | null | notes |
|---|---|---|---|
| email | VARCHAR(254) | yes |  |
| phone | VARCHAR(20) | yes |  |
| password_hash | VARCHAR(255) | no |  |
| full_name | VARCHAR(160) | no |  |
| status | VARCHAR(40) | no |  |
| locale | VARCHAR(8) | no |  |
| document_locale | VARCHAR(8) | yes |  |
| number_system | VARCHAR(8) | no |  |
| timezone | VARCHAR(64) | no |  |
| currency | VARCHAR(3) | no |  |
| email_verified_at | TIMESTAMP WITH TIME ZONE | yes |  |
| phone_verified_at | TIMESTAMP WITH TIME ZONE | yes |  |
| mfa_enabled | BOOLEAN | no |  |
| mfa_secret_enc | TEXT | yes |  |
| mfa_recovery_hashes | JSONB | yes |  |
| failed_login_count | INTEGER | no |  |
| locked_until | TIMESTAMP WITH TIME ZONE | yes |  |
| last_login_at | TIMESTAMP WITH TIME ZONE | yes |  |
| password_changed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| terms_version | VARCHAR(20) | yes |  |
| terms_accepted_at | TIMESTAMP WITH TIME ZONE | yes |  |
| suspended_reason | TEXT | yes |  |
| avatar_file_id | UUID | yes | → files.id |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `verification_records`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | yes | → users.id, indexed |
| purpose | VARCHAR(40) | no |  |
| channel | VARCHAR(40) | no |  |
| target | VARCHAR(254) | no |  |
| code_hash | VARCHAR(128) | no |  |
| reference_id | VARCHAR(64) | yes |  |
| attempts | INTEGER | no |  |
| expires_at | TIMESTAMP WITH TIME ZONE | no |  |
| consumed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

## business

### `business_addresses`

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | no | → businesses.id, indexed |
| kind | VARCHAR(30) | no |  |
| city_id | INTEGER | yes | → cities.id |
| district | VARCHAR(120) | yes |  |
| address_line | VARCHAR(255) | no |  |
| postal_code | VARCHAR(10) | yes |  |
| building_number | VARCHAR(10) | yes |  |
| lat | FLOAT | yes |  |
| lng | FLOAT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `business_branches`

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | no | → businesses.id, indexed |
| name | VARCHAR(160) | no |  |
| code | VARCHAR(30) | yes |  |
| city_id | INTEGER | yes | → cities.id, indexed |
| district | VARCHAR(120) | yes |  |
| address_line | VARCHAR(255) | yes |  |
| lat | FLOAT | yes |  |
| lng | FLOAT | yes |  |
| phone | VARCHAR(20) | yes |  |
| working_hours | JSONB | yes |  |
| manager_user_id | UUID | yes | → users.id |
| is_active | BOOLEAN | no |  |
| is_primary | BOOLEAN | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (business_id, code)

### `business_documents`  · RLS

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | no | → businesses.id, indexed |
| doc_type | VARCHAR(40) | no |  |
| file_id | UUID | no | → files.id |
| number | VARCHAR(40) | yes |  |
| expires_on | DATE | yes |  |
| status | VARCHAR(40) | no |  |
| reviewed_by | UUID | yes |  |
| reviewed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| review_notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `business_users`

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | no | → businesses.id, indexed |
| user_id | UUID | no | → users.id, indexed |
| role_id | UUID | no | → roles.id |
| branch_id | UUID | yes | → business_branches.id |
| status | VARCHAR(40) | no |  |
| title | VARCHAR(120) | yes |  |
| invited_by | UUID | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (business_id, user_id)

### `businesses`

| column | type | null | notes |
|---|---|---|---|
| type | VARCHAR(40) | no | indexed |
| legal_name | VARCHAR(200) | no |  |
| trade_name_ar | VARCHAR(200) | no |  |
| trade_name_en | VARCHAR(200) | yes |  |
| slug | VARCHAR(120) | no | unique |
| cr_number | VARCHAR(20) | yes |  |
| vat_number | VARCHAR(20) | yes |  |
| vat_registered | BOOLEAN | no |  |
| activity | VARCHAR(200) | yes |  |
| description | TEXT | yes |  |
| logo_file_id | UUID | yes | → files.id |
| email | VARCHAR(254) | yes |  |
| phone | VARCHAR(20) | yes |  |
| website | VARCHAR(200) | yes |  |
| city_id | INTEGER | yes | → cities.id, indexed |
| verification_status | VARCHAR(40) | no | indexed |
| verified_at | TIMESTAMP WITH TIME ZONE | yes |  |
| verified_by | UUID | yes |  |
| rejection_reason | TEXT | yes |  |
| status | VARCHAR(40) | no |  |
| min_order_value | NUMERIC(14, 2) | yes |  |
| supply_terms | TEXT | yes |  |
| payment_terms | TEXT | yes |  |
| default_lead_time_days | INTEGER | yes |  |
| discoverable | BOOLEAN | no |  |
| store_type | VARCHAR(40) | yes |  |
| rating_avg | FLOAT | no |  |
| rating_count | INTEGER | no |  |
| created_by | UUID | yes |  |
| settings | JSONB | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `cities`

| column | type | null | notes |
|---|---|---|---|
| id | INTEGER | no | PK |
| region_id | INTEGER | no | → regions.id, indexed |
| code | VARCHAR(30) | no | unique |
| name | JSONB | no |  |
| lat | FLOAT | yes |  |
| lng | FLOAT | yes |  |

### `files`

| column | type | null | notes |
|---|---|---|---|
| owner_user_id | UUID | yes | → users.id, indexed |
| business_id | UUID | yes | → businesses.id, indexed |
| purpose | VARCHAR(40) | no |  |
| storage_key | VARCHAR(255) | no | unique |
| original_name | VARCHAR(255) | no |  |
| mime_type | VARCHAR(100) | no |  |
| size_bytes | BIGINT | no |  |
| sha256 | VARCHAR(64) | no |  |
| is_public | BOOLEAN | no |  |
| width | INTEGER | yes |  |
| height | INTEGER | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `regions`

| column | type | null | notes |
|---|---|---|---|
| id | INTEGER | no | PK |
| code | VARCHAR(20) | no | unique |
| name | JSONB | no |  |

### `supplier_coverage_areas`

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| city_id | INTEGER | no | → cities.id, indexed |
| district | VARCHAR(120) | yes |  |
| delivery_fee | NUMERIC(10, 2) | no |  |
| min_order_value | NUMERIC(14, 2) | yes |  |
| lead_time_days | INTEGER | no |  |
| delivery_days | JSONB | yes |  |
| is_active | BOOLEAN | no |  |
| id | UUID | no | PK |

Unique: (supplier_id, city_id, district)

## catalog

### `brands`

| column | type | null | notes |
|---|---|---|---|
| name_ar | VARCHAR(160) | no |  |
| name_en | VARCHAR(160) | no |  |
| slug | VARCHAR(120) | no | unique |
| manufacturer | VARCHAR(200) | yes |  |
| country | VARCHAR(2) | yes |  |
| logo_file_id | UUID | yes | → files.id |
| owner_business_id | UUID | yes | → businesses.id |
| is_active | BOOLEAN | no |  |
| created_by_business_id | UUID | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `categories`

| column | type | null | notes |
|---|---|---|---|
| id | INTEGER | no | PK |
| parent_id | INTEGER | yes | → categories.id |
| slug | VARCHAR(80) | no | unique |
| name | JSONB | no |  |
| icon | VARCHAR(40) | yes |  |
| sort_order | INTEGER | no |  |
| is_active | BOOLEAN | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `price_list_items`

| column | type | null | notes |
|---|---|---|---|
| price_list_id | UUID | no | → price_lists.id, indexed |
| supplier_product_id | UUID | no | → supplier_products.id, indexed |
| unit_price | NUMERIC(12, 2) | no |  |
| carton_price | NUMERIC(12, 2) | yes |  |
| id | UUID | no | PK |

Unique: (price_list_id, supplier_product_id)

### `price_lists`

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| name | VARCHAR(160) | no |  |
| type | VARCHAR(40) | no |  |
| currency | VARCHAR(3) | no |  |
| priority | INTEGER | no |  |
| valid_from | TIMESTAMP WITH TIME ZONE | yes |  |
| valid_to | TIMESTAMP WITH TIME ZONE | yes |  |
| is_active | BOOLEAN | no |  |
| customer_business_ids | JSONB | no |  |
| city_ids | JSONB | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `price_rules`

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| name | VARCHAR(160) | no |  |
| name_i18n | JSONB | no |  |
| kind | VARCHAR(40) | no |  |
| value | NUMERIC(10, 2) | no |  |
| min_qty | INTEGER | no |  |
| supplier_product_id | UUID | yes | → supplier_products.id |
| category_id | INTEGER | yes | → categories.id |
| customer_business_ids | JSONB | no |  |
| city_ids | JSONB | no |  |
| starts_at | TIMESTAMP WITH TIME ZONE | no |  |
| ends_at | TIMESTAMP WITH TIME ZONE | no |  |
| is_active | BOOLEAN | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `product_units`

| column | type | null | notes |
|---|---|---|---|
| product_id | UUID | no | → products.id, indexed |
| unit | VARCHAR(40) | no |  |
| pieces | INTEGER | no |  |
| barcode | VARCHAR(32) | yes |  |
| id | UUID | no | PK |

Unique: (product_id, unit)

### `products`

| column | type | null | notes |
|---|---|---|---|
| name_ar | VARCHAR(255) | no |  |
| name_en | VARCHAR(255) | no |  |
| name_i18n | JSONB | no |  |
| description_ar | TEXT | yes |  |
| description_en | TEXT | yes |  |
| brand_id | UUID | yes | → brands.id, indexed |
| category_id | INTEGER | no | → categories.id, indexed |
| manufacturer | VARCHAR(200) | yes |  |
| barcode | VARCHAR(32) | yes |  |
| base_sku | VARCHAR(64) | yes |  |
| package_size | VARCHAR(40) | yes |  |
| pieces_per_carton | INTEGER | no |  |
| image_file_id | UUID | yes | → files.id |
| status | VARCHAR(40) | no | indexed |
| created_by_business_id | UUID | yes | → businesses.id |
| search_text | TEXT | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `supplier_products`

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| product_id | UUID | no | → products.id, indexed |
| sku | VARCHAR(64) | yes |  |
| unit_price | NUMERIC(12, 2) | no |  |
| carton_price | NUMERIC(12, 2) | yes |  |
| pieces_per_carton | INTEGER | no |  |
| sell_by_piece | BOOLEAN | no |  |
| sell_by_carton | BOOLEAN | no |  |
| min_order_qty | INTEGER | no |  |
| availability | VARCHAR(40) | no |  |
| stock_qty | INTEGER | yes |  |
| low_stock_threshold | INTEGER | yes |  |
| is_active | BOOLEAN | no |  |
| price_updated_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (supplier_id, product_id)

## reps

### `authorization_areas`  · RLS

| column | type | null | notes |
|---|---|---|---|
| authorization_id | UUID | no | → authorizations.id, indexed |
| city_id | INTEGER | no | → cities.id |
| district | VARCHAR(120) | yes |  |
| id | UUID | no | PK |

### `authorization_history`  · RLS

| column | type | null | notes |
|---|---|---|---|
| authorization_id | UUID | no | → authorizations.id, indexed |
| action | VARCHAR(40) | no |  |
| from_status | VARCHAR(40) | yes |  |
| to_status | VARCHAR(40) | yes |  |
| actor_user_id | UUID | yes |  |
| reason | TEXT | yes |  |
| snapshot | JSONB | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `authorization_products`  · RLS

| column | type | null | notes |
|---|---|---|---|
| authorization_id | UUID | no | → authorizations.id, indexed |
| product_id | UUID | yes | → products.id |
| category_id | INTEGER | yes | → categories.id |
| brand_id | UUID | yes | → brands.id |
| id | UUID | no | PK |

### `authorizations`  · RLS

| column | type | null | notes |
|---|---|---|---|
| number | VARCHAR(30) | no | unique |
| supplier_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| type | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no | indexed |
| initiated_by | VARCHAR(20) | no |  |
| request_message | TEXT | yes |  |
| agreement_id | UUID | yes | → commission_agreements.id |
| all_products | BOOLEAN | no |  |
| all_areas | BOOLEAN | no |  |
| start_date | DATE | yes |  |
| end_date | DATE | yes |  |
| terms | TEXT | yes |  |
| terms_hash | VARCHAR(64) | yes |  |
| accepted_at | TIMESTAMP WITH TIME ZONE | yes |  |
| accepted_by | UUID | yes |  |
| status_reason | TEXT | yes |  |
| expiry_warned_at | TIMESTAMP WITH TIME ZONE | yes |  |
| renewed_from_id | UUID | yes | → authorizations.id |
| version | INTEGER | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `commission_agreements`

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| name | VARCHAR(160) | no |  |
| description | TEXT | yes |  |
| eligible_after | VARCHAR(20) | no |  |
| hold_days | INTEGER | no |  |
| is_active | BOOLEAN | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `commission_rules`

| column | type | null | notes |
|---|---|---|---|
| agreement_id | UUID | no | → commission_agreements.id, indexed |
| basis | VARCHAR(40) | no |  |
| rate | NUMERIC(10, 4) | no |  |
| scope | VARCHAR(40) | no |  |
| product_id | UUID | yes | → products.id |
| category_id | INTEGER | yes | → categories.id |
| brand_id | UUID | yes | → brands.id |
| min_order_value | NUMERIC(14, 2) | yes |  |
| priority | INTEGER | no |  |
| id | UUID | no | PK |

### `rep_targets`  · RLS

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| period_start | DATE | no |  |
| period_end | DATE | no |  |
| sales_target | NUMERIC(14, 2) | no |  |
| visits_target | INTEGER | no |  |
| new_customers_target | INTEGER | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `rep_tasks`  · RLS

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| customer_id | UUID | yes | → customers.id |
| title | VARCHAR(200) | no |  |
| description | TEXT | yes |  |
| due_at | TIMESTAMP WITH TIME ZONE | yes |  |
| priority | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no |  |
| created_by | UUID | yes |  |
| completed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `representative_areas`

| column | type | null | notes |
|---|---|---|---|
| representative_id | UUID | no | → representatives.id, indexed |
| city_id | INTEGER | no | → cities.id, indexed |
| district | VARCHAR(120) | yes |  |
| id | UUID | no | PK |

Unique: (representative_id, city_id, district)

### `representative_categories`

| column | type | null | notes |
|---|---|---|---|
| representative_id | UUID | no | PK, → representatives.id |
| category_id | INTEGER | no | PK, → categories.id |

### `representative_companies`

| column | type | null | notes |
|---|---|---|---|
| representative_id | UUID | no | → representatives.id, indexed |
| supplier_id | UUID | no | → businesses.id, indexed |
| relation | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no |  |
| employee_code | VARCHAR(40) | yes |  |
| supervisor_user_id | UUID | yes | → users.id |
| started_at | TIMESTAMP WITH TIME ZONE | no |  |
| ended_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (representative_id, supplier_id)

### `representative_documents`

| column | type | null | notes |
|---|---|---|---|
| representative_id | UUID | no | → representatives.id, indexed |
| doc_type | VARCHAR(40) | no |  |
| file_id | UUID | no | → files.id |
| status | VARCHAR(40) | no |  |
| reviewed_by | UUID | yes |  |
| reviewed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| review_notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `representatives`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, unique |
| kind | VARCHAR(40) | no |  |
| display_name | VARCHAR(160) | no |  |
| headline | VARCHAR(200) | yes |  |
| bio | TEXT | yes |  |
| experience_years | INTEGER | no |  |
| skills | JSONB | no |  |
| languages | JSONB | no |  |
| availability | VARCHAR(40) | no |  |
| public_profile | BOOLEAN | no |  |
| verification_status | VARCHAR(40) | no | indexed |
| verified_at | TIMESTAMP WITH TIME ZONE | yes |  |
| rejection_reason | TEXT | yes |  |
| freelance_doc_number | VARCHAR(40) | yes |  |
| home_city_id | INTEGER | yes | → cities.id |
| rating_avg | FLOAT | no |  |
| rating_count | INTEGER | no |  |
| is_active | BOOLEAN | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

## crm

### `customer_acquisition_records`  · RLS

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| retailer_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | yes | → representatives.id, indexed |
| source | VARCHAR(40) | no |  |
| first_order_id | UUID | yes |  |
| acquired_at | TIMESTAMP WITH TIME ZONE | no |  |
| recorded_by | UUID | yes |  |
| id | UUID | no | PK |

### `customer_assignments`  · RLS

| column | type | null | notes |
|---|---|---|---|
| customer_id | UUID | no | → customers.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| assigned_by | UUID | yes |  |
| starts_at | TIMESTAMP WITH TIME ZONE | no |  |
| ends_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |

### `customer_contacts`  · RLS

| column | type | null | notes |
|---|---|---|---|
| customer_id | UUID | no | → customers.id, indexed |
| name | VARCHAR(160) | no |  |
| role | VARCHAR(80) | yes |  |
| phone | VARCHAR(20) | yes |  |
| email | VARCHAR(254) | yes |  |
| id | UUID | no | PK |

### `customer_notes`  · RLS

| column | type | null | notes |
|---|---|---|---|
| customer_id | UUID | no | → customers.id, indexed |
| author_user_id | UUID | yes | → users.id |
| body | TEXT | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `customer_source_changes`  · RLS

| column | type | null | notes |
|---|---|---|---|
| acquisition_id | UUID | no | → customer_acquisition_records.id, indexed |
| old_source | VARCHAR(40) | yes |  |
| new_source | VARCHAR(40) | yes |  |
| old_representative_id | UUID | yes |  |
| new_representative_id | UUID | yes |  |
| reason | TEXT | no |  |
| changed_by | UUID | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `customers`  · RLS

| column | type | null | notes |
|---|---|---|---|
| owner_supplier_id | UUID | yes | → businesses.id, indexed |
| owner_representative_id | UUID | yes | → representatives.id, indexed |
| retailer_id | UUID | yes | → businesses.id, indexed |
| branch_id | UUID | yes | → business_branches.id |
| name | VARCHAR(200) | no |  |
| contact_name | VARCHAR(160) | yes |  |
| phone | VARCHAR(20) | yes |  |
| email | VARCHAR(254) | yes |  |
| city_id | INTEGER | yes | → cities.id, indexed |
| district | VARCHAR(120) | yes |  |
| address_line | VARCHAR(255) | yes |  |
| lat | FLOAT | yes |  |
| lng | FLOAT | yes |  |
| status | VARCHAR(40) | no | indexed |
| source | VARCHAR(40) | no |  |
| tags | JSONB | no |  |
| assigned_representative_id | UUID | yes | → representatives.id, indexed |
| favorite_product_ids | JSONB | no |  |
| last_order_at | TIMESTAMP WITH TIME ZONE | yes |  |
| last_visit_at | TIMESTAMP WITH TIME ZONE | yes |  |
| next_follow_up_at | TIMESTAMP WITH TIME ZONE | yes |  |
| orders_count | INTEGER | no |  |
| total_sales | NUMERIC(14, 2) | no |  |
| created_by | UUID | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `opportunities`  · RLS

| column | type | null | notes |
|---|---|---|---|
| customer_id | UUID | no | → customers.id, indexed |
| owner_supplier_id | UUID | yes | → businesses.id, indexed |
| owner_representative_id | UUID | yes | → representatives.id, indexed |
| supplier_id | UUID | yes | → businesses.id |
| title | VARCHAR(200) | no |  |
| estimated_value | NUMERIC(14, 2) | yes |  |
| stage | VARCHAR(40) | no |  |
| expected_close_at | TIMESTAMP WITH TIME ZONE | yes |  |
| notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `visits`  · RLS

| column | type | null | notes |
|---|---|---|---|
| representative_id | UUID | no | → representatives.id, indexed |
| supplier_id | UUID | yes | → businesses.id, indexed |
| customer_id | UUID | yes | → customers.id, indexed |
| retailer_id | UUID | yes | → businesses.id, indexed |
| branch_id | UUID | yes | → business_branches.id |
| purpose | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no | indexed |
| scheduled_at | TIMESTAMP WITH TIME ZONE | yes | indexed |
| started_at | TIMESTAMP WITH TIME ZONE | yes |  |
| ended_at | TIMESTAMP WITH TIME ZONE | yes |  |
| start_lat | FLOAT | yes |  |
| start_lng | FLOAT | yes |  |
| end_lat | FLOAT | yes |  |
| end_lng | FLOAT | yes |  |
| location_consent | BOOLEAN | no |  |
| outcome | VARCHAR(40) | yes |  |
| notes | TEXT | yes |  |
| discussed_products | JSONB | no |  |
| order_id | UUID | yes |  |
| next_visit_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

## orders

### `cart_items`  · RLS

| column | type | null | notes |
|---|---|---|---|
| cart_id | UUID | no | → carts.id, indexed |
| supplier_product_id | UUID | no | → supplier_products.id |
| unit | VARCHAR(40) | no |  |
| quantity | INTEGER | no |  |
| id | UUID | no | PK |

Unique: (cart_id, supplier_product_id, unit)

### `carts`  · RLS

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, indexed |
| retailer_id | UUID | no | → businesses.id |
| supplier_id | UUID | no | → businesses.id |
| branch_id | UUID | yes | → business_branches.id |
| notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (user_id, retailer_id, supplier_id)

### `delivery_confirmations`  · RLS

| column | type | null | notes |
|---|---|---|---|
| delivery_id | UUID | no | → delivery_records.id, indexed |
| order_id | UUID | no | → orders.id, indexed |
| confirmed_by | UUID | no |  |
| receiver_name | VARCHAR(160) | yes |  |
| items | JSONB | no |  |
| has_shortage | BOOLEAN | no |  |
| notes | TEXT | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `delivery_records`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, unique |
| status | VARCHAR(40) | no |  |
| scheduled_date | DATE | yes |  |
| prepared_at | TIMESTAMP WITH TIME ZONE | yes |  |
| ready_at | TIMESTAMP WITH TIME ZONE | yes |  |
| dispatched_at | TIMESTAMP WITH TIME ZONE | yes |  |
| delivered_at | TIMESTAMP WITH TIME ZONE | yes |  |
| driver_name | VARCHAR(160) | yes |  |
| driver_phone | VARCHAR(20) | yes |  |
| vehicle_plate | VARCHAR(20) | yes |  |
| proof_file_id | UUID | yes | → files.id |
| notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `number_sequences`

| column | type | null | notes |
|---|---|---|---|
| key | VARCHAR(40) | no | PK |
| value | INTEGER | no |  |

### `order_approvals`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| version | INTEGER | no |  |
| kind | VARCHAR(30) | no |  |
| requested_by | UUID | yes |  |
| requested_at | TIMESTAMP WITH TIME ZONE | no |  |
| opened_at | TIMESTAMP WITH TIME ZONE | yes |  |
| opened_by | UUID | yes |  |
| decision | VARCHAR(40) | no |  |
| decided_at | TIMESTAMP WITH TIME ZONE | yes |  |
| decided_by | UUID | yes |  |
| method | VARCHAR(40) | yes |  |
| comment | TEXT | yes |  |
| snapshot | JSONB | no |  |
| snapshot_hash | VARCHAR(64) | no |  |
| ip | VARCHAR(64) | yes |  |
| id | UUID | no | PK |

### `order_collections`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| amount | NUMERIC(14, 2) | no |  |
| method | VARCHAR(30) | no |  |
| reference | VARCHAR(120) | yes |  |
| collected_at | TIMESTAMP WITH TIME ZONE | no |  |
| proof_file_id | UUID | yes | → files.id |
| recorded_by | UUID | no |  |
| notes | TEXT | yes |  |
| id | UUID | no | PK |

### `order_items`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| position | INTEGER | no |  |
| supplier_product_id | UUID | no | → supplier_products.id |
| product_id | UUID | no | → products.id, indexed |
| name_ar | VARCHAR(255) | no |  |
| name_en | VARCHAR(255) | no |  |
| sku | VARCHAR(64) | yes |  |
| unit | VARCHAR(40) | no |  |
| pieces_per_unit | INTEGER | no |  |
| quantity | INTEGER | no |  |
| list_unit_price | NUMERIC(12, 2) | no |  |
| unit_price | NUMERIC(12, 2) | no |  |
| discount | NUMERIC(12, 2) | no |  |
| promotion_id | UUID | yes |  |
| line_total | NUMERIC(14, 2) | no |  |
| vat_amount | NUMERIC(14, 2) | no |  |
| delivered_qty | INTEGER | yes |  |
| returned_qty | INTEGER | no |  |
| category_id | INTEGER | yes |  |
| brand_id | UUID | yes |  |
| id | UUID | no | PK |

### `order_offer_items`  · RLS

| column | type | null | notes |
|---|---|---|---|
| offer_id | UUID | no | → order_offers.id, indexed |
| order_item_id | UUID | no | → order_items.id |
| quantity | INTEGER | no |  |
| unit_price | NUMERIC(12, 2) | no |  |
| discount | NUMERIC(12, 2) | no |  |
| id | UUID | no | PK |

### `order_offers`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| version | INTEGER | no |  |
| created_by | UUID | no |  |
| status | VARCHAR(40) | no |  |
| delivery_fee | NUMERIC(10, 2) | no |  |
| expected_delivery_date | DATE | yes |  |
| valid_until | TIMESTAMP WITH TIME ZONE | yes |  |
| notes | TEXT | yes |  |
| subtotal | NUMERIC(14, 2) | no |  |
| total | NUMERIC(14, 2) | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `order_status_history`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| from_status | VARCHAR(40) | yes |  |
| to_status | VARCHAR(40) | no |  |
| actor_user_id | UUID | yes |  |
| actor_role | VARCHAR(30) | yes |  |
| reason | TEXT | yes |  |
| version | INTEGER | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `orders`  · RLS

| column | type | null | notes |
|---|---|---|---|
| number | VARCHAR(30) | no | unique |
| retailer_id | UUID | no | → businesses.id, indexed |
| branch_id | UUID | yes | → business_branches.id, indexed |
| supplier_id | UUID | no | → businesses.id, indexed |
| channel | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no | indexed |
| created_by_user_id | UUID | no | → users.id |
| representative_id | UUID | yes | → representatives.id, indexed |
| authorization_id | UUID | yes | → authorizations.id |
| visit_id | UUID | yes |  |
| currency | VARCHAR(3) | no |  |
| subtotal | NUMERIC(14, 2) | no |  |
| discount_total | NUMERIC(14, 2) | no |  |
| delivery_fee | NUMERIC(10, 2) | no |  |
| vat_rate | NUMERIC(5, 4) | no |  |
| vat_total | NUMERIC(14, 2) | no |  |
| total | NUMERIC(14, 2) | no |  |
| notes | TEXT | yes |  |
| supplier_notes | TEXT | yes |  |
| version | INTEGER | no |  |
| approved_version | INTEGER | yes |  |
| submitted_at | TIMESTAMP WITH TIME ZONE | yes |  |
| approved_at | TIMESTAMP WITH TIME ZONE | yes |  |
| delivered_at | TIMESTAMP WITH TIME ZONE | yes |  |
| completed_at | TIMESTAMP WITH TIME ZONE | yes |  |
| cancelled_at | TIMESTAMP WITH TIME ZONE | yes |  |
| status_reason | TEXT | yes |  |
| expected_delivery_date | DATE | yes |  |
| payment_status | VARCHAR(40) | no |  |
| paid_amount | NUMERIC(14, 2) | no |  |
| invoice_file_id | UUID | yes | → files.id |
| invoice_number | VARCHAR(60) | yes |  |
| city_id | INTEGER | yes | → cities.id, indexed |
| idempotency_key | VARCHAR(80) | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `return_items`  · RLS

| column | type | null | notes |
|---|---|---|---|
| return_id | UUID | no | → returns.id, indexed |
| order_item_id | UUID | no | → order_items.id |
| quantity | INTEGER | no |  |
| approved_quantity | INTEGER | yes |  |
| reason | VARCHAR(40) | yes |  |
| id | UUID | no | PK |

### `returns`  · RLS

| column | type | null | notes |
|---|---|---|---|
| number | VARCHAR(30) | no | unique |
| order_id | UUID | no | → orders.id, indexed |
| retailer_id | UUID | no | → businesses.id, indexed |
| supplier_id | UUID | no | → businesses.id, indexed |
| requested_by | UUID | no |  |
| reason | VARCHAR(40) | no |  |
| description | TEXT | yes |  |
| status | VARCHAR(40) | no | indexed |
| evidence_file_ids | JSONB | no |  |
| decided_by | UUID | yes |  |
| decided_at | TIMESTAMP WITH TIME ZONE | yes |  |
| decision_notes | TEXT | yes |  |
| settlement_note | TEXT | yes |  |
| total_value | NUMERIC(14, 2) | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

## commissions

### `commission_adjustments`  · RLS

| column | type | null | notes |
|---|---|---|---|
| commission_id | UUID | no | → commissions.id, indexed |
| amount_delta | NUMERIC(14, 2) | no |  |
| reason | VARCHAR(40) | no |  |
| reference_id | UUID | yes |  |
| note | TEXT | yes |  |
| created_by | UUID | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `commission_disputes`  · RLS

| column | type | null | notes |
|---|---|---|---|
| commission_id | UUID | no | → commissions.id, indexed |
| raised_by | UUID | no |  |
| reason | TEXT | no |  |
| expected_amount | NUMERIC(14, 2) | yes |  |
| status | VARCHAR(40) | no |  |
| previous_status | VARCHAR(30) | yes |  |
| resolution | TEXT | yes |  |
| resolved_amount | NUMERIC(14, 2) | yes |  |
| resolved_by | UUID | yes |  |
| resolved_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `commission_payments`  · RLS

| column | type | null | notes |
|---|---|---|---|
| supplier_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| amount | NUMERIC(14, 2) | no |  |
| commission_ids | JSONB | no |  |
| method | VARCHAR(30) | no |  |
| reference | VARCHAR(120) | yes |  |
| proof_file_id | UUID | yes | → files.id |
| paid_at | TIMESTAMP WITH TIME ZONE | no |  |
| recorded_by | UUID | no |  |
| acknowledged_at | TIMESTAMP WITH TIME ZONE | yes |  |
| id | UUID | no | PK |

### `commissions`  · RLS

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| supplier_id | UUID | no | → businesses.id, indexed |
| representative_id | UUID | no | → representatives.id, indexed |
| authorization_id | UUID | no | → authorizations.id |
| agreement_id | UUID | no | → commission_agreements.id |
| status | VARCHAR(40) | no | indexed |
| eligible_amount | NUMERIC(14, 2) | no |  |
| amount | NUMERIC(14, 2) | no |  |
| original_amount | NUMERIC(14, 2) | no |  |
| currency | VARCHAR(3) | no |  |
| breakdown | JSONB | no |  |
| due_at | TIMESTAMP WITH TIME ZONE | yes |  |
| approved_at | TIMESTAMP WITH TIME ZONE | yes |  |
| approved_by | UUID | yes |  |
| paid_at | TIMESTAMP WITH TIME ZONE | yes |  |
| status_reason | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

## system

### `advertisements`

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | yes | → businesses.id |
| placement | VARCHAR(40) | no |  |
| title | JSONB | no |  |
| body | JSONB | no |  |
| image_file_id | UUID | yes | → files.id |
| link_url | VARCHAR(255) | yes |  |
| starts_at | TIMESTAMP WITH TIME ZONE | no |  |
| ends_at | TIMESTAMP WITH TIME ZONE | no |  |
| status | VARCHAR(40) | no |  |
| city_ids | JSONB | no |  |
| impressions | INTEGER | no |  |
| clicks | INTEGER | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `ai_interactions`  · RLS

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, indexed |
| business_id | UUID | yes |  |
| feature | VARCHAR(40) | no |  |
| provider | VARCHAR(20) | no |  |
| input_summary | TEXT | yes |  |
| output_summary | TEXT | yes |  |
| latency_ms | INTEGER | yes |  |
| success | BOOLEAN | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `audit_logs`

| column | type | null | notes |
|---|---|---|---|
| id | BIGINT | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no | indexed |
| actor_user_id | UUID | yes | indexed |
| actor_business_id | UUID | yes | indexed |
| action | VARCHAR(80) | no | indexed |
| entity_type | VARCHAR(40) | yes |  |
| entity_id | VARCHAR(64) | yes |  |
| result | VARCHAR(20) | no |  |
| changes | JSONB | yes |  |
| reason | TEXT | yes |  |
| ip | VARCHAR(64) | yes |  |
| user_agent | VARCHAR(400) | yes |  |
| request_id | VARCHAR(64) | yes |  |

### `complaint_messages`  · RLS

| column | type | null | notes |
|---|---|---|---|
| complaint_id | UUID | no | → complaints.id, indexed |
| author_user_id | UUID | no |  |
| author_side | VARCHAR(20) | no |  |
| body | TEXT | no |  |
| internal | BOOLEAN | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `complaints`  · RLS

| column | type | null | notes |
|---|---|---|---|
| number | VARCHAR(30) | no | unique |
| kind | VARCHAR(40) | no |  |
| category | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no | indexed |
| priority | VARCHAR(40) | no |  |
| order_id | UUID | yes | → orders.id, indexed |
| raised_by_user_id | UUID | no | → users.id |
| raised_by_business_id | UUID | yes | → businesses.id, indexed |
| against_business_id | UUID | yes | → businesses.id, indexed |
| against_representative_id | UUID | yes | → representatives.id, indexed |
| subject | VARCHAR(200) | no |  |
| description | TEXT | no |  |
| attachment_file_ids | JSONB | no |  |
| assigned_admin_id | UUID | yes |  |
| resolution | TEXT | yes |  |
| resolved_at | TIMESTAMP WITH TIME ZONE | yes |  |
| order_status_before | VARCHAR(40) | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `contact_messages`

| column | type | null | notes |
|---|---|---|---|
| name | VARCHAR(160) | no |  |
| email | VARCHAR(254) | yes |  |
| phone | VARCHAR(20) | yes |  |
| audience | VARCHAR(20) | yes |  |
| message | TEXT | no |  |
| handled | BOOLEAN | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `content_pages`

| column | type | null | notes |
|---|---|---|---|
| slug | VARCHAR(80) | no |  |
| locale | VARCHAR(8) | no |  |
| title | VARCHAR(200) | no |  |
| body | TEXT | no |  |
| version | VARCHAR(20) | no |  |
| is_published | BOOLEAN | no |  |
| updated_by | UUID | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (slug, locale)

### `data_requests`  · RLS

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, indexed |
| kind | VARCHAR(40) | no |  |
| status | VARCHAR(40) | no |  |
| reason | TEXT | yes |  |
| handled_by | UUID | yes |  |
| handled_at | TIMESTAMP WITH TIME ZONE | yes |  |
| result_file_id | UUID | yes | → files.id |
| notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `job_runs`

| column | type | null | notes |
|---|---|---|---|
| job | VARCHAR(60) | no | indexed |
| started_at | TIMESTAMP WITH TIME ZONE | no |  |
| finished_at | TIMESTAMP WITH TIME ZONE | yes |  |
| success | BOOLEAN | yes |  |
| processed | INTEGER | no |  |
| error | TEXT | yes |  |
| id | UUID | no | PK |

### `languages`

| column | type | null | notes |
|---|---|---|---|
| code | VARCHAR(8) | no | PK |
| name | VARCHAR(60) | no |  |
| native_name | VARCHAR(60) | no |  |
| direction | VARCHAR(3) | no |  |
| is_enabled | BOOLEAN | no |  |
| sort_order | INTEGER | no |  |

### `notification_deliveries`

| column | type | null | notes |
|---|---|---|---|
| notification_id | UUID | yes | → notifications.id, indexed |
| user_id | UUID | yes |  |
| channel | VARCHAR(40) | no |  |
| target | VARCHAR(254) | yes |  |
| template | VARCHAR(60) | no |  |
| locale | VARCHAR(8) | no |  |
| payload | JSONB | no |  |
| status | VARCHAR(40) | no |  |
| attempts | INTEGER | no |  |
| next_attempt_at | TIMESTAMP WITH TIME ZONE | no |  |
| last_error | TEXT | yes |  |
| provider_ref | VARCHAR(120) | yes |  |
| dedupe_key | VARCHAR(200) | yes | unique |
| sent_at | TIMESTAMP WITH TIME ZONE | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `notification_preferences`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | PK, → users.id |
| event | VARCHAR(60) | no | PK |
| channel | VARCHAR(40) | no | PK |
| enabled | BOOLEAN | no |  |

### `notifications`  · RLS

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id |
| event | VARCHAR(60) | no |  |
| params | JSONB | no |  |
| link | VARCHAR(255) | yes |  |
| entity_type | VARCHAR(40) | yes |  |
| entity_id | VARCHAR(64) | yes |  |
| dedupe_key | VARCHAR(200) | yes |  |
| read_at | TIMESTAMP WITH TIME ZONE | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `platform_settings`

| column | type | null | notes |
|---|---|---|---|
| key | VARCHAR(80) | no | PK |
| value | JSONB | yes |  |
| is_public | BOOLEAN | no |  |
| updated_by | UUID | yes |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `push_subscriptions`

| column | type | null | notes |
|---|---|---|---|
| user_id | UUID | no | → users.id, indexed |
| endpoint | TEXT | no | unique |
| p256dh | VARCHAR(200) | no |  |
| auth | VARCHAR(100) | no |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `rating_reports`

| column | type | null | notes |
|---|---|---|---|
| rating_id | UUID | no | → ratings.id, indexed |
| reported_by | UUID | no |  |
| reason | TEXT | no |  |
| resolved_at | TIMESTAMP WITH TIME ZONE | yes |  |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

### `ratings`

| column | type | null | notes |
|---|---|---|---|
| order_id | UUID | no | → orders.id, indexed |
| rater_business_id | UUID | no | → businesses.id |
| rater_user_id | UUID | no |  |
| target_type | VARCHAR(40) | no |  |
| target_id | UUID | no | indexed |
| overall | SMALLINT | no |  |
| product_quality | SMALLINT | yes |  |
| delivery_commitment | SMALLINT | yes |  |
| communication | SMALLINT | yes |  |
| comment | TEXT | yes |  |
| status | VARCHAR(40) | no |  |
| moderation_note | TEXT | yes |  |
| reply | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

Unique: (order_id, rater_business_id, target_type)

### `subscription_plans`

| column | type | null | notes |
|---|---|---|---|
| code | VARCHAR(40) | no | unique |
| audience | VARCHAR(20) | no |  |
| name | JSONB | no |  |
| description | JSONB | no |  |
| price_monthly | NUMERIC(10, 2) | no |  |
| price_yearly | NUMERIC(10, 2) | no |  |
| limits | JSONB | no |  |
| features | JSONB | no |  |
| is_active | BOOLEAN | no |  |
| sort_order | INTEGER | no |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `subscriptions`

| column | type | null | notes |
|---|---|---|---|
| business_id | UUID | yes | → businesses.id, indexed |
| representative_id | UUID | yes | → representatives.id, indexed |
| plan_id | UUID | no | → subscription_plans.id |
| status | VARCHAR(40) | no |  |
| period_start | TIMESTAMP WITH TIME ZONE | no |  |
| period_end | TIMESTAMP WITH TIME ZONE | yes |  |
| notes | TEXT | yes |  |
| id | UUID | no | PK |
| created_at | TIMESTAMP WITH TIME ZONE | no |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |

### `translation_overrides`

| column | type | null | notes |
|---|---|---|---|
| locale | VARCHAR(8) | no | → languages.code |
| key | VARCHAR(200) | no |  |
| value | TEXT | no |  |
| updated_by | UUID | yes |  |
| updated_at | TIMESTAMP WITH TIME ZONE | no |  |
| id | UUID | no | PK |

Unique: (locale, key)
