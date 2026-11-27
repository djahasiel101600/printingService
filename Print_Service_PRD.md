# Project Requirements Document: On-Demand Print Service Web Application

**Status:** v1.1 — Admin-managed catalogue services
**Date:** September 5, 2026
**Platform:** Web Application
**Core Integrations:** Epson Connect API v2.0 (printing) · PayMongo API (QR Ph payments)

---

## 1. Project Overview

### 1.1 Purpose

A web-based, on-demand printing service. Clients submit digital files (documents or images) with printing instructions, pay online, and have the job printed on an Epson printer via the Epson Connect API — without needing to understand printer settings themselves. An administrator reviews and approves every job before it is released to the printer, acting as a quality and cost checkpoint.

### 1.2 Problem Statement

Ordinary customers who want something printed (documents, photos, school requirements, marketing materials, etc.) are often unfamiliar with printer-level settings such as paper size, paper type, color mode, orientation, or duplex printing. This creates friction with self-service printing kiosks, remote/cloud printing tools, or describing needs to a print shop over chat/phone. The goal: remove that friction. The client describes what they want in plain language, optionally fine-tunes a few simple options, and the system + an admin operator handle the technical translation to actual printer parameters.

### 1.3 Goals & Objectives

- **Accessibility** — Make remote printing usable by anyone, regardless of technical knowledge, similar to walking up to a shop counter and saying "please print this."
- **Guided simplicity** — Printing parameters (paper size, paper type, color, sides, quality, copies) are optional, sensible defaults are pre-selected, and the client can rely on free-text instructions instead.
- **Quality control** — No file reaches the physical printer without human admin review and approval, reducing misprints and wasted materials.
- **Revenue assurance** — Require at least a partial payment via QR Ph before a job is queued, reducing no-shows and unclaimed print-outs.
- **Catalogue flexibility** — Let shop admins offer fixed-price services such as 2x2 ID pictures without changing the per-side pricing rules used for custom documents.
- **Traceability** — Every accepted job receives a unique tracking identifier so clients (even guests) can check status without creating an account.
- **Lean scope** — Provide only the editing tools needed to prepare a file for print (crop, split, resize, center). This is not a design or desktop-publishing tool.

### 1.4 Target Users

- Digital clients (students, professionals, small business owners) who need something printed but don't own/operate a capable printer.
- Repeat/business clients who prefer a registered account with saved history and details.
- Admin/operator staff who manage the physical printer(s), review jobs, and handle fulfillment.

---

## 2. Scope

### 2.1 In Scope (v1 / MVP)

- Guest and registered-account submission flow.
- Multi-file upload (PDF and common image formats) for custom printing.
- Admin-managed catalogue services with fixed unit prices, quantity limits, featured products, and one uploaded source file per catalogue order.
- Guided print-specification form mapped to Epson Connect API parameters, plus a free-text instructions field.
- Basic pre-print editing: crop, split PDF pages, resize, and center/align on the print canvas.
- Automatic price computation (quotation engine) based on selected parameters and page/quantity count.
- Online payment (full or partial/down payment) via PayMongo QR Ph.
- Admin review and approval queue prior to sending the job to the printer.
- Order tracking via a unique reference/tracking ID, with status updates.
- Integration with Epson Connect API v2 to submit and monitor the actual print job.
- Basic notification of status changes (email/SMS/on-site tracking page).

### 2.2 Out of Scope (v1)

- Advanced graphic design / desktop-publishing features (layering, filters, in-file text editing, template design).
- Automatic 2x2 photo composition, cropping, passport-photo validation, or template generation; catalogue layouts are prepared manually by shop staff.
- Shopping carts, multiple catalogue products per order, and multi-file catalogue requests in v1.
- Support for printer brands/APIs other than Epson Connect.
- Multi-branch / multi-location printer routing (single shop / small fixed pool of printers assumed for v1).
- Delivery/courier logistics (v1 assumes client pickup after printing, referencing the tracking ID).
- In-house accounting/bookkeeping system beyond basic payment and order records.

