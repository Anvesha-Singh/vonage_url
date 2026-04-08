# Sleemans Delivery CRM & POS System

## Overview
This application is a monolithic, server-side rendered Flask CRM and Point of Sale (POS) system designed specifically for a local delivery business (specifically handling gas cylinders like Butane and Propane). It handles customer management, order tracking, real-time inventory deduction, delivery route optimization, and synchronization with SumUp payment terminals.

The application uses **PostgreSQL** as its database, relying heavily on `psycopg2` for direct SQL execution rather than an ORM like SQLAlchemy, optimizing for complex analytical queries and raw performance.

## System Requirements & Environment Variables
To run this application, a `.env` file is required in the root directory with the following variables:
* `USERNAME` / `PASSWORD`: Hardcoded credentials for the basic authentication system.
* `DB_URL`: The PostgreSQL connection string.
* `ORS_API_KEY`: API key for OpenRouteService (used for delivery route optimization).
* `SUMUP_API_KEY`: API key for pulling external terminal transactions.

---

## 1. Database Helpers (Core Data Access)
These functions handle direct communication with the PostgreSQL database. The thought process here is to keep data-fetching logic modular and separate from the route handlers to allow for caching and reuse.

* `get_db()`
    * **What it does:** Establishes and returns a connection to the PostgreSQL database using `psycopg2.extras.DictCursor`.
    * **Thought process:** Using `DictCursor` ensures that database rows can be accessed via column names (like dictionaries) rather than integer indices, making the codebase much more readable and less prone to index-out-of-bounds errors if the schema changes.
* `clean_phone(phone)`
    * **What it does:** Strips `+`, `0`, and `44` prefixes from UK phone numbers to create a standardized integer-like string.
    * **Thought process:** Phone numbers are the primary identifier for customers in this system. Normalizing them prevents duplicate customer records if someone enters `07...` vs `+447...`.
* `get_customer(phone)` & `get_all_customers()`
    * **What it does:** Retrieves specific or all customer records. The bulk function also aggregates their `last_order_date`.
    * **Thought process:** Sorting customers by their last order date in the main search view ensures the most active customers are surfaced to the top of the directory.
