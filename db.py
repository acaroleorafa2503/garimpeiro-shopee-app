
import sqlite3
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "data" / "garimpeiro.db"

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _ensure_column(con, table, col, decl):
    cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

def init_db():
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        keyword TEXT NOT NULL,
        category TEXT,
        operation_model TEXT,
        seasonality_type TEXT,
        peak_months TEXT,
        status TEXT DEFAULT 'radar',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        captured_at TEXT NOT NULL,
        price_avg REAL,
        demand_signal REAL,
        competitor_count REAL,
        review_signal REAL,
        supplier_cost REAL,
        shipping_in REAL,
        packaging REAL,
        marketplace_pct REAL,
        tax_pct REAL,
        discount_pct REAL,
        ads_pct REAL,
        losses_pct REAL,
        demanda REAL,
        tendencia REAL,
        sazonalidade REAL,
        concorrencia REAL,
        margem REAL,
        fornecedor REAL,
        prontidao REAL,
        logistica REAL,
        devolucao REAL,
        visual REAL,
        kit REAL,
        recorrencia REAL,
        comoditizacao REAL,
        escala REAL,
        score REAL,
        classification TEXT,
        profit_est REAL,
        margin_est_pct REAL,
        why_now TEXT,
        notes TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        supplier_name TEXT NOT NULL,
        supplier_url TEXT,
        contact TEXT,
        unit_cost REAL,
        moq REAL,
        shipping_est REAL,
        lead_time_days REAL,
        ready_to_ship INTEGER DEFAULT 1,
        prep_type TEXT DEFAULT 'pronto',
        notes TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS public_search_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        captured_at TEXT NOT NULL,
        query TEXT NOT NULL,
        title TEXT,
        url TEXT,
        description TEXT,
        source_domain TEXT,
        result_rank INTEGER,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );


    CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        impressions REAL DEFAULT 0,
        clicks REAL DEFAULT 0,
        orders REAL DEFAULT 0,
        revenue REAL DEFAULT 0,
        ad_spend REAL DEFAULT 0,
        returns REAL DEFAULT 0,
        cogs REAL DEFAULT 0,
        shipping_cost REAL DEFAULT 0,
        marketplace_fees REAL DEFAULT 0,
        taxes REAL DEFAULT 0,
        other_costs REAL DEFAULT 0,
        ctr REAL,
        conversion_rate REAL,
        cac_real REAL,
        roas_real REAL,
        return_rate REAL,
        profit_real REAL,
        profit_margin_real REAL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS weight_calibrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        observations INTEGER NOT NULL,
        old_weights_json TEXT NOT NULL,
        suggested_weights_json TEXT NOT NULL,
        applied_weights_json TEXT,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL UNIQUE,
        stock_on_hand REAL DEFAULT 0,
        stock_inbound REAL DEFAULT 0,
        unit_cost REAL DEFAULT 0,
        reorder_lead_days REAL DEFAULT 0,
        safety_stock_days REAL DEFAULT 7,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS portfolio_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        action TEXT NOT NULL,
        priority TEXT NOT NULL,
        confidence REAL,
        reason TEXT NOT NULL,
        metrics_json TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );


    CREATE TABLE IF NOT EXISTS cash_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        total_budget REAL NOT NULL,
        reserve_pct REAL NOT NULL,
        usable_budget REAL NOT NULL,
        plan_json TEXT NOT NULL,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS growth_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        horizon_days INTEGER NOT NULL,
        plan_json TEXT NOT NULL,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS scenario_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        scenario_name TEXT NOT NULL,
        params_json TEXT NOT NULL,
        result_json TEXT NOT NULL,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS automation_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        product_id INTEGER,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        dedupe_key TEXT,
        sent_email INTEGER DEFAULT 0,
        sent_telegram INTEGER DEFAULT 0,
        sent_webhook INTEGER DEFAULT 0,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS automation_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        run_type TEXT NOT NULL,
        events_created INTEGER DEFAULT 0,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS orchestrator_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_uid TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        product_id INTEGER,
        source_type TEXT,
        source_id INTEGER,
        task_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        priority TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente',
        requires_approval INTEGER DEFAULT 0,
        approved_at TEXT,
        rejected_at TEXT,
        executed_at TEXT,
        execution_result TEXT,
        expires_at TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS orchestrator_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        run_type TEXT NOT NULL,
        tasks_created INTEGER DEFAULT 0,
        tasks_executed INTEGER DEFAULT 0,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS decision_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        product_id INTEGER,
        decision_type TEXT NOT NULL,
        decision TEXT NOT NULL,
        actor TEXT NOT NULL,
        rationale TEXT,
        source_task_uid TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );


    CREATE TABLE IF NOT EXISTS action_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        task_uid TEXT NOT NULL,
        product_id INTEGER,
        action_type TEXT NOT NULL,
        draft_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'rascunho',
        approved_at TEXT,
        rejected_at TEXT,
        exported_at TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );


    CREATE TABLE IF NOT EXISTS outbound_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        channel TEXT NOT NULL,
        destination TEXT,
        status TEXT NOT NULL DEFAULT 'pendente',
        sent_at TEXT,
        result TEXT,
        FOREIGN KEY(draft_id) REFERENCES action_drafts(id)
    );


    CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        job_type TEXT NOT NULL,
        cadence TEXT NOT NULL,
        hour INTEGER,
        weekday INTEGER,
        enabled INTEGER DEFAULT 1,
        last_run TEXT,
        next_run TEXT,
        notes TEXT
    );


    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        product_id INTEGER,
        name TEXT NOT NULL,
        hypothesis TEXT,
        variant_a TEXT,
        variant_b TEXT,
        metric TEXT,
        status TEXT DEFAULT 'planejado',
        result TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)

    # V4 financial fields, safely added to old V3 database
    for col, decl in [
        ("marketplace_fixed", "REAL DEFAULT 0"),
        ("target_profit_margin_pct", "REAL DEFAULT 12"),
        ("contribution_before_ads", "REAL"),
        ("cac_max_break_even", "REAL"),
        ("cac_max_target", "REAL"),
        ("roas_min_break_even", "REAL"),
        ("roas_target", "REAL")
    ]:
        _ensure_column(con, "snapshots", col, decl)

    con.commit()
    con.close()