(See Section 10 for post-MVP candidates.)

---

## 3. User Roles & Permissions

| Role | Description | Key Permissions |
|---|---|---|
| Guest Client | Submits a job by providing name and a contact method, no account required. | Upload files, set instructions, pay, track order via reference ID + contact match. |
| Registered Client | Created an account (email/password or social login). | All guest permissions, plus saved order history, saved contact/billing details, faster re-orders. |
| Admin / Staff | Operates the print shop side of the platform. | Review submitted jobs, approve/reject/request revision, adjust job parameters, view payment status, push approved jobs to the printer, update order status, manage pricing rules. |
| Super Admin (optional) | Owner/manager level. | All admin permissions, plus manage pricing table, manage staff accounts, manage connected printers, view reports. |

Shop admins manage the catalogue. Approvers can review and act on orders but cannot create, edit, feature, archive, or reprice catalogue products.

---

## 4. End-to-End User Flow

The admin approval step sits **after online payment is secured, or after the customer selects the enabled pay-upon-pickup option, but before the job is released to the physical printer** — so unpaid pickup work remains visible while still protecting the printer from unreviewed jobs.

### 4.1 Client-Side Flow

1. Entry point — the client chooses to (a) log in / create an account, or (b) continue as guest.
2. If guest: client provides full name, a contact number, and at least one reachable channel (Facebook Messenger link/handle or email).
3. File upload — client uploads one or more files (PDF, JPG, PNG, etc.). Each file shows a live preview thumbnail.
4. Basic pre-print editing (optional) — client may crop, split a multi-page PDF into a chosen page range, resize, or center/align content on the target paper size before proceeding.
5. Print specification — for each file (or applied to all files at once), the client either:
   - (a) fills out simple guided fields — paper size, paper type, color or black-and-white, number of copies, single/double-sided, print quality — all optional with system defaults pre-filled; and/or
   - (b) writes free-text instructions describing the request in plain language, as if speaking to a person behind a counter.
6. Quotation — system calculates an estimated price from page count, copies, paper size/type, and color mode, and displays it before checkout.
7. Payment — client pays via PayMongo QR Ph, choosing full payment or a partial/down payment (a configurable minimum percentage), or selects **Pay upon pickup** when the shop has enabled it. Checkout cannot proceed without a valid payment selection.
8. Confirmation & tracking ID — after order submission and successful online payment, or after pay-upon-pickup selection, the system shows the order/tracking identifier and a confirmation screen; guests also receive a reminder of how to check status later (tracking ID + contact info).
9. Status tracking — client can check the order status at any time (Submitted, Pending Review, Approved/In Queue, Printing, Printed – Ready for Pickup, On Hold, Rejected, Cancelled) using the tracking ID.

**Catalogue alternative:** From `/order?mode=catalogue`, the client chooses one active catalogue service, enters the number of finished pieces, uploads exactly one source file, and sees the fixed server-calculated total before submitting. Page counts and per-side controls are not used for catalogue pricing. The same flow is available to shop admins when creating an order for a registered customer or walk-in.

### 4.2 Admin-Side Flow

1. New paid submissions and orders using the enabled pay-upon-pickup option appear in an Admin Review Queue, sorted by submission time / due date.
2. Admin opens a job to view: uploaded/edited files, client-selected parameters, free-text instructions, computed price, and payment status (full or partial).
3. Admin can adjust or correct print parameters if the client's request is ambiguous, add internal notes, and then Approve, Reject (with reason, triggering refund/communication workflow), or Request Revision (sends the job back to the client with comments).
4. On approval, the system submits the print job to the target Epson printer through the Epson Connect API (file upload + print settings + execute print).
5. Admin monitors job/device status (printing, completed, error) and updates the order status accordingly; marks the order Printed – Ready for Pickup once physical output is confirmed.
6. For partial-payment or pay-upon-pickup orders, admin can record the balance collected at the shop to close the amount due.
7. For a catalogue order, staff must upload the shop-prepared layout through **Upload prepared layout** on the source file before approval. A raw photo, printer-compatible upload, or automatically generated final file is not sufficient.
8. Shop admins manage products at `/admin/catalogue`, including fixed peso prices, quantity bounds, print defaults, instructions, featured status, and archival. Existing orders retain their creation-time snapshots.

