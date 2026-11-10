from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from datetime import datetime, timedelta, timezone
from functools import wraps
import sqlite3, os, json

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "interzone.db")
app = Flask(__name__)
app.secret_key = os.environ.get("INTERZONE_SECRET", "local-prototype-change-me")

DEMO_USERS = [
    ("alice", "Alice Morgan", "Technical", "Junior Executive", "employee"),
    ("ben", "Ben Carter", "Technical", "Manager", "manager"),
    ("diana", "Diana Lee", "Design", "Manager", "manager"),
    ("sara", "Sara Patel", "HR", "Department Head", "manager"),
    ("mike", "Mike Chen", "Sales", "Team Leader", "employee"),
    ("intern", "Noah Reed", "Interns", "Intern", "employee"),
    ("ceo", "Jordan Blake", "Executive", "CEO", "executive"),
    ("cto", "Taylor Kim", "Executive", "CTO", "executive"),
    ("cfo", "Morgan Shah", "Executive", "CFO", "executive"),
    ("owner", "Alex Rivera", "Executive", "Owner", "executive"),
]
DEPARTMENTS = ["HR", "Technical", "Design", "Sales", "Interns", "Executive"]
RESOURCES = [
    ("design_brand_kit", "Brand Design Files", "Design", "internal", "read"),
    ("design_product_mockups", "Unreleased Product Mockups", "Design", "confidential", "read"),
    ("hr_employee_records", "Employee Records", "HR", "highly confidential", "read"),
    ("finance_forecast", "Quarterly Financial Forecast", "Finance", "highly confidential", "read"),
    ("tech_source_repo", "Product Source Repository", "Technical", "confidential", "read"),
    ("tech_architecture", "System Architecture Documents", "Technical", "confidential", "read"),
    ("sales_customer_list", "Customer Account List", "Sales", "confidential", "read"),
    ("intern_public_docs", "Intern Onboarding Guide", "Interns", "internal", "read"),
]