def upsert_product(name, keyword, category="", operation_model="A",
                   seasonality_type="Perene", peak_months="", status="radar"):
    con = connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("""
        INSERT INTO products(name, keyword, category, operation_model, seasonality_type, peak_months, status, created_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
          keyword=excluded.keyword,
          category=excluded.category,
          operation_model=excluded.operation_model,
          seasonality_type=excluded.seasonality_type,
          peak_months=excluded.peak_months,
          status=excluded.status
    """, (name, keyword, category, operation_model, seasonality_type, peak_months, status, now))
    con.commit()
    row = con.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone()
    con.close()
    return int(row["id"])

def add_snapshot(product_id, snapshot):
    con = connect()
    cols = ["product_id","captured_at"] + list(snapshot.keys())
    vals = [product_id, datetime.now().isoformat(timespec="seconds")] + list(snapshot.values())
    q = f"INSERT INTO snapshots({','.join(cols)}) VALUES({','.join(['?']*len(vals))})"
    con.execute(q, vals)
    con.commit()
    con.close()

def add_alert(product_id, alert_type, severity, message):
    con = connect()
    con.execute("""
        INSERT INTO alerts(product_id,created_at,alert_type,severity,message)
        VALUES(?,?,?,?,?)
    """, (product_id, datetime.now().isoformat(timespec="seconds"), alert_type, severity, message))
    con.commit()
    con.close()

