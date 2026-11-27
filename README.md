# DineFlow | Restaurant Management System

A unified **5-screen live dinner-service dashboard** built with **Python & Django (MVT/MVC)** for **CSE 451 – Software Engineering (Autumn 2026, IUB)**.

> **Documentation:** Full SRS, SDS, UML/DFD, Coding Standards, Sphinx Docs, Code Review Findings, and Testing reports are available in the **[GitHub Wiki](https://github.com/SalmanBhuiyan65/DineFlow-Restaurant-Management-System/wiki)**.

---

## Team Members & 9-Feature Ownership (3×3 Split)

| Member | Role | Assigned Features (3 per member) | Django App |
| :--- | :--- | :--- | :--- |
| **1. Salman** | Waitstaff / Floor & Kitchen Lead | **DF-01** Floor Map & Table Session Lifecycle<br>**DF-02** Order Entry & Modification<br>**DF-03** Kitchen Display System (KDS) & Ticket Bump | `floor_kitchen/` |
| **2. Orin** | Host / Reception & Menu Lead | **DF-04** Reservations & Booking Timeline<br>**DF-05** Walk-in Waitlist & Best-Fit Seating<br>**DF-06** Menu Catalog & Category Management | `bookings_menu/` |
| **3. Hasibul** | Manager / Cashier & Analytics Lead | **DF-07** Itemized Billing & Idempotent Payment Recording<br>**DF-08** Menu Engineering Analytics (Stars/Plowhorses/Puzzles/Dogs)<br>**DF-09** Daily Takings & Shift Summary Reports | `billing_analytics/` |

---

## Prerequisites
- **Python 3.11+** (tested on Python 3.13)
- **Git**

---

## How to Run Locally

1. **Create & activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply migrations & seed realistic dinner-service data:**
   ```bash
   python manage.py migrate
   python manage.py seed_dineflow
   ```

4. **Run unit tests & coding standard checks:**
   ```bash
   python manage.py test
   flake8 .
   ```

5. **Start the development server:**
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` and use the **1-Click Demo Role Switcher** (`Host`, `Waiter`, `Kitchen`, `Manager`) or sign in with `salman` / `dineflow123`.

---

## End-to-End Live Demo Flow
1. **Bookings & Waitlist (`/bookings/`):** Seat **Nabila** (or add a walk-in and click **Auto-Seat Best-Fit**).
2. **Floor (`/`):** Select **T2**, add dishes with a kitchen note, and click **Send Drafts to Kitchen** (table turns `Cooking`).
3. **Kitchen (`/kitchen/`):** View oldest-first queue (tickets `>= 12 min` highlight **LATE**), click **Bump Ticket** (Floor updates to `Eating`).
4. **Floor (`/`):** Click **Request Bill** on the table.
5. **Billing (`/billing/`):** View itemized bill + 5% VAT, print receipt, and click **Record Cash / Card / bKash** (table resets to `Empty`; duplicate payment is idempotently ignored).
6. **Takings (`/takings/`) & Menu Analytics (`/analytics/`):** Verify live sales, hourly breakdown, previous-day comparison, and dish quadrants.

---

## Git Branching & PR Workflow (Modeled on Sample Repos)
- `main`: Production-ready, reviewed releases.
- `development`: Integration branch for tested features.
- Feature branches per member:
  - `salman-floor-table-sessions`, `salman-order-entry`, `salman-kitchen-display`
  - `orin-reservations-timeline`, `orin-waitlist-best-fit`, `orin-menu-catalog`
  - `hasibul-billing-idempotent`, `hasibul-menu-analytics`, `hasibul-takings-report`
- Workflow: `git checkout -b <branch>` → implement & `python manage.py test` → `flake8 .` → push & open Pull Request → review & merge into `development` / `main`.