def now():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.isoformat()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      username TEXT PRIMARY KEY, full_name TEXT NOT NULL, department TEXT NOT NULL,
      title TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS resources (
      resource_id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
      sensitivity TEXT NOT NULL, allowed_action TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS access_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT NOT NULL,
      resource_id TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
      duration_minutes INTEGER NOT NULL, status TEXT NOT NULL,
      manager_approved_by TEXT, owner_approved_by TEXT,
      created_at TEXT NOT NULL, decided_at TEXT
    );
    CREATE TABLE IF NOT EXISTS grants (
      id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL,
      username TEXT NOT NULL, resource_id TEXT NOT NULL, action TEXT NOT NULL,
      starts_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT,
      FOREIGN KEY(request_id) REFERENCES access_requests(id)
    );
    CREATE TABLE IF NOT EXISTS executive_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT NOT NULL,
      resource_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
      first_approver TEXT, second_approver TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
      event_type TEXT NOT NULL, resource_id TEXT, details TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """)
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.executemany("INSERT INTO users VALUES (?,?,?,?,?,1)", DEMO_USERS)
    if con.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
        con.executemany("INSERT INTO resources VALUES (?,?,?,?,?)", RESOURCES)
    con.commit()
    con.close()

def current_user():
    username = session.get("username", "alice")
    con = db()
    row = con.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    con.close()
    return dict(row) if row else None

def audit(actor, event_type, resource_id=None, details=""):
    con = db()
    con.execute("INSERT INTO audit_events(actor,event_type,resource_id,details,created_at) VALUES (?,?,?,?,?)",
                (actor, event_type, resource_id, details, iso(now())))
    con.commit()
    con.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Sign in required"}), 401
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {"me": current_user(), "demo_users": DEMO_USERS}

@app.route("/")
def index():
    if not session.get("username"):
        session["username"] = "alice"
    return render_template("index.html")

@app.post("/switch-user")
def switch_user():
    username = request.form.get("username", "")
    if username not in [u[0] for u in DEMO_USERS]:
        abort(400)
    session["username"] = username
    audit(username, "DEMO_IDENTITY_SWITCH", None, "Prototype demo identity selected")
    return redirect(url_for("index"))

@app.get("/api/dashboard")
@login_required
def dashboard():
    user = current_user()
    con = db()
    resources = [dict(r) for r in con.execute("SELECT * FROM resources ORDER BY department,name")]
    requests = [dict(r) for r in con.execute("SELECT * FROM access_requests ORDER BY id DESC LIMIT 12")]
    grants = [dict(r) for r in con.execute("SELECT * FROM grants ORDER BY id DESC LIMIT 12")]
    events = [dict(r) for r in con.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 15")]
    pending_exec = [dict(r) for r in con.execute("SELECT * FROM executive_requests WHERE status IN ('pending_second_approval','pending_first_approval') ORDER BY id DESC")]
    counts = {
        "requests": con.execute("SELECT COUNT(*) FROM access_requests WHERE status IN ('pending_manager','pending_owner')").fetchone()[0],
        "active_grants": con.execute("SELECT COUNT(*) FROM grants WHERE revoked_at IS NULL AND expires_at > ?", (iso(now()),)).fetchone()[0],
        "audit_events": con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        "pending_exec": len(pending_exec)
    }
    con.close()
    # Non-executives see only their own requests/grants and department resources.
    if user["role"] == "employee":
        requests = [r for r in requests if r["requester"] == user["username"]]
        grants = [g for g in grants if g["username"] == user["username"]]
        events = [e for e in events if e["actor"] == user["username"]]
    elif user["role"] == "manager":
        # Managers see workflow items; the approval endpoints enforce which department
        # they are authorized to approve for.
        grants = [g for g in grants if g["username"] == user["username"]]
        events = [e for e in events if e["actor"] == user["username"]]
    return jsonify({"user": user, "resources": resources, "requests": requests,
                    "grants": grants, "events": events, "counts": counts,
                    "executive_requests": pending_exec if user["role"] == "executive" else []})

@app.post("/api/request")
@login_required
def create_request():
    user = current_user()
    data = request.get_json(force=True)
    resource_id = data.get("resource_id")
    action = data.get("action", "read")
    reason = (data.get("reason") or "").strip()
    duration = int(data.get("duration_minutes", 15))
    if duration not in (15, 30, 60) or not reason or len(reason) < 8:
        return jsonify({"error": "Choose 15, 30 or 60 minutes and provide a meaningful reason (at least 8 characters)."}), 400
    con = db()
    resource = con.execute("SELECT * FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if not resource:
        con.close()
        return jsonify({"error": "Unknown resource"}), 404
    if user["role"] == "executive":
        con.close()
        return jsonify({"error": "Executives use the restricted executive-access workflow."}), 403
    if user["department"] == resource["department"]:
        con.close()
        return jsonify({"error": "You already belong to this resource's department in this prototype."}), 400
    status = "pending_manager"
    con.execute("""INSERT INTO access_requests
      (requester,resource_id,action,reason,duration_minutes,status,created_at)
      VALUES (?,?,?,?,?,?,?)""",
      (user["username"], resource_id, action, reason, duration, status, iso(now())))
    rid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    audit(user["username"], "ACCESS_REQUEST_CREATED", resource_id, f"Request #{rid}; {duration} minutes; {reason}")
    return jsonify({"ok": True, "request_id": rid})

@app.post("/api/requests/<int:rid>/approve-manager")
@login_required
def approve_manager(rid):
    user = current_user()
    if user["role"] not in ("manager", "executive"):
        return jsonify({"error": "Only an authorized manager can perform this step."}), 403
    con = db()
    row = con.execute("SELECT ar.*,u.department AS requester_department FROM access_requests ar JOIN users u ON u.username=ar.requester WHERE ar.id=?", (rid,)).fetchone()
    if not row or row["status"] != "pending_manager":
        con.close()
        return jsonify({"error": "Request not found or not awaiting manager review."}), 404
    if user["department"] != row["requester_department"] and user["role"] != "executive":
        con.close()
        return jsonify({"error": "Only the requester's department manager can approve this step."}), 403
    if user["username"] == row["requester"]:
        con.close()
        return jsonify({"error": "Self-approval is prohibited."}), 403
    con.execute("UPDATE access_requests SET status='pending_owner', manager_approved_by=?, decided_at=? WHERE id=?",
                (user["username"], iso(now()), rid))
    con.commit(); con.close()
    audit(user["username"], "REQUEST_MANAGER_APPROVED", row["resource_id"], f"Request #{rid} forwarded to resource owner")
    return jsonify({"ok": True})

@app.post("/api/requests/<int:rid>/approve-owner")
@login_required
def approve_owner(rid):
    user = current_user()
    if user["role"] not in ("manager", "executive"):
        return jsonify({"error": "Only an authorized manager can perform this step."}), 403
    con = db()
    row = con.execute("SELECT ar.*,r.department AS owner_department FROM access_requests ar JOIN resources r ON r.resource_id=ar.resource_id WHERE ar.id=?", (rid,)).fetchone()
    if not row or row["status"] != "pending_owner":
        con.close()
        return jsonify({"error": "Request not found or not awaiting owner approval."}), 404
    if user["department"] != row["owner_department"] and user["role"] != "executive":
        con.close()
        return jsonify({"error": "Only the resource-owning department manager can approve this step."}), 403
    if user["username"] == row["requester"]:
        con.close()
        return jsonify({"error": "Self-approval is prohibited."}), 403
    start = now()
    expiry = start + timedelta(minutes=row["duration_minutes"])
    con.execute("UPDATE access_requests SET status='approved', owner_approved_by=?, decided_at=? WHERE id=?",
                (user["username"], iso(start), rid))
    con.execute("""INSERT INTO grants(request_id,username,resource_id,action,starts_at,expires_at)
                   VALUES (?,?,?,?,?,?)""",
                (rid, row["requester"], row["resource_id"], row["action"], iso(start), iso(expiry)))
    con.commit(); con.close()
    audit(user["username"], "TEMPORARY_ACCESS_GRANTED", row["resource_id"], f"Request #{rid}; expires {iso(expiry)}")
    return jsonify({"ok": True, "expires_at": iso(expiry)})

@app.post("/api/requests/<int:rid>/reject")
@login_required
def reject_request(rid):
    user = current_user()
    if user["role"] not in ("manager", "executive"):
        return jsonify({"error": "Manager access required"}), 403
    con = db()
    row = con.execute("SELECT * FROM access_requests WHERE id=?", (rid,)).fetchone()
    if not row:
        con.close(); return jsonify({"error": "Not found"}), 404
    con.execute("UPDATE access_requests SET status='rejected', decided_at=? WHERE id=?", (iso(now()), rid))
    con.commit(); con.close()
    audit(user["username"], "ACCESS_REQUEST_REJECTED", row["resource_id"], f"Request #{rid}")
    return jsonify({"ok": True})

@app.post("/api/grants/<int:gid>/revoke")
@login_required
def revoke_grant(gid):
    user = current_user()
    if user["role"] not in ("manager", "executive"):
        return jsonify({"error": "Manager access required"}), 403
    con = db()
    row = con.execute("SELECT * FROM grants WHERE id=?", (gid,)).fetchone()
    if not row:
        con.close(); return jsonify({"error": "Not found"}), 404
    con.execute("UPDATE grants SET revoked_at=? WHERE id=? AND revoked_at IS NULL", (iso(now()), gid))
    con.commit(); con.close()
    audit(user["username"], "ACCESS_REVOKED", row["resource_id"], f"Grant #{gid} for {row['username']}")
    return jsonify({"ok": True})

@app.post("/api/executive/request")
@login_required
def executive_request():
    user = current_user()
    if user["role"] != "executive":
        return jsonify({"error": "Executive role required"}), 403
    data = request.get_json(force=True)
    resource_id = data.get("resource_id")
    reason = (data.get("reason") or "").strip()
    con = db()
    resource = con.execute("SELECT * FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if not resource or resource["sensitivity"] not in ("confidential", "highly confidential"):
        con.close(); return jsonify({"error": "This workflow is for restricted resources."}), 400
    if len(reason) < 8:
        con.close(); return jsonify({"error": "Please provide a meaningful business justification."}), 400
    cur = con.execute("INSERT INTO executive_requests(requester,resource_id,reason,status,created_at) VALUES (?,?,?,'pending_second_approval',?)",
                      (user["username"], resource_id, reason, iso(now())))
    eid = cur.lastrowid
    con.commit(); con.close()
    audit(user["username"], "EXECUTIVE_SENSITIVE_ACCESS_REQUESTED", resource_id, f"Executive request #{eid}: {reason}")
    return jsonify({"ok": True, "request_id": eid})

@app.post("/api/executive/<int:eid>/approve")
@login_required
def approve_executive(eid):
    user = current_user()
    if user["role"] != "executive":
        return jsonify({"error": "Only an executive can approve this request."}), 403
    con = db()
    row = con.execute("SELECT * FROM executive_requests WHERE id=?", (eid,)).fetchone()
    if not row or row["status"] != "pending_second_approval":
        con.close(); return jsonify({"error": "Request not pending"}), 404
    if row["requester"] == user["username"]:
        con.close(); return jsonify({"error": "A requester cannot approve their own request."}), 403
    con.execute("UPDATE executive_requests SET status='approved', second_approver=? WHERE id=?", (user["username"], eid))
    con.commit(); con.close()
    audit(user["username"], "EXECUTIVE_SECOND_APPROVAL_GRANTED", row["resource_id"], f"Executive request #{eid} by {row['requester']}")
    return jsonify({"ok": True})

@app.get("/api/resource/<resource_id>")
@login_required
def protected_resource(resource_id):
    """The proof-of-concept enforcement point: authorization is checked on EVERY request."""
    user = current_user()
    con = db()
    resource = con.execute("SELECT * FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if not resource:
        con.close(); return jsonify({"error": "Resource not found"}), 404

    allowed = False
    explanation = ""
    if user["role"] == "executive":
        # Oversight does not equal automatic access to sensitive content.
        if resource["sensitivity"] in ("internal",):
            allowed = True
            explanation = "Executive oversight access"
        else:
            er = con.execute("""SELECT * FROM executive_requests
                WHERE requester=? AND resource_id=? AND status='approved'
                ORDER BY id DESC LIMIT 1""", (user["username"], resource_id)).fetchone()
            allowed = er is not None
            explanation = "Second executive approval verified" if allowed else "Restricted executive access requires a second executive approval"
    elif user["department"] == resource["department"]:
        allowed = True
        explanation = "Department membership"
    else:
        grant = con.execute("""SELECT * FROM grants WHERE username=? AND resource_id=?
            AND action='read' AND revoked_at IS NULL AND starts_at<=? AND expires_at>?
            ORDER BY id DESC LIMIT 1""",
            (user["username"], resource_id, iso(now()), iso(now()))).fetchone()
        allowed = grant is not None
        explanation = "Active, scoped temporary grant" if allowed else "No active grant for this resource"
    con.close()

    if not allowed:
        audit(user["username"], "ACCESS_DENIED", resource_id, explanation)
        return jsonify({"allowed": False, "error": "Access denied", "reason": explanation}), 403

    audit(user["username"], "RESOURCE_VIEWED", resource_id, explanation)
    return jsonify({"allowed": True, "resource": resource["name"],
                    "department": resource["department"], "sensitivity": resource["sensitivity"],
                    "message": "Prototype protected content: access was checked by the policy enforcement point."})

@app.post("/api/employee/deactivate")
@login_required
def deactivate_employee():
    user = current_user()
    if user["role"] != "manager" and user["title"] not in ("Owner", "CEO"):
        return jsonify({"error": "Only an authorized HR/administrative role can deactivate an employee in this prototype."}), 403
    data = request.get_json(force=True)
    target = data.get("username")
    if not target or target == user["username"]:
        return jsonify({"error": "Choose another employee."}), 400
    con = db()
    row = con.execute("SELECT * FROM users WHERE username=?", (target,)).fetchone()
    if not row:
        con.close(); return jsonify({"error": "Employee not found"}), 404
    con.execute("UPDATE users SET active=0 WHERE username=?", (target,))
    con.execute("UPDATE grants SET revoked_at=? WHERE username=? AND revoked_at IS NULL", (iso(now()), target))
    con.commit(); con.close()
    audit(user["username"], "EMPLOYEE_DEACTIVATED", None, f"{target}; active grants revoked")
    return jsonify({"ok": True})

@app.get("/health")
def health():
    return jsonify({"status": "ok", "project": "InterZone Prototype v0.1"})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