---

## 5. Functional Requirements

### 5.1 Account & Guest Handling

- **FR-1:** Users can register with email/password (and optionally social login) or continue as a guest.
- **FR-2:** Guest checkout requires: full name, contact number, and at least one of {email, Facebook Messenger handle/link}.
- **FR-3:** Guest orders are retrievable using tracking ID + the contact info supplied at submission (as a lightweight verification step).
- **FR-4:** Registered clients get an order history dashboard and can reuse previously saved contact/billing details. Shop admins have an owner-only customer directory at `/admin/customers` showing signup/contact details, account status, sign-in information, order counts, and last-order information; guest checkout details are not registered accounts.

### 5.2 File Upload & Basic Editing

- **FR-5:** Support multi-file upload in a single order, with per-file thumbnail preview.
- **FR-6:** Accepted formats for v1: PDF, JPG/JPEG, PNG (extensible later to DOCX/PPTX via server-side conversion if needed).
- **FR-7:** File size limits and total upload caps are configurable by admin.
- **FR-8:** Basic editing toolkit, deliberately limited to:
  - Crop — trim a rectangular region of an image or PDF page.
  - Split PDF — divide a multi-page PDF into separate print jobs or select a specific page range.
  - Resize — scale content to fit a selected paper size.
  - Center / Align — position content within the printable canvas (center, or align to a margin).
- **FR-9:** Editing is performed client-side where possible for responsiveness, with the final edited output saved as the file actually sent for printing.
- **FR-10:** Explicitly excluded from editing: text/content editing inside the file, filters/effects, multi-layer composition, template design — to keep the tool simple and prevent scope creep.

### 5.3 Print Specification

- **FR-11:** Guided fields are optional and pre-populated with sensible defaults (e.g., A4/Letter, plain paper, color, 1 copy, single-sided, normal quality).
- **FR-12:** A free-text "instructions" field is always available and can fully replace the guided fields; admin reads and manually maps it to printer parameters during review if needed.
- **FR-13:** Guided fields map directly to Epson Connect API v2 print settings (see Section 7.1) so admin approval requires little to no re-entry of data.
- **FR-14:** Client can apply one set of settings to all files, or customize settings per file.

### 5.4 Pricing & Quotation

- **FR-15:** System computes a price estimate automatically from: page/sheet count, number of copies, paper size, paper type, color vs. black-and-white, and single- vs. double-sided, using an admin-configurable price table.
- **FR-16:** Price is recalculated live as the client changes parameters, files, or page ranges.
- **FR-17:** Admin can override the computed price on a specific order (e.g., for a custom job described only in free text) before it is sent for payment, or at review time if payment covers a manual quote workflow.

### 5.5 Payment (PayMongo QR Ph and Pay upon pickup)

- **FR-18:** Client must choose QR Ph full payment, QR Ph partial/down payment (minimum percentage configurable by admin, e.g. 50%), or pay upon pickup when that option is enabled by the shop admin at `/admin/settings`.
- **FR-19:** Checkout is blocked unless a valid payment option is selected. Disabled pay-upon-pickup requests are rejected by the backend even if a stale client attempts them; QR Ph remains available.
- **FR-20:** Payment is processed through PayMongo's Payment Intent workflow with QR Ph as the enabled payment method; the dynamic QR code (single-use, amount-encoded, ~30 minute expiry) is displayed to the client at checkout.
- **FR-21:** Payment confirmation is received via PayMongo webhook (`payment.paid`) and reflected on the order automatically; `qrph.expired` and `payment.failed` are handled with a retry option.
- **FR-22:** For partial payments and pay-upon-pickup orders, the system tracks amount paid vs. balance due. Pickup selection creates no online payment and moves the order to pending review; staff can later record the cash collected at pickup to close the balance.
- **FR-23:** Refunds (e.g., on admin rejection) are recorded and, where supported by PayMongo, processed via the Refunds API; otherwise flagged for manual refund handling.