def add_supplier(product_id, supplier_name, supplier_url="", contact="", unit_cost=0,
                 moq=1, shipping_est=0, lead_time_days=0, ready_to_ship=1,
                 prep_type="pronto", notes=""):
    con = connect()
    con.execute("""
      INSERT INTO suppliers(product_id,supplier_name,supplier_url,contact,unit_cost,moq,
      shipping_est,lead_time_days,ready_to_ship,prep_type,notes,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (product_id,supplier_name,supplier_url,contact,unit_cost,moq,shipping_est,
          lead_time_days,ready_to_ship,prep_type,notes,datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()

def suppliers(product_id=None):
    con = connect()
    if product_id:
        rows = con.execute("""
          SELECT s.*, p.name product_name FROM suppliers s
          JOIN products p ON p.id=s.product_id
          WHERE product_id=? ORDER BY unit_cost ASC
        """,(product_id,)).fetchall()
    else:
        rows = con.execute("""
          SELECT s.*, p.name product_name FROM suppliers s
          JOIN products p ON p.id=s.product_id
          ORDER BY p.name, unit_cost ASC
        """).fetchall()
    con.close()
    return [dict(r) for r in rows]

def clear_public_search(product_id):
    con = connect()
    con.execute("DELETE FROM public_search_results WHERE product_id=?", (product_id,))
    con.commit()
    con.close()

def add_public_search_result(product_id, query, title, url, description, source_domain, result_rank):
    con = connect()
    con.execute("""
      INSERT INTO public_search_results(product_id,captured_at,query,title,url,description,source_domain,result_rank)
      VALUES(?,?,?,?,?,?,?,?)
    """,(product_id,datetime.now().isoformat(timespec="seconds"),query,title,url,description,source_domain,result_rank))
    con.commit()
    con.close()

def public_search_results(product_id=None):
    con=connect()
    if product_id:
        rows=con.execute("""
          SELECT r.*,p.name product_name FROM public_search_results r
          JOIN products p ON p.id=r.product_id WHERE r.product_id=?
          ORDER BY r.result_rank
        """,(product_id,)).fetchall()
    else:
        rows=con.execute("""
          SELECT r.*,p.name product_name FROM public_search_results r
          JOIN products p ON p.id=r.product_id
          ORDER BY r.captured_at DESC,r.result_rank
        """).fetchall()
    con.close()
    return [dict(r) for r in rows]

def products():
    con = connect()
    rows = con.execute("SELECT * FROM products ORDER BY name").fetchall()
    con.close()
    return [dict(r) for r in rows]

def history(product_id, limit=365):
    con = connect()
    rows = con.execute("""
        SELECT * FROM snapshots WHERE product_id=?
        ORDER BY captured_at DESC LIMIT ?
    """, (product_id, limit)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def latest_snapshots():
    con = connect()
    rows = con.execute("""
      SELECT s.*, p.name, p.keyword, p.category, p.operation_model, p.seasonality_type, p.peak_months
      FROM snapshots s
      JOIN products p ON p.id=s.product_id
      JOIN (
        SELECT product_id, MAX(captured_at) mx
        FROM snapshots GROUP BY product_id
      ) x ON x.product_id=s.product_id AND x.mx=s.captured_at
      ORDER BY s.score DESC
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

def alerts(unread_only=False):
    con = connect()
    q = """
      SELECT a.*, p.name FROM alerts a
      JOIN products p ON p.id=a.product_id
    """
    if unread_only:
        q += " WHERE a.is_read=0"
    q += " ORDER BY a.created_at DESC"
    rows = con.execute(q).fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_performance(product_id, date, impressions=0, clicks=0, orders=0, revenue=0,
                    ad_spend=0, returns=0, cogs=0, shipping_cost=0,
                    marketplace_fees=0, taxes=0, other_costs=0):
    con = connect()
    impressions=float(impressions or 0); clicks=float(clicks or 0); orders=float(orders or 0)
    revenue=float(revenue or 0); ad_spend=float(ad_spend or 0); returns=float(returns or 0)
    cogs=float(cogs or 0); shipping_cost=float(shipping_cost or 0)
    marketplace_fees=float(marketplace_fees or 0); taxes=float(taxes or 0); other_costs=float(other_costs or 0)

    ctr=(clicks/impressions*100) if impressions else 0
    conversion=(orders/clicks*100) if clicks else 0
    cac=(ad_spend/orders) if orders else None
    roas=(revenue/ad_spend) if ad_spend else None
    return_rate=(returns/orders*100) if orders else 0
    profit=revenue-ad_spend-cogs-shipping_cost-marketplace_fees-taxes-other_costs
    margin=(profit/revenue*100) if revenue else 0

    con.execute("""
      INSERT INTO performance(product_id,date,impressions,clicks,orders,revenue,ad_spend,returns,
      cogs,shipping_cost,marketplace_fees,taxes,other_costs,ctr,conversion_rate,cac_real,
      roas_real,return_rate,profit_real,profit_margin_real,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(product_id,date,impressions,clicks,orders,revenue,ad_spend,returns,cogs,shipping_cost,
         marketplace_fees,taxes,other_costs,ctr,conversion,cac,roas,return_rate,profit,margin,
         datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()

def performance(product_id=None, limit=10000):
    con=connect()
    if product_id:
        rows=con.execute("""
          SELECT pf.*,p.name product_name FROM performance pf
          JOIN products p ON p.id=pf.product_id
          WHERE pf.product_id=? ORDER BY date DESC LIMIT ?
        """,(product_id,limit)).fetchall()
    else:
        rows=con.execute("""
          SELECT pf.*,p.name product_name FROM performance pf
          JOIN products p ON p.id=pf.product_id
          ORDER BY date DESC LIMIT ?
        """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def save_calibration(observations, old_weights, suggested_weights, applied_weights=None, notes=""):
    import json
    con=connect()
    con.execute("""
      INSERT INTO weight_calibrations(created_at,observations,old_weights_json,
      suggested_weights_json,applied_weights_json,notes)
      VALUES(?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),observations,
         json.dumps(old_weights,ensure_ascii=False),
         json.dumps(suggested_weights,ensure_ascii=False),
         json.dumps(applied_weights,ensure_ascii=False) if applied_weights else None,
         notes))
    con.commit()
    con.close()

