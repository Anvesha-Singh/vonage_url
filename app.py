from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

import psycopg2
import psycopg2.extras
import re
import json
from datetime import datetime
from flask import Flask, request, redirect, jsonify

app = Flask(__name__)

# ── DB helpers ────────────────────────────────────────────────────────────────
DB_URL = os.getenv("DB_URL")  
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    conn = psycopg2.connect(
        DB_URL, 
        cursor_factory=psycopg2.extras.DictCursor,
        sslmode='require' 
    )
    return conn

def normalize_phone(phone):
    if not phone:
        return None
    clean = re.sub(r'\D', '', str(phone))
    if clean.startswith('0'):
        clean = '44' + clean[1:]
    elif len(clean) == 10:
        clean = '44' + clean
    return f"+{clean}" if clean else None

def get_customer(phone):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE phone = %s", (phone,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None

def get_orders(phone):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT o.id, o.order_date, o.notes, p.name AS product, oi.quantity
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products   p  ON oi.product_id = p.id
        WHERE o.phone = %s
        ORDER BY o.order_date DESC, o.id DESC
    ''', (phone,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    orders = {}
    for row in rows:
        oid = row["id"]
        if oid not in orders:
            orders[oid] = {"date": row["order_date"], "notes": row["notes"] or "", "items": []}
        orders[oid]["items"].append({"product": row["product"], "qty": row["quantity"]})
    return list(orders.values())

def get_all_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def get_all_customers():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.cookies.get("auth") == "1":
            return f(*args, **kwargs)
        return redirect("/login")
    return wrapper

# ── Shared HTML assets ────────────────────────────────────────────────────────

STYLE = """
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0e0f13;
    --surface: #16181f;
    --border: #252830;
    --accent: #f97316;
    --accent2: #fb923c;
    --text: #e8eaf0;
    --muted: #6b7280;
    --danger: #ef4444;
    --success: #22c55e;
    }

    .light {
    --bg: #f6f7fb;
    --surface: #ffffff;
    --border: #e5e7eb;
    --text: #111827;
    --muted: #6b7280;
    .customer-hero {
    background: linear-gradient(135deg, #ffffff, #f3f4f6);
    }

    .order-card {
    background: #ffffff;
    }

    .product-tile {
    background: #ffffff;
    }

    tr:hover td {
    background: rgba(0,0,0,.04);
    }

    .order-item-tag {
    background: #f9fafb;
    }

    .badge {
    background: rgba(249,115,22,.1);
    }
    }

  body { font-family: 'Syne', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

  nav {
    display: flex; align-items: center; gap: 24px;
    padding: 16px 32px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  nav .logo { font-size: 1.1rem; font-weight: 800; letter-spacing: -0.5px; color: var(--accent); text-decoration: none; margin-right: auto; }
  nav a { font-size: .85rem; font-weight: 600; color: var(--muted); text-decoration: none; padding: 6px 14px; border-radius: 6px; transition: all .15s; }
  nav a:hover { color: var(--text); background: var(--border); }

  .page      { max-width: 960px;  margin: 0 auto; padding: 36px 24px; }
  .page-wide { max-width: 1200px; margin: 0 auto; padding: 36px 24px; }

  h1 { font-size: 2rem; font-weight: 800; letter-spacing: -1px; }
  h2 { font-size: 1.4rem; font-weight: 700; letter-spacing: -.5px; }
  h3 { font-size: .85rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 1.2px; }

  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; }
  .card + .card { margin-top: 16px; }

  .customer-hero {
    background: linear-gradient(135deg, #1a1c24, #1f212c);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 28px 32px; display: flex; align-items: center; gap: 20px;
  }
  .avatar {
    width: 56px; height: 56px; background: var(--accent); border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem; font-weight: 800; color: #fff; flex-shrink: 0;
  }
  .info h2 { font-size: 1.5rem; }
  .meta { font-family: 'DM Mono', monospace; font-size: .8rem; color: var(--muted); margin-top: 4px; }
  .badge {
    display: inline-block; background: rgba(249,115,22,.15); color: var(--accent);
    border: 1px solid rgba(249,115,22,.3); font-family: 'DM Mono', monospace;
    font-size: .72rem; padding: 3px 10px; border-radius: 99px; margin-left: 8px;
  }

  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'Syne', sans-serif; font-size: .85rem; font-weight: 700;
    padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer;
    text-decoration: none; transition: all .15s;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent2); transform: translateY(-1px); }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }

  .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr)); gap: 10px; margin: 16px 0; }
  .product-tile {
    background: var(--bg); border: 2px solid var(--border); border-radius: 10px;
    padding: 16px 12px; text-align: center; cursor: pointer; transition: all .15s;
    user-select: none; position: relative;
  }
  .product-tile:hover { border-color: var(--muted); }
  .product-tile.selected { border-color: var(--accent); background: rgba(249,115,22,.08); }
  .p-name { font-size: .82rem; font-weight: 600; line-height: 1.3; }
  .p-qty  { display: block; margin-top: 8px; font-family: 'DM Mono', monospace; font-size: 1.5rem; color: var(--accent); min-height: 1.8rem; }
  .p-reset { position: absolute; top: 6px; right: 8px; font-size: .68rem; color: var(--muted); display: none; }
  .product-tile.selected .p-reset { display: block; }

  .order-list { display: flex; flex-direction: column; gap: 10px; }
  .order-card { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; display: flex; gap: 20px; align-items: flex-start; }
  .order-date { font-family: 'DM Mono', monospace; font-size: .75rem; color: var(--muted); white-space: nowrap; padding-top: 3px; min-width: 96px; }
  .order-items { display: flex; flex-wrap: wrap; gap: 6px; }
  .order-item-tag { font-size: .78rem; font-weight: 600; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; }
  .order-item-tag span { color: var(--accent); margin-left: 4px; }

  input[type=text], input[type=date], input[type=tel] {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-family: 'DM Mono', monospace; font-size: .85rem;
    padding: 10px 14px; outline: none; transition: border-color .15s; width: 100%;
  }
  input:focus { border-color: var(--accent); }
  label { font-size: .8rem; color: var(--muted); font-weight: 600; display: block; margin-bottom: 6px; }
  .form-group { margin-bottom: 18px; }

  table { width: 100%; border-collapse: collapse; }
  th { font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--border); }
  td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: .88rem; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,.02); }

  .pill { font-family: 'DM Mono', monospace; font-size: .72rem; background: var(--surface); border: 1px solid var(--border); border-radius: 99px; padding: 3px 10px; color: var(--muted); }
  .section-header { display: flex; align-items: center; justify-content: space-between; margin: 28px 0 14px; }
  .empty { text-align: center; padding: 40px; color: var(--muted); font-size: .88rem; }
  .unknown-banner { background: rgba(239,68,68,.08); border: 1px solid rgba(239,68,68,.3); color: #fca5a5; border-radius: var(--radius); padding: 24px 28px; }
  #toast { position: fixed; bottom: 24px; right: 24px; background: var(--success); color: #fff; font-weight: 700; padding: 12px 22px; border-radius: 8px; font-size: .85rem; opacity: 0; pointer-events: none; transition: opacity .3s; z-index: 999; }
  #toast.show { opacity: 1; }
</style>
"""

NAV = """
<nav>
  <a class="logo" href="/">Sleemans</a>
  <a href="/search">Customers</a>
  <a href="#" onclick="toggleTheme()" id="theme-icon">&#9728;</a>
</nav>
"""

TOAST_JS = '''<div id="toast"></div><script>function showToast(m){const t=document.getElementById("toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2500);} 
    function toggleTheme(){
        const isLight = document.body.classList.toggle("light");
        localStorage.setItem("theme", isLight ? "light" : "dark");
        document.getElementById("theme-icon").innerHTML = isLight ? "&#9790;" : "&#9728;";
        }
        (function(){
        const saved = localStorage.getItem("theme");
        if(saved==="light"){
            document.body.classList.add("light");
        }
    })();
</script>'''

def page(title, body, wide=False):
    cls = "page-wide" if wide else "page"
    return f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">{STYLE}<title>{title} – Sleemans</title></head><body>{NAV}<div class="{cls}">{body}</div>{TOAST_JS}</body></html>'

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return redirect("/search")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if u == USERNAME and p == PASSWORD:
            resp = redirect("/search")
            resp.set_cookie("auth", "1", max_age=60*60*24*30)  # 30 days
            return resp

    body = '''
    <h1 style="margin-bottom:24px">Login</h1>
    <div class="card">
      <form method="POST">
        <div class="form-group">
          <label>Username</label>
          <input type="text" name="username" required>
        </div>
        <div class="form-group">
          <label>Password</label>
          <input type="password" name="password" required>
        </div>
        <button class="btn btn-primary">Login</button>
      </form>
    </div>
    '''
    return page("Login", body)

@app.route("/lookup")
@login_required
def lookup():
    raw   = request.args.get("phone", "")
    phone = normalize_phone(raw)
    user  = get_customer(phone) if phone else None
    orders = get_orders(phone) if phone else []

    if not phone:
        body = f'<div class="unknown-banner"><h2>Invalid number</h2><p class="meta" style="margin-top:6px">{raw}</p></div>'

    elif not user:
        body = f'''<div class="unknown-banner">
        <h2>Unknown caller</h2>
        <p class="meta" style="margin-top:6px">{phone}</p>
        <div style="margin-top:16px;display:flex;gap:10px">
            <a href="/add_customer?phone={phone}" class="btn btn-primary">+ Add Customer</a>
            <a href="/order?phone={phone}" class="btn btn-ghost">+ Add Order Anyway</a>
        </div>
        </div>'''

    else:
        initial = (user['name'] or '?')[0].upper()
        gas_line = f'<div class="meta" style="margin-top:4px;color:var(--accent)">Usual: {user["gas_request"]}</div>' if user.get('gas_request') and str(user['gas_request']) not in ('nan', '') else ''

        if orders:
            order_cards = ""
            for o in orders:
                tags = "".join(f'<span class="order-item-tag">{i["product"]}<span>x{i["qty"]}</span></span>' for i in o["items"])
                order_cards += f'<div class="order-card"><div class="order-date">{o["date"]}</div><div class="order-items">{tags}</div></div>'
        else:
            order_cards = '<div class="empty">No previous orders on record.</div>'

        body = f'''
        <div class="customer-hero">
          <div class="avatar">{initial}</div>
          <div class="info">
            <h2>{user["name"]} <span class="badge">{phone}</span></h2>
            <div class="meta">{user.get("address","")} &middot; {user.get("town","")} &middot; {user.get("postcode","")}</div>
            {gas_line}
          </div>
          <div style="margin-left:auto;display:flex;gap:8px">
            <a href="/edit_customer?phone={phone}" class="btn btn-ghost">Edit</a>
            <a href="/order?phone={phone}" class="btn btn-primary">+ Add Order</a>
          </div>
        </div>

        <div class="section-header" style="margin-top:32px">
          <h3>Order History</h3>
          <span class="pill">{len(orders)} orders</span>
        </div>
        <div class="order-list">{order_cards}</div>'''

    return page("Lookup", body)


@app.route("/order")
@login_required
def order_page():
    phone_raw = request.args.get("phone", "")
    phone     = normalize_phone(phone_raw) or phone_raw
    products  = get_all_products()

    tiles = ""
    for p in products:
        tiles += f'''<div class="product-tile" id="tile-{p["id"]}" onclick="addQty({p["id"]})">
          <div class="p-name">{p["name"]}</div>
          <div class="p-qty" id="qty-{p["id"]}"></div>
          <span class="p-reset" onclick="event.stopPropagation();resetTile({p["id"]})">&#x2715; clear</span>
        </div>'''

    if phone:
        phone_field = f'<input type="hidden" name="phone" value="{phone}">'
        cancel_btn  = f'<a href="/lookup?phone={phone}" class="btn btn-ghost">Cancel</a>'
        user = get_customer(phone)
        hero = ""
        if user:
            hero = f'<div class="customer-hero" style="margin-bottom:24px"><div class="avatar">{user["name"][0].upper()}</div><div class="info"><h2>{user["name"]}</h2><div class="meta">{user.get("address","")} &middot; {user.get("town","")} &middot; {user.get("postcode","")}</div></div><a href="/lookup?phone={phone}" class="btn btn-ghost" style="margin-left:auto">&#x2190; Profile</a></div>'
    else:
        phone_field = '<div class="form-group"><label>Phone Number</label><input type="tel" name="phone" placeholder="+44 7700 900000" required></div>'
        cancel_btn  = ""
        hero        = ""

    body = f'''
    <h1 style="margin-bottom:24px">Add Order</h1>
    {hero}
    <div class="card">
      <form method="POST" action="/save_order">
        {phone_field}
        <div class="form-group">
          <label>Order Date</label>
          <input type="date" name="date" value="{datetime.today().date()}" style="max-width:200px">
        </div>
        <div class="form-group">
          <label>Products &nbsp;<span style="color:var(--muted);font-weight:400;text-transform:none;letter-spacing:0">tap once = qty 1, tap again for more</span></label>
          <div class="product-grid">{tiles}</div>
        </div>
        <input type="hidden" name="items" id="items-input">
        <div style="display:flex;gap:10px;margin-top:8px">
          <button type="submit" class="btn btn-primary" onclick="return prepareSubmit()">Save Order</button>
          {cancel_btn}
        </div>
      </form>
    </div>

    <script>
    const items = {{}};
    function addQty(id) {{
      items[id] = (items[id] || 0) + 1;
      document.getElementById("qty-" + id).textContent = items[id];
      document.getElementById("tile-" + id).classList.add("selected");
    }}
    function resetTile(id) {{
      delete items[id];
      document.getElementById("qty-" + id).textContent = "";
      document.getElementById("tile-" + id).classList.remove("selected");
    }}
    function prepareSubmit() {{
      if (!Object.keys(items).length) {{ alert("Select at least one product."); return false; }}
      document.getElementById("items-input").value = JSON.stringify(items);
      return true;
    }}
    </script>'''

    return page("Add Order", body)


@app.route("/save_order", methods=["POST"])
@login_required
def save_order():
    phone_raw = request.form.get("phone", "")
    phone     = normalize_phone(phone_raw) or phone_raw
    date      = request.form.get("date") or str(datetime.today().date())

    try:
        items = json.loads(request.form.get("items", "{}"))
    except Exception:
        items = {}

    if not items:
        return redirect(f"/order?phone={phone}")

    conn = get_db()
    cur = conn.cursor()
    if not get_customer(phone):
        cur.execute("INSERT INTO customers (phone, name) VALUES (%s, %s)", (phone, "Unknown"))
    cur.execute("INSERT INTO orders (phone, order_date) VALUES (%s, %s) RETURNING id", (phone, date))
    oid = cur.fetchone()[0]

    for pid, qty in items.items():
        cur.execute("INSERT INTO order_items (order_id, product_id, quantity) VALUES (%s, %s, %s)", (oid, int(pid), int(qty)))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(f"/lookup?phone={phone}")


@app.route("/search")
@login_required
def search():
    customers = get_all_customers()

    rows = ""
    for u in customers:
        name     = u.get('name', '') or ''
        phone    = u.get('phone', '') or ''
        town     = u.get('town', '') or ''
        postcode = u.get('postcode', '') or ''
        gas      = u.get('gas_request', '') or ''
        initial  = (name or '?')[0].upper()
        gas_disp = gas if gas not in ('nan', '') else ''

        rows += f'''<tr data-name="{(name or '').lower()}" 
                    data-phone="{phone or ''}" 
                    data-address="{(u.get('address') or '').lower()}" 
                    data-postcode="{(u.get('postcode') or '').lower()}" 
                    data-gas="{(u.get('gas_request') or '').lower()}">
          <td>
            <div style="display:flex;align-items:center;gap:10px">
              <div style="width:32px;height:32px;background:var(--accent);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem;flex-shrink:0">{initial}</div>
              {name}
            </div>
          </td>
          <td><span class="pill">{phone}</span></td>
          <td style="color:var(--muted);font-size:.82rem">{u.get('address','')}, {town}, {postcode}</td>
          <td style="color:var(--muted);font-size:.82rem">{gas_disp}</td>
          <td>
            <a href="/lookup?phone={phone}" class="btn btn-ghost" style="padding:6px 12px;font-size:.78rem">View</a>
            <a href="/order?phone={phone}"  class="btn btn-primary" style="padding:6px 12px;font-size:.78rem;margin-left:6px">+ Order</a>
          </td>
        </tr>'''

    body = f'''
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <h1>Customers <span class="pill" style="font-size:.9rem;vertical-align:middle">{len(customers)}</span></h1>
    <div style="display:flex;gap:10px">
        <a href="/add_customer" class="btn btn-ghost">+ Add Customer</a>
        <a href="/order" class="btn btn-primary">+ Manual Order</a>
    </div>
    </div>

    <div style="display:flex;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
    <input type="text" id="search-input" placeholder="Search by name, phone, address, postcode..." oninput="filterTable()" style="flex:1;min-width:200px;max-width:360px">
    <input type="text" id="gas-search" placeholder="Filter by Usual Gas" oninput="filterTable()" style="min-width:180px;max-width:220px">
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <table>
        <thead><tr><th>Name</th><th>Phone</th><th>Location</th><th>Usual Gas</th><th>Actions</th></tr></thead>
        <tbody id="table-body">{rows}</tbody>
      </table>
      {'<div class="empty">No customers yet. Run setup_db.py with your Excel file.</div>' if not customers else ''}
    </div>

    <script>
    function filterTable() {{
    const q = document.getElementById("search-input").value.toLowerCase();
    const gasQ = document.getElementById("gas-search").value.toLowerCase();

    document.querySelectorAll("#table-body tr").forEach(r => {{
        const name = r.dataset.name || "";
        const phone = r.dataset.phone || "";
        const addr = r.dataset.address || "";
        const postcode = r.dataset.postcode || "";
        const gas = r.dataset.gas || "";

        const matchGeneral = name.includes(q) || phone.includes(q) || addr.includes(q) || postcode.includes(q);
        const matchGas = gas.includes(gasQ);

        r.style.display = (matchGeneral && matchGas) ? "" : "none";
    }});
    }}
    </script>'''

    return page("Customers", body, wide=True)

@app.route("/add_customer", methods=["GET", "POST"])
@login_required
def add_customer():
    phone_prefill = request.args.get("phone", "")
    if request.method == "POST":
        phone = normalize_phone(request.form.get("phone"))
        name  = request.form.get("name")
        address = request.form.get("address")
        town = request.form.get("town")
        postcode = request.form.get("postcode")

        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO customers (phone, name, address, town, postcode)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (phone) DO UPDATE
            SET name = EXCLUDED.name,
                address = EXCLUDED.address,
                town = EXCLUDED.town,
                postcode = EXCLUDED.postcode
        ''', (phone, name, address, town, postcode))
        conn.commit()
        cur.close()
        conn.close()

        if "save_and_order" in request.form:
            return redirect(f"/order?phone={phone}")
        return redirect("/search")

    body = f'''
    <h1 style="margin-bottom:24px">Add Customer</h1>
    <div class="card">
      <form method="POST">
        <div class="form-group">
          <label>Name</label>
          <input type="text" name="name" required>
        </div>
        <div class="form-group">
          <label>Phone</label>
          <input type="tel" name="phone" value="{phone_prefill}" required>
        </div>
        <div class="form-group">
          <label>Address</label>
          <input type="text" name="address">
        </div>
        <div class="form-group">
          <label>Town</label>
          <input type="text" name="town">
        </div>
        <div class="form-group">
          <label>Postcode</label>
          <input type="text" name="postcode">
        </div>

        <div style="display:flex;gap:10px">
          <button class="btn btn-primary">Save</button>
          <button name="save_and_order" class="btn btn-ghost">Save & Add Order</button>
        </div>
      </form>
    </div>
    '''
    return page("Add Customer", body)

@app.route("/edit_customer", methods=["GET", "POST"])
@login_required
def edit_customer():
    phone = normalize_phone(request.args.get("phone"))

    if request.method == "POST":
        phone = normalize_phone(request.form.get("phone"))
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            UPDATE customers
            SET name=%s, address=%s, town=%s, postcode=%s, gas_request=%s
            WHERE phone=%s
        ''', (
            request.form.get("name"),
            request.form.get("address"),
            request.form.get("town"),
            request.form.get("postcode"),
            request.form.get("gas_request"),
            phone
        ))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(f"/lookup?phone={phone}")

    user = get_customer(phone)

    body = f'''
    <h1 style="margin-bottom:24px">Edit Customer</h1>
    <div class="card">
      <form method="POST">
        <input type="hidden" name="phone" value="{phone}">
        <div class="form-group"><label>Name</label><input type="text" name="name" value="{user.get("name","")}"></div>
        <div class="form-group"><label>Address</label><input type="text" name="address" value="{user.get("address","")}"></div>
        <div class="form-group"><label>Town</label><input type="text" name="town" value="{user.get("town","")}"></div>
        <div class="form-group"><label>Postcode</label><input type="text" name="postcode" value="{user.get("postcode","")}"></div>
        <div class="form-group"><label>Usual Gas Request</label><input type="text" name="gas_request" value="{user.get("gas_request","")}"></div>

        <button class="btn btn-primary">Save</button>
      </form>
    </div>
    '''
    return page("Edit Customer", body)

@app.route("/api/orders")
@login_required
def api_orders():
    phone = normalize_phone(request.args.get("phone", ""))
    return jsonify(get_orders(phone) if phone else [])


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)