* `get_last_orders_bulk()` & `get_orders(phone, limit)`
    * **What it does:** Fetches historical orders. The bulk function uses `STRING_AGG` and `DISTINCT ON` to create a lightweight summary string of a customer's most recent order.
    * **Thought process:** Instead of running an N+1 query (querying the DB for every single customer's last order on the search page), this runs one highly optimized SQL query to build a map in memory, dramatically speeding up the customer search page.
* `get_products_sold(start, end)` & `get_all_products()`
    * **What it does:** Retrieves product catalog and sales data. `get_all_products` is wrapped in `@lru_cache`.
    * **Thought process:** The product catalog rarely changes during daily operations. Caching it in server memory prevents unnecessary database hits every time the POS or Lookup page is loaded. The cache is manually busted via the `/reload_cache` route when inventory is edited.
* `get_delivery_schedule(town)`
    * **What it does:** Maps a customer's town to predefined delivery days (e.g., "Mon, Wed, Fri").

## 2. Analytics Helpers (Business Intelligence)
These functions power the Chart.js dashboards and forecasting features.

* `get_today_revenue()`
    * **What it does:** Splits revenue into Walk-in, Delivery, and SumUp matched totals, then compares it against the raw SumUp API total.
    * **Thought process:** This is a crucial reconciliation tool. It helps the business owner identify discrepancies between what was logged in the CRM vs. what was actually processed through the card terminals.
* `predict_next_calls(days)`
    * **What it does:** Analyzes a customer's historical order dates, calculates the average days between their orders, and predicts if they are due to call within the next `x` days (or if they are overdue).
    * **Thought process:** Moves the CRM from a passive record-keeper to a proactive sales tool, identifying missed recurring revenue.
* `get_inventory_status()`
    * **What it does:** Compares current stock levels against the trailing 7-day sales velocity to calculate how many "days left" of stock remain.

## 3. Core Application Routes (Views & Controllers)

### Authentication & Routing
* `@login_required` (Decorator) & `/login`
    * **What it does:** A lightweight middleware that checks for a simple `auth=1` cookie.
    * **Thought process:** Avoids the overhead of Flask-Login or complex session management for a system that is likely only used by a few internal staff members.

### Customer & Order Management
* `/search` (Homepage)
    * **What it does:** Renders the main customer directory with a real-time JavaScript text filter and product-based filtering.
* `/lookup`
    * **What it does:** The primary customer dashboard. It displays customer details, past orders, and an interactive POS-style grid to place new orders.
    * **Thought process:** Designed for speed on the phone. The operator can see the caller's history, calculate travel time to their address, and tap product tiles to instantly build a new order without leaving the page.
* `/save_order` & `/delete_order`
    * **What it does:** Handles the transaction of creating or removing an order.
    * **Thought process:** Uses `ON CONFLICT DO UPDATE` (Upsert) when modifying inventory. If an order is saved, it deducts stock. If deleted, it adds the stock back. This guarantees inventory accuracy even if a mistake is made.

### Routing & Logistics
* `/deliveries`
    * **What it does:** Generates the daily Run Sheet for drivers. It groups orders by town, formats them into a table, and dynamically generates an HTML/CSS matrix for loading the truck with specific gas weights (Net/Gross calculations).
* `/api/optimize_route`
    * **What it does:** Takes a list of UK postcodes, geocodes them using `postcodes.io`, and sends them to the OpenRouteService API to calculate the mathematically fastest round-trip route from the depot. It then re-sorts the DOM table via JavaScript to match the optimized route.
    * **Thought process:** Automates the complex traveling salesperson problem for the driver, saving time and fuel.
* `/api/travel_time`
    * **What it does:** Uses OpenStreetMap (OSRM) to calculate the exact driving time from the depot to a specific customer while on the phone.

### Export & Reporting
* `/export_delivery_excel`
    * **What it does:** Uses `openpyxl` to generate a heavily formatted, printable Excel spreadsheet of the daily run sheet, complete with the weight matrix and Hazmat (ADR) transport compliance footers.
* `/analytics`
    * **What it does:** Feeds JSON data into Chart.js to render visual representations of product performance, revenue splits, and inventory warnings.

### Point of Sale & External Integrations
* `/cash` & `/save_walkin`
    * **What it does:** A dedicated POS screen for walk-in customers that bypasses the need for a customer profile by assigning the order to a generic "Walk-in" database entry (`00000000000`).
* `/sync_sumup`
    * **What it does:** Polls the SumUp API for recent card transactions. It attempts to string-match the items sold on the terminal with the items in the PostgreSQL database. If matched, it automatically generates an order, deducts inventory, and marks it paid.
    * **Thought process:** Eliminates double-data entry. The system uses soft-matching (`display_name` vs `name`) to bridge the gap between how a product is named on a card reader vs. how it is tracked in the database.

### Inventory Management
* `/inventory`
    * **What it does:** A bulk-edit grid for products.
    * **Thought process (Archiving vs. Deleting):** If a user tries to delete a product, the code first attempts a hard SQL `DELETE`. If this fails (because PostgreSQL blocks it due to foreign key constraints from historical orders), the system catches the exception and does a "Soft Delete" (`is_active = FALSE`). This brilliantly prevents the database from breaking while keeping historical financial reports intact.

---
## Front-End Architecture
Rather than separating the frontend into a framework like React or Vue, the HTML, CSS, and JS are embedded as string templates directly in the Python files using f-strings.

**Why?**
1.  **Zero-Build Pipeline:** The app requires no Node.js, Webpack, or build steps. It deploys instantly.
2.  **Server-Side State:** By injecting Python variables directly into the DOM (e.g., `let items = {{}};`), the frontend instantly inherits the backend state without needing complex REST API calls for initial page loads.
3.  **Tailored Print CSS:** The application includes highly specific `@media print` CSS directives ensuring that when run sheets are printed for drivers, navbars are hidden, fonts are resized, and matrices fit perfectly on a landscape A4 page.