def calibrations(limit=50):
    con=connect()
    rows=con.execute("SELECT * FROM weight_calibrations ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def upsert_inventory(product_id, stock_on_hand=0, stock_inbound=0, unit_cost=0,
                     reorder_lead_days=0, safety_stock_days=7):
    con=connect()
    con.execute("""
      INSERT INTO inventory(product_id,stock_on_hand,stock_inbound,unit_cost,
      reorder_lead_days,safety_stock_days,updated_at)
      VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(product_id) DO UPDATE SET
        stock_on_hand=excluded.stock_on_hand,
        stock_inbound=excluded.stock_inbound,
        unit_cost=excluded.unit_cost,
        reorder_lead_days=excluded.reorder_lead_days,
        safety_stock_days=excluded.safety_stock_days,
        updated_at=excluded.updated_at
    """,(product_id,stock_on_hand,stock_inbound,unit_cost,reorder_lead_days,
         safety_stock_days,datetime.now().isoformat(timespec="seconds")))
    con.commit(); con.close()

def inventory(product_id=None):
    con=connect()
    if product_id:
        rows=con.execute("""
          SELECT i.*,p.name product_name FROM inventory i
          JOIN products p ON p.id=i.product_id WHERE i.product_id=?
        """,(product_id,)).fetchall()
    else:
        rows=con.execute("""
          SELECT i.*,p.name product_name FROM inventory i
          JOIN products p ON p.id=i.product_id ORDER BY p.name
        """).fetchall()
    con.close()
    return [dict(r) for r in rows]

def save_portfolio_action(product_id, action, priority, confidence, reason, metrics_json=""):
    con=connect()
    con.execute("""
      INSERT INTO portfolio_actions(product_id,created_at,action,priority,confidence,reason,metrics_json)
      VALUES(?,?,?,?,?,?,?)
    """,(product_id,datetime.now().isoformat(timespec="seconds"),action,priority,
         confidence,reason,metrics_json))
    con.commit(); con.close()

def portfolio_actions(limit=500):
    con=connect()
    rows=con.execute("""
      SELECT a.*,p.name FROM portfolio_actions a
      JOIN products p ON p.id=a.product_id
      ORDER BY a.created_at DESC LIMIT ?
    """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_cash_plan(total_budget, reserve_pct, usable_budget, plan_json, notes=""):
    con=connect()
    con.execute("""
      INSERT INTO cash_plans(created_at,total_budget,reserve_pct,usable_budget,plan_json,notes)
      VALUES(?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),total_budget,reserve_pct,
         usable_budget,plan_json,notes))
    con.commit(); con.close()

def cash_plans(limit=50):
    con=connect()
    rows=con.execute("SELECT * FROM cash_plans ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_growth_plan(horizon_days, plan_json, notes=""):
    con=connect()
    con.execute("""
      INSERT INTO growth_plans(created_at,horizon_days,plan_json,notes)
      VALUES(?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),horizon_days,plan_json,notes))
    con.commit(); con.close()