### 5.6 Admin Review & Approval

- **FR-24:** All paid orders and pay-upon-pickup orders enter a review queue and cannot be sent to the printer until explicitly approved by an admin.
- **FR-25:** Admin can Approve, Reject (with reason), or Request Revision (returns the order to the client with comments, order re-enters an editable state).
- **FR-26:** Admin can adjust print parameters before approval (e.g., correcting a paper size the client left ambiguous) and can leave internal notes.
- **FR-27:** Admin dashboard shows, per order: files (with preview), client-selected parameters, free-text instructions, computed price, payment status, and client contact info.

### 5.7 Printer Integration (Epson Connect API v2)

- **FR-28:** On approval, the system authenticates with Epson Connect API v2 (device/subject-level access token per the printer's client ID/secret) and creates a print job using `job_name`, `print_mode`, and the mapped `print_setting` object.
- **FR-29:** System uploads the (edited) file to the job's provided upload URI, then triggers execution and polls or listens for job status.
- **FR-30:** System retrieves and (where useful) exposes the target printer's supported capabilities (paper sizes/types per print mode, color modes, sources) so guided fields only offer values the connected printer can actually fulfill.
- **FR-31:** Printer/job errors (e.g., out of paper, offline, unsupported settings) are surfaced to the admin with the order flagged for attention (e.g., status "On Hold – Printer Issue").

### 5.8 Order Tracking & Notifications

- **FR-32:** A unique, human-readable tracking ID (e.g., `PR-20260905-0001`) is generated once payment succeeds.
- **FR-33:** Order status is visible to the client at any time via the tracking ID (and login for registered users), with at minimum these states: Submitted, Pending Review, Approved/In Queue, Printing, Printed – Ready for Pickup, On Hold, Revision Requested, Rejected, Cancelled.
- **FR-34:** Status-change notifications are sent through the client's chosen contact channel (email, SMS, or Messenger, depending on what's available/integrated).

---

## 6. Non-Functional Requirements

- **Usability:** The guided flow must be understandable to a first-time, non-technical user without instructions; free-text input is always an acceptable fallback.
- **Security:** Uploaded files, payment data, and personal contact details must be handled securely (HTTPS everywhere, no storage of raw card data — payment fields are collected and tokenized client-side by PayMongo, never touching the application backend).
- **Reliability:** Print job status and payment status must stay consistent even if a step (upload, webhook, printer response) is delayed or retried; use idempotent requests where the payment API supports it.
- **Performance:** File preview and basic editing actions (crop, resize, split) should feel near-instant for typical file sizes (a few MB, under ~50 pages).
- **Auditability:** Every status change (submitted, approved, rejected, printed, paid, refunded) is logged with a timestamp and the acting user (client or admin).
- **Data retention:** Uploaded files can be purged automatically after a configurable retention window post-completion, to avoid unnecessary storage of clients' personal materials.
- **Scalability:** Architecture should allow adding more connected printers or admin seats without a redesign, even though v1 targets a single shop/printer pool.

---

## 7. Third-Party Integrations

### 7.1 Epson Connect API v2 — Print Job Mapping

