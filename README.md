# Sleemans Delivery CRM & POS System

## Overview
This application is a monolithic, server-side rendered Flask CRM and Point of Sale (POS) system designed specifically for a local delivery business (specifically handling gas cylinders like Butane and Propane)[cite: 2]. It handles customer management, order tracking, real-time inventory deduction, delivery route optimization, dynamic tax/VAT calculation, and synchronization with SumUp payment terminals[cite: 2].

The application uses **PostgreSQL** as its database, relying heavily on `psycopg2` for direct SQL execution rather than an ORM like SQLAlchemy, optimizing for complex analytical queries and raw performance[cite: 2].

## System Requirements & Environment Variables
To run this application, a `.env` file is required in the root directory with the following variables[cite: 2]:
* `USERNAME` / `PASSWORD`: Hardcoded credentials for the basic authentication system[cite: 2].
* `DB_URL`: The PostgreSQL connection string[cite: 2].
* `ORS_API_KEY`: API key for OpenRouteService (used for delivery route optimization)[cite: 2].
* `SUMUP_API_KEY`: API key for pulling external terminal transactions[cite: 2].

---

## 1. Database Helpers (Core Data Access)
These functions handle direct communication with the PostgreSQL database[cite: 2]. The thought process here is to keep data-fetching logic modular and separate from the route handlers to allow for caching and reuse[cite: 2].

* **`get_db()`**
    * **What it does:** Establishes and returns a connection to the PostgreSQL database using `psycopg2.extras.DictCursor`[cite: 2].
    * **Thought process:** Using `DictCursor` ensures that database rows can be accessed via column names (like dictionaries) rather than integer indices, making the codebase much more readable and less prone to index-out-of-bounds errors if the schema changes[cite: 2].
* **`clean_phone(phone)`**
    * **What it does:** Strips `+`, `0`, and `44` prefixes from UK phone numbers to create a standardized integer-like string[cite: 2].
    * **Thought process:** Phone numbers are the primary identifier for customers in this system[cite: 2]. Normalizing them prevents duplicate customer records if someone enters `07...` vs `+447...`[cite: 2].
* **`get_customer(phone)` & `get_all_customers()`**
    * **What it does:** Retrieves specific or all customer records[cite: 2]. The bulk function also aggregates their `last_order_date`[cite: 2].
    * **Thought process:** Sorting customers by their last order date in the main search view ensures the most active customers are surfaced to the top of the directory[cite: 2].
* **`get_last_orders_bulk()` & `get_orders(phone, limit)`**
    * **What it does:** Fetches historical orders[cite: 2]. The bulk function uses `STRING_AGG` and `DISTINCT ON` to create a lightweight summary string of a customer's most recent order[cite: 2].
    * **Thought process:** Instead of querying the DB for every single customer's last order on the search page, this runs one highly optimized SQL query to build a map in memory, dramatically speeding up the customer search page[cite: 2].
* **`get_products_sold(start, end)` & `get_all_products()`**
    * **What it does:** Retrieves product catalog and sales data[cite: 2]. `get_all_products` is wrapped in `@lru_cache`[cite: 2].
    * **Thought process:** The product catalog rarely changes during daily operations[cite: 2]. Caching it in server memory prevents unnecessary database hits every time the POS or Lookup page is loaded[cite: 2]. The cache is manually busted via the `/reload_cache` route when inventory is edited[cite: 2].
* **`get_delivery_schedule(town)`**
    * **What it does:** Maps a customer's town to predefined delivery days (e.g., "Mon, Wed, Fri")[cite: 2].

## 2. Analytics Helpers (Business Intelligence)
These functions power the Chart.js dashboards and forecasting features[cite: 2].

* **`get_today_revenue()`**
    * **What it does:** Splits revenue into Walk-in, Delivery, and SumUp matched totals, then compares it against the raw SumUp API total[cite: 2].
    * **Thought process:** This is a crucial reconciliation tool[cite: 2]. It helps the business owner identify discrepancies between what was logged in the CRM vs. what was actually processed through the card terminals[cite: 2].
* **`predict_next_calls(days)`**
    * **What it does:** Analyzes a customer's historical order dates, calculates the average days between their orders, and predicts if they are due to call within the next `x` days[cite: 2].
    * **Thought process:** Moves the CRM from a passive record-keeper to a proactive sales tool, identifying missed recurring revenue[cite: 2].
* **`get_inventory_status()`**
    * **What it does:** Compares current stock levels against the trailing 7-day sales velocity to calculate how many "days left" of stock remain[cite: 2].

## 3. Core Application Routes (Views & Controllers)

### Authentication & Routing
* **`@login_required` (Decorator) & `/login`**
    * **What it does:** A lightweight middleware that checks for a simple `auth=1` cookie[cite: 2].
    * **Thought process:** Avoids the overhead of Flask-Login or complex session management for a system that is likely only used by a few internal staff members[cite: 2].