def growth_plans(limit=50):
    con=connect()
    rows=con.execute("SELECT * FROM growth_plans ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_scenario_run(scenario_name, params_json, result_json, notes=""):
    con=connect()
    con.execute("""
      INSERT INTO scenario_runs(created_at,scenario_name,params_json,result_json,notes)
      VALUES(?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),scenario_name,params_json,result_json,notes))
    con.commit(); con.close()

def scenario_runs(limit=100):
    con=connect()
    rows=con.execute("SELECT * FROM scenario_runs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def save_automation_event(product_id, event_type, severity, title, message, dedupe_key=""):
    con=connect()
    con.execute("""
      INSERT INTO automation_events(created_at,product_id,event_type,severity,title,message,dedupe_key)
      VALUES(?,?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),product_id,event_type,severity,title,message,dedupe_key))
    con.commit(); con.close()

def automation_events(limit=500):
    con=connect()
    rows=con.execute("""
      SELECT e.*,p.name FROM automation_events e
      LEFT JOIN products p ON p.id=e.product_id
      ORDER BY e.created_at DESC LIMIT ?
    """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def last_event_by_key(dedupe_key):
    con=connect()
    row=con.execute("""
      SELECT * FROM automation_events
      WHERE dedupe_key=? ORDER BY created_at DESC LIMIT 1
    """,(dedupe_key,)).fetchone()
    con.close()
    return dict(row) if row else None

def save_automation_run(run_type, events_created=0, notes=""):
    con=connect()
    con.execute("""
      INSERT INTO automation_runs(created_at,run_type,events_created,notes)
      VALUES(?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),run_type,events_created,notes))
    con.commit(); con.close()

def automation_runs(limit=100):
    con=connect()
    rows=con.execute("SELECT * FROM automation_runs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_orchestrator_task(task_uid, product_id, source_type, source_id, task_type,
                             title, description, priority, requires_approval=0, expires_at=None):
    con=connect()
    now=datetime.now().isoformat(timespec="seconds")
    con.execute("""
      INSERT OR IGNORE INTO orchestrator_tasks(
        task_uid,created_at,updated_at,product_id,source_type,source_id,task_type,title,
        description,priority,status,requires_approval,expires_at
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(task_uid,now,now,product_id,source_type,source_id,task_type,title,description,
         priority,"pendente",requires_approval,expires_at))
    con.commit(); con.close()

def orchestrator_tasks(status=None, limit=500):
    con=connect()
    q="""
      SELECT t.*,p.name FROM orchestrator_tasks t
      LEFT JOIN products p ON p.id=t.product_id
    """
    params=[]
    if status:
        q+=" WHERE t.status=?"
        params.append(status)
    q+=" ORDER BY CASE t.priority WHEN 'critica' THEN 1 WHEN 'alta' THEN 2 WHEN 'media' THEN 3 ELSE 4 END, t.created_at DESC LIMIT ?"
    params.append(limit)
    rows=con.execute(q,tuple(params)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def update_task_status(task_uid, status, result=None):
    con=connect()
    now=datetime.now().isoformat(timespec="seconds")
    fields=["status=?","updated_at=?"]
    vals=[status,now]
    if status=="aprovada":
        fields.append("approved_at=?"); vals.append(now)
    elif status=="rejeitada":
        fields.append("rejected_at=?"); vals.append(now)
    elif status=="executada":
        fields.append("executed_at=?"); vals.append(now)
    if result is not None:
        fields.append("execution_result=?"); vals.append(result)
    vals.append(task_uid)
    con.execute(f"UPDATE orchestrator_tasks SET {','.join(fields)} WHERE task_uid=?",tuple(vals))
    con.commit(); con.close()

def save_orchestrator_run(run_type, tasks_created=0, tasks_executed=0, notes=""):
    con=connect()
    con.execute("""
      INSERT INTO orchestrator_runs(created_at,run_type,tasks_created,tasks_executed,notes)
      VALUES(?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),run_type,tasks_created,tasks_executed,notes))
    con.commit(); con.close()

def orchestrator_runs(limit=100):
    con=connect()
    rows=con.execute("SELECT * FROM orchestrator_runs ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def save_decision(product_id, decision_type, decision, actor, rationale="", source_task_uid=None):
    con=connect()
    con.execute("""
      INSERT INTO decision_log(created_at,product_id,decision_type,decision,actor,rationale,source_task_uid)
      VALUES(?,?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),product_id,decision_type,decision,actor,rationale,source_task_uid))
    con.commit(); con.close()

def decision_log(limit=500):
    con=connect()
    rows=con.execute("""
      SELECT d.*,p.name FROM decision_log d
      LEFT JOIN products p ON p.id=d.product_id
      ORDER BY d.created_at DESC LIMIT ?
    """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_action_draft(task_uid, product_id, action_type, draft_type, title, content):
    con=connect()
    con.execute("""
      INSERT INTO action_drafts(created_at,task_uid,product_id,action_type,draft_type,title,content,status)
      VALUES(?,?,?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),task_uid,product_id,action_type,draft_type,title,content,"rascunho"))
    con.commit(); con.close()

def action_drafts(status=None, limit=500):
    con=connect()
    q="""
      SELECT d.*,p.name FROM action_drafts d
      LEFT JOIN products p ON p.id=d.product_id
    """
    params=[]
    if status:
        q+=" WHERE d.status=?"
        params.append(status)
    q+=" ORDER BY d.created_at DESC LIMIT ?"
    params.append(limit)
    rows=con.execute(q,tuple(params)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def update_action_draft_status(draft_id, status):
    con=connect()
    now=datetime.now().isoformat(timespec="seconds")
    fields=["status=?"]
    vals=[status]
    if status=="aprovado":
        fields.append("approved_at=?"); vals.append(now)
    elif status=="rejeitado":
        fields.append("rejected_at=?"); vals.append(now)
    elif status=="exportado":
        fields.append("exported_at=?"); vals.append(now)
    vals.append(draft_id)
    con.execute(f"UPDATE action_drafts SET {','.join(fields)} WHERE id=?",tuple(vals))
    con.commit(); con.close()


def create_outbound_action(draft_id, channel, destination=""):
    con=connect()
    con.execute("""
      INSERT INTO outbound_actions(draft_id,created_at,channel,destination,status)
      VALUES(?,?,?,?,?)
    """,(draft_id,datetime.now().isoformat(timespec="seconds"),channel,destination,"pendente"))
    con.commit(); con.close()

def outbound_actions(limit=500):
    con=connect()
    rows=con.execute("""
      SELECT o.*,d.title,d.content,d.action_type,p.name
      FROM outbound_actions o
      JOIN action_drafts d ON d.id=o.draft_id
      LEFT JOIN products p ON p.id=d.product_id
      ORDER BY o.created_at DESC LIMIT ?
    """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def mark_outbound_sent(action_id, result=""):
    con=connect()
    con.execute("""
      UPDATE outbound_actions SET status='enviado',sent_at=?,result=? WHERE id=?
    """,(datetime.now().isoformat(timespec="seconds"),result,action_id))
    con.commit(); con.close()


def upsert_scheduled_job(name,job_type,cadence,hour=None,weekday=None,enabled=1,notes=""):
    con=connect()
    con.execute("""
      INSERT INTO scheduled_jobs(name,job_type,cadence,hour,weekday,enabled,notes)
      VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(name) DO UPDATE SET job_type=excluded.job_type,cadence=excluded.cadence,
      hour=excluded.hour,weekday=excluded.weekday,enabled=excluded.enabled,notes=excluded.notes
    """,(name,job_type,cadence,hour,weekday,enabled,notes))
    con.commit(); con.close()

def scheduled_jobs():
    con=connect(); rows=con.execute("SELECT * FROM scheduled_jobs ORDER BY name").fetchall()
    con.close(); return [dict(r) for r in rows]

def mark_job_run(job_id,next_run=None):
    con=connect()
    con.execute("UPDATE scheduled_jobs SET last_run=?,next_run=? WHERE id=?",
                (datetime.now().isoformat(timespec='seconds'),next_run,job_id))
    con.commit(); con.close()


def create_experiment(product_id,name,hypothesis,variant_a,variant_b,metric):
    con=connect()
    con.execute("""
      INSERT INTO experiments(created_at,product_id,name,hypothesis,variant_a,variant_b,metric,status)
      VALUES(?,?,?,?,?,?,?,?)
    """,(datetime.now().isoformat(timespec="seconds"),product_id,name,hypothesis,variant_a,variant_b,metric,"planejado"))
    con.commit(); con.close()

def experiments(limit=200):
    con=connect()
    rows=con.execute("""
      SELECT e.*,p.name product_name FROM experiments e
      LEFT JOIN products p ON p.id=e.product_id ORDER BY e.created_at DESC LIMIT ?
    """,(limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]