Epson Connect API v1.3 is being retired; this project targets **v2.0**. A print job is created against an authorized printer (identified via the printer's registered email / client credentials), then the source file is uploaded to the job, then execution is triggered.

| Client-Facing Field | Epson API Parameter | Notes |
|---|---|---|
| Job label | `job_name` | System-generated from the order/tracking ID, not client-entered. |
| Content type | `print_mode` (`document` / `photo`) | Inferred from file type by default; photo mode for images, document mode for PDFs. |
| Paper size | `print_setting.media_size` | Populated from the printer's actual supported sizes (via capabilities lookup) rather than a hardcoded list. |
| Paper type | `print_setting.media_type` | E.g., plain paper, photo paper — also limited to printer-supported values. |
| Borderless printing | `print_setting.borderless` | Only offered where supported for the chosen size/type. |
| Print quality | `print_setting.print_quality` (`draft` / `normal` / `high`) | Simple 3-tier selector for the client. |
| Paper source/tray | `print_setting.source` | Defaults to the printer's primary tray; admin can override. |
| Color mode | `print_setting.color_mode` (`color` / `mono`) | Directly affects the price quotation. |
| Sides | `print_setting.2_sided` (`none` / `long` / `short` edge) | Presented to the client as "Single-sided / Double-sided (flip long edge / flip short edge)." |
| Copies | `print_setting.copies` (1–99) | Directly editable by the client. |
| Collate / reverse order | `print_setting.collate`, `print_setting.reverse_order` | Advanced options, hidden by default behind an "Advanced" toggle. |

**Implementation note:** call the printer capabilities endpoint per `print_mode` so the guided form only ever shows sizes/types/qualities the connected printer actually supports, avoiding failed jobs at print time.

### 7.2 PayMongo — QR Ph Payment Flow

PayMongo's QR Ph is the Philippine national QR standard (BSP-supervised); a dynamic, single-use, amount-encoded QR code is generated per transaction and expires after ~30 minutes if unscanned. The application follows PayMongo's standard Payment Intent workflow:

1. Backend creates a Payment Intent with the computed order amount and `"qrph"` included in `payment_method_allowed`.
2. Frontend creates a Payment Method of type `qrph`, using the client's name, email, and phone as billing details.
3. Frontend attaches the Payment Method to the Payment Intent using the `client_key` from step 1.
4. On successful attach, the response's `next_action.code.image_url` contains a Base64 QR code image, displayed to the client to scan with any supported banking or e-wallet app.
5. PayMongo sends a `payment.paid` webhook on success (or `payment.failed` / `qrph.expired` on failure/timeout); the backend updates order and payment status accordingly.

For partial payments, the Payment Intent amount is set to the partial amount; a second Payment Intent is created later for the remaining balance when the client settles it (e.g., on pickup).

---

## 8. Order Status Lifecycle

| Status | Meaning |
|---|---|
| Draft | Client has started an order (files/instructions) but has not paid yet. |
| Awaiting Payment | Order submitted, checkout in progress, QR Ph code generated and awaiting scan. |
| Pending Review | Payment (full or partial) confirmed; order is in the admin queue awaiting approval. |
| Revision Requested | Admin sent the order back to the client with comments; client can edit and resubmit. |
| Approved / Queued | Admin approved; job has been or is about to be submitted to the Epson printer. |
| Printing | Epson Connect API reports the job is actively printing. |
| On Hold – Printer Issue | Printer error (offline, paper jam, unsupported setting) needs admin attention. |
| Printed – Ready for Pickup | Physical output confirmed complete; balance payment (if any) collected on pickup. |
| Rejected | Admin declined the order (e.g., inappropriate content, unfulfillable request); refund workflow triggered if paid. |
| Cancelled | Cancelled by client (before review) or by admin; refund workflow triggered if paid. |
| Completed | Client has picked up the material and any balance is fully settled. Terminal state. |

---

## 9. Key Data Entities (High-Level)

- **User** — `id`, `role` (guest/client/admin), `name`, `email`, `phone`, `facebook_handle`, `password_hash` (if registered), `created_at`.
- **Order** — `id`, `tracking_id`, `user_id` (nullable for guest + guest contact snapshot), `status`, `subtotal`, `amount_paid`, `balance_due`, `payment_type` (full/partial), `admin_notes`, `created_at`, `approved_at`, `completed_at`. Catalogue orders also store `catalogue_product`, `product_name_snapshot`, `product_unit_price_snapshot`, `product_unit_label_snapshot`, `product_instructions_snapshot`, `product_min_quantity_snapshot`, `product_max_quantity_snapshot`, and `product_quantity`.
- **CatalogueProduct** — `id`, unique immutable `slug`, `name`, `description`, optional `cover_image` with public `cover_image_url`, `category`, `price` (centavos), `unit_label`, `min_quantity`, nullable `max_quantity`, `is_active`, `is_featured`, `display_order`, `default_spec`, customer/staff `instructions`, `created_at`, `updated_at`.
- **OrderFile** — `id`, `order_id`, `original_file_url`, `edited_file_url`, `file_type`, `page_count`, `edit_actions` (crop/split/resize/center metadata).
- **PrintSpecification** — `id`, `order_file_id` (or `order_id` if applied to all), `media_size`, `media_type`, `color_mode`, `sides`, `print_quality`, `copies`, `borderless`, `source`, `free_text_instructions`.
- **Payment** — `id`, `order_id`, `paymongo_payment_intent_id`, `amount`, `method` (qrph), `status`, `paid_at`, `refund_status`.
- **PrintJob** — `id`, `order_id`, `epson_job_id`, `printer_id`, `status`, `submitted_at`, `completed_at`, `error_message`.
- **PriceRule** — `id`, `media_size`, `media_type`, `color_mode`, `sides`, `price_per_page_or_sheet`, `effective_date`.

---

## 10. Future Enhancements (Post-MVP)

- Support for additional file formats (DOCX, PPTX, XLSX) via automatic server-side conversion to print-ready PDF.
- Multi-printer / multi-branch routing, letting clients or admins choose a pickup location/printer.
- Delivery/courier integration for clients who cannot pick up in person.
- Additional PayMongo payment methods (cards, GCash, Maya) alongside QR Ph.
- Loyalty/rewards or bulk-order discounts for registered clients.
- In-app chat between client and admin for clarifying ambiguous instructions.
- Analytics dashboard for admin (sales, popular paper types, turnaround time).

---

## 11. Open Questions / Decisions Needed

- What is the minimum acceptable partial payment percentage, and is it configurable per order type (e.g., large bulk orders may require a higher down payment)?
- How many physical printers will be connected at launch, and do they differ in supported paper sizes/types (affects how much the guided form needs to adapt)?
- What is the target turnaround time (SLA) admin should be held to for reviewing paid orders?
- Should rejected/cancelled paid orders be refunded automatically via PayMongo's Refunds API, or handled manually at first?
- Do guest orders need any additional identity verification beyond tracking ID + contact match, to prevent someone else from viewing or claiming a client's order?
- Is pickup the only fulfillment method for v1, or should delivery be considered sooner?

---

## 12. Admin-Managed Printing Catalogue

### 12.1 Product and pricing rules

- **FR-35:** Shop admins can list, search, filter, create, edit, feature, reactivate, and archive catalogue products. Approvers and customers cannot manage products.
- **FR-36:** Public catalogue endpoints return active products only, with search, category, featured, and pagination support. Inactive product detail returns 404. The homepage displays every active product, with featured products identified by a badge and distinct styling.
- **FR-37:** Product prices are positive integer centavos. Admin peso input is converted exactly without floating-point rounding and rejects more than two decimal places.
- **FR-38:** Quantity bounds are positive and ordered. `default_spec` accepts existing print-spec fields and Epson vocabulary; catalogue orders always force Epson `copies=1` because finished-piece quantity is separate from printer copies.
- **FR-39:** A non-overwriting data migration seeds `2x2 ID Picture` (`2x2-id-picture`) at ₱30.00 per piece, quantity 1–99, active and featured, with A4 photo-paper color/high-quality/single-sided/portrait defaults and one Epson copy. Existing admin-edited products are never overwritten.

### 12.2 Catalogue ordering and historical integrity

- **FR-40:** A catalogue order contains one product and exactly one uploaded source file. The server resolves an active product, validates quantity, merges product defaults with submitted settings, and forces Epson `copies=1`. Homepage **Order this service** links include the product ID, and the catalogue order form preselects that service and its minimum quantity.
- **FR-41:** Product name, unit price, unit label, instructions, and quantity bounds are snapshotted at creation. Product edits, archival, file changes, page selection, color analysis, and specification changes never reprice an existing catalogue order.
- **FR-42:** Catalogue quote lines use `kind="catalogue"` with quantity, unit label, unit price, and amount; page/copy/side/color values are null. Existing custom quote lines remain `kind="custom"` and retain per-side calculations. Missing catalogue snapshots fail closed rather than falling back to custom pricing.
- **FR-43:** Guest, registered-customer, and admin-created catalogue orders use the existing payment, review, tracking, and notification lifecycle.

### 12.3 Staff quantity changes and approval safeguard

- **FR-44:** `PATCH /api/admin/orders/{id}/product/` is shop-admin-only and catalogue-only. It is allowed only for `draft`, `awaiting payment`, `pending review`, or `revision requested` orders with `amount_paid=0`; invalid quantities return 400 and unsafe state changes return 409.
- **FR-45:** Quantity changes validate against snapshotted bounds and reprice from the snapshotted unit price. They clear prepared output and page selection, reset `replaced_by_admin`, and add unchanged-status history and activity entries.
- **FR-46:** Approval is blocked with HTTP 409 unless every catalogue source file has `replaced_by_admin=True` and a non-empty `final_file`. The guard runs before automatic preparation, changes no status, creates no print job, and logs no successful approval. Customer re-upload clears preparation state and reactivates the guard.

### 12.4 Catalogue cover photos

- **FR-47:** Shop admins can upload, preview, replace, or remove an optional product cover photo from the catalogue editor and Django admin. Approvers and customers cannot upload covers. The admin API accepts multipart `cover_image` uploads; omitting the field preserves the current photo and JSON `null` removes it. Replaced or removed files are cleaned up after the database transaction commits.
- **FR-48:** Covers must be genuine JPEG, PNG, or WebP images with matching filename extensions, at most 5 MB and 20 megapixels. Public active-product responses expose an absolute `cover_image_url`. Homepage product cards and the catalogue service selector display the photo, with a generic placeholder when absent. Cover changes never alter historical order price snapshots.

### 12.5 In-house catalogue completion

- **FR-49:** A shop admin can complete a `pending review` catalogue order in-house after printing it directly, without creating or submitting an Epson print job. Approvers and custom-order customers cannot use this action. The order moves to `completed`, stamps `completed_at`, records status history and activity, and sends the existing completion notification.
- **FR-50:** In-house completion is blocked with HTTP 409 unless every catalogue source file has `replaced_by_admin=True` and a non-empty `final_file`. The guard runs before any status, history, activity, or printer change.

### 12.6 Catalogue API summary

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/catalogue/products/` | Public | Active products with search/category/featured/pagination |
| GET | `/api/catalogue/products/{slug}/` | Public | Active product detail |
| GET/POST | `/api/admin/catalogue/products/` | Shop admin | List all products / create product (JSON or multipart with optional cover) |
| GET/PATCH/DELETE | `/api/admin/catalogue/products/{id}/` | Shop admin | Detail / update, including multipart cover replacement / archive |
| POST | `/api/orders/quote/` | Public | Quote custom files or catalogue product + quantity |
| POST | `/api/orders/` | Public/account/admin | Create custom or catalogue order |
| PATCH | `/api/admin/orders/{id}/product/` | Shop admin | Adjust unpaid pre-approval catalogue quantity |
| POST | `/api/admin/orders/{id}/actions/complete_in_house/` | Shop admin | Complete a prepared catalogue order without an Epson job |