### Customer & Order Management
* **`/search` (Homepage)**
    * **What it does:** Renders the main customer directory with a real-time JavaScript text filter and product-based filtering[cite: 2].
* **`/lookup` & `/cash` (POS Core)**
    * **What it does:** The primary customer dashboard and Walk-in POS[cite: 2]. It displays history, calculates travel times, and features an interactive product grid[cite: 2].
    * **Thought process:** Designed for speed on the phone[cite: 2]. Users can tap product tiles to instantly build orders[cite: 2]. It features a dynamic "Other" item builder that instantly generates custom tiles in the DOM with bespoke names, custom prices, and independent `+`/`-` quantity controls.
* **`/save_order` & `/delete_order`**
    * **What it does:** Handles the transaction of creating or removing an order[cite: 2].
    * **Thought process:** Uses `ON CONFLICT DO UPDATE` (Upsert) when modifying inventory[cite: 2]. If an order is saved, it deducts stock; if deleted, it adds the stock back, guaranteeing accuracy[cite: 2].

### Document Generation & Tax Compliance
* **`/print_doc`**
    * **What it does:** Dynamically generates printable Invoices and Receipts for specific orders.
    * **Thought process:** Features a robust VAT engine. Tax rates are locked into the `order_items` table at the exact time of sale. This ensures that historical receipts remain mathematically accurate even if a product's base tax rate changes in the future. The frontend dynamically groups and summarizes sub-totals by tax bracket (e.g., 5% vs 20%) to ensure HMRC compliance.

### Routing & Logistics
* **`/deliveries`**
    * **What it does:** Generates the daily Run Sheet for drivers[cite: 2]. Groups orders by town, formats them into a table, and generates an HTML/CSS matrix for loading the truck with specific gas weights (Net/Gross calculations)[cite: 2].
* **`/api/optimize_route`**
    * **What it does:** Takes a list of UK postcodes, geocodes them using `postcodes.io`, and sends them to the OpenRouteService API to calculate the mathematically fastest round-trip route from the depot[cite: 2]. It then re-sorts the DOM table via JavaScript[cite: 2].
    * **Thought process:** Automates the complex traveling salesperson problem for the driver, saving time and fuel[cite: 2].

### Export & Reporting
* **`/export_delivery_excel`**
    * **What it does:** Uses `openpyxl` to generate a heavily formatted, printable Excel spreadsheet of the daily run sheet, complete with the weight matrix and Hazmat (ADR) transport compliance footers[cite: 2].
* **`/analytics`**
    * **What it does:** Feeds JSON data into Chart.js to render visual representations of product performance, revenue splits, and inventory warnings[cite: 2].

### Point of Sale & External Integrations
* **`/sync_sumup`**
    * **What it does:** Polls the SumUp API for recent card transactions[cite: 2]. Attempts to string-match the items sold on the terminal with the items in the PostgreSQL database[cite: 2]. If matched, it automatically generates an order, deducts inventory, and marks it paid[cite: 2].
    * **Thought process:** Eliminates double-data entry[cite: 2]. Uses soft-matching (`display_name` vs `name`) to bridge the gap between how a product is named on a card reader vs. how it is tracked in the database[cite: 2].

### Inventory Management
* **`/inventory`**
    * **What it does:** A bulk-edit grid for products featuring native HTML5 drag-and-drop sorting and HTML5 color pickers for tile customization.
    * **Thought process (Archiving vs. Deleting):** If a user tries to delete a product, the code first attempts a hard SQL `DELETE`[cite: 2]. If this fails (because PostgreSQL blocks it due to foreign key constraints from historical orders), the system catches the exception and does a "Soft Delete" (`is_active = FALSE`)[cite: 2]. This prevents the database from breaking while keeping historical financial reports intact[cite: 2].

---
## Front-End Architecture
Rather than separating the frontend into a framework like React or Vue, the HTML, CSS, and JS are embedded as string templates directly in the Python files using f-strings[cite: 2].

**Why?**
1.  **Zero-Build Pipeline:** The app requires no Node.js, Webpack, or build steps[cite: 2]. It deploys instantly[cite: 2].
2.  **Server-Side State:** By injecting Python variables directly into the DOM (e.g., `let items = {{}};`), the frontend instantly inherits the backend state without needing complex REST API calls for initial page loads[cite: 2]. Advanced DOM manipulation (like dynamic custom product tiles and drag-and-drop sorting) is handled entirely via Vanilla JavaScript.
3.  **Tailored Print CSS:** The application includes highly specific `@media print` CSS directives ensuring that when run sheets are printed for drivers, navbars are hidden, fonts are resized, and matrices fit perfectly on a landscape A4 page[cite: 2].