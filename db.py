# ============================================================================
# db.py — Database Layer (SQLite)
# ============================================================================
# YEH FILE KYA KARTI HAI?
# -----------------------
# SQLite ek "file-based" database hai — koi server nahi chahiye.
# Ye file ek "brandguard.db" file banayegi jismein 4 tables hongi:
#   1. documents   → knowledge base mein upload ki gayi files ka record
#   2. submissions → creators ne jo drafts submit kiye unka record
#   3. evaluations → AI ne jo scores/feedback diye unka record  
#   4. reviews     → human reviewer ne approve/reject kiya uska record
#
# SQLITE KYA HAI?
# ---------------
# SQLite ek lightweight database hai jo ek single file mein data store karta hai.
# Koi server install nahi karna padta. Python mein built-in aata hai (import sqlite3).
# Perfect for hackathons aur small-to-medium apps.
#
# SQL KYA HAI?
# ------------
# SQL = Structured Query Language — database se baat karne ki language.
#   CREATE TABLE → naya table banao
#   INSERT INTO  → naya record daalo
#   SELECT       → data nikalo
#   UPDATE       → data update karo
# ============================================================================

import sqlite3          # Python ki built-in library — SQLite se baat karne ke liye
import json             # Python objects ko JSON string mein convert karne ke liye
import os               # File paths handle karne ke liye
from datetime import datetime  # Current date/time nikalne ke liye
import bcrypt           # Password hashing ke liye (Improvement 1)

# Database file ka path — project root mein banega
DB_PATH = os.path.join(os.path.dirname(__file__), "brandguard.db")


def get_connection():
    """
    Database se connection banao.
    
    CONNECTION KYA HAI?
    Jaise phone call karne ke liye pehle dial karna padta hai,
    waise hi database se baat karne ke liye pehle connection banana padta hai.
    
    row_factory = sqlite3.Row → results ko dictionary jaisi access kar sakte ho
    (row["name"] instead of row[0])
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Results ko dict-like banao for easy access
    conn.execute("PRAGMA foreign_keys = ON")  # Foreign key constraints enable karo
    return conn


def init_db():
    """
    Database ke saare tables banao (agar pehle se nahi hain).
    
    IF NOT EXISTS → agar table already hai toh dobara mat banao (error nahi aayega).
    
    SCHEMA KYA HAI?
    Schema = table ka structure (kaunse columns hain, kis type ke hain).
    Jaise ek form ka template — kya kya fill karna hai.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # ─────────────────────────────────────────────────────────
    # TABLE 1: documents — Knowledge base documents ka record
    # ─────────────────────────────────────────────────────────
    # Ye table track karti hai ki admin ne kaunse documents upload kiye
    # (brand guidelines, product info, legal rules, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            doc_type TEXT NOT NULL DEFAULT 'guideline',
            content_preview TEXT,
            chunk_count INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            uploaded_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    # PRIMARY KEY AUTOINCREMENT → har row ko unique id milega (1, 2, 3, ...)
    # TEXT, INTEGER → data types (text = string, integer = number)
    # NOT NULL → ye field khali nahi chhod sakte
    # DEFAULT → agar value nahi di toh ye use hogi
    
    # ─────────────────────────────────────────────────────────
    # TABLE 2: submissions — Creator ke drafts ka record
    # ─────────────────────────────────────────────────────────
    # Jab creator apna post submit karta hai review ke liye,
    # uska sara data yahan save hota hai.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_name TEXT NOT NULL DEFAULT 'Anonymous',
            text_content TEXT,
            image_path TEXT,
            campaign_objective TEXT NOT NULL DEFAULT 'brand_awareness',
            status TEXT NOT NULL DEFAULT 'pending',
            parent_submission_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (parent_submission_id) REFERENCES submissions(id)
        )
    """)
    # status values: 'pending', 'evaluated', 'sent_for_review', 'approved', 'rejected'
    # parent_submission_id → agar ye ek resubmission hai toh original submission ka id
    # FOREIGN KEY → ye column dusre table ke id se linked hai (relationship)
    
    # ─────────────────────────────────────────────────────────
    # TABLE 3: evaluations — AI evaluation results
    # ─────────────────────────────────────────────────────────
    # Jab AI kisi submission ko evaluate karta hai,
    # scores aur feedback yahan save hote hain.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            overall_score REAL DEFAULT 0,
            factual_accuracy REAL DEFAULT 0,
            regulatory_compliance REAL DEFAULT 0,
            brand_identity REAL DEFAULT 0,
            visual_consistency REAL DEFAULT 0,
            campaign_effectiveness REAL DEFAULT 0,
            accessibility REAL DEFAULT 0,
            overall_design REAL DEFAULT 0,
            critical_flags TEXT DEFAULT '[]',
            feedback TEXT DEFAULT '{}',
            suggestions TEXT DEFAULT '[]',
            has_critical_issues INTEGER DEFAULT 0,
            evaluated_at TEXT NOT NULL,
            FOREIGN KEY (submission_id) REFERENCES submissions(id)
        )
    """)
    # REAL → decimal numbers (like 85.5)
    # critical_flags → JSON string — list of critical issues found
    # feedback → JSON string — detailed category-wise feedback
    # suggestions → JSON string — list of actionable suggestions
    # has_critical_issues → 0 (false) or 1 (true) — koi bada issue hai ya nahi
    
    # ─────────────────────────────────────────────────────────
    # TABLE 4: reviews — Human reviewer decisions
    # ─────────────────────────────────────────────────────────
    # Jab human reviewer approve/reject karta hai, uska record yahan.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            evaluation_id INTEGER NOT NULL,
            reviewer_name TEXT NOT NULL DEFAULT 'Manager',
            decision TEXT NOT NULL,
            comments TEXT,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY (submission_id) REFERENCES submissions(id),
            FOREIGN KEY (evaluation_id) REFERENCES evaluations(id)
        )
    """)
    # decision values: 'approved', 'rejected', 'revision_needed'
    
    # ─────────────────────────────────────────────────────────
    # TABLE 5: users — Real authentication (Improvement 1)
    # ---------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'creator',
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()   # Changes save karo (like Ctrl+S)
    conn.close()    # Connection band karo
    print("✅ Database initialized successfully!")


# ============================================================================
# CRUD FUNCTIONS — Create, Read, Update, Delete
# ============================================================================
# CRUD kya hai?
# C = Create (naya data daalo)
# R = Read   (data padhho)
# U = Update (data badlo)
# D = Delete (data mitao)
# Har application mein ye 4 basic operations hote hain.
# ============================================================================

# ─── DOCUMENTS (Knowledge Base) ─────────────────────────────────────────────

def add_document(filename, doc_type, content_preview, chunk_count):
    """Naya document record add karo jab admin koi file upload kare."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO documents (filename, doc_type, content_preview, chunk_count, uploaded_at)
           VALUES (?, ?, ?, ?, ?)""",
        (filename, doc_type, content_preview[:500] if content_preview else "", 
         chunk_count, datetime.now().isoformat())
    )
    # ? = placeholder — SQL injection attack se bachata hai
    # VALUES ke andar actual values tuple mein dete hain
    doc_id = cursor.lastrowid  # Naye record ka auto-generated id
    conn.commit()
    conn.close()
    return doc_id


def get_all_documents():
    """Saare active documents ki list nikalo."""
    conn = get_connection()
    docs = conn.execute(
        "SELECT * FROM documents WHERE is_active = 1 ORDER BY uploaded_at DESC"
    ).fetchall()
    # WHERE → filter lagao (sirf active documents)
    # ORDER BY ... DESC → newest first
    # fetchall() → saare results ek list mein do
    conn.close()
    return [dict(d) for d in docs]  # Row objects ko dictionaries mein convert karo


def delete_document(doc_id):
    """Document ko soft-delete karo (is_active = 0)."""
    conn = get_connection()
    conn.execute("UPDATE documents SET is_active = 0 WHERE id = ?", (doc_id,))
    # Soft delete = data delete nahi karte, sirf inactive mark karte hain
    # Taaki history mein record rahe
    conn.commit()
    conn.close()


# ─── SUBMISSIONS ────────────────────────────────────────────────────────────

def create_submission(creator_name, text_content, image_path, campaign_objective, 
                      parent_id=None):
    """Naya submission record banao jab creator draft submit kare."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO submissions 
           (creator_name, text_content, image_path, campaign_objective, 
            parent_submission_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (creator_name, text_content, image_path, campaign_objective,
         parent_id, datetime.now().isoformat())
    )
    sub_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sub_id


def get_submission(sub_id):
    """Ek specific submission nikalo by id."""
    conn = get_connection()
    sub = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (sub_id,)
    ).fetchone()
    # fetchone() → sirf ek result do (ya None agar nahi mila)
    conn.close()
    return dict(sub) if sub else None


def update_submission_status(sub_id, status):
    """Submission ka status update karo (pending → evaluated → approved etc.)"""
    conn = get_connection()
    conn.execute(
        "UPDATE submissions SET status = ? WHERE id = ?", (status, sub_id)
    )
    conn.commit()
    conn.close()


def get_submissions_by_status(status):
    """Ek specific status ke saare submissions nikalo."""
    conn = get_connection()
    subs = conn.execute(
        "SELECT * FROM submissions WHERE status = ? ORDER BY created_at DESC",
        (status,)
    ).fetchall()
    conn.close()
    return [dict(s) for s in subs]


def get_all_submissions():
    """Saare submissions nikalo (history ke liye)."""
    conn = get_connection()
    subs = conn.execute(
        "SELECT * FROM submissions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(s) for s in subs]


# ─── EVALUATIONS ────────────────────────────────────────────────────────────

def save_evaluation(submission_id, scores, critical_flags, feedback, suggestions,
                    has_critical):
    """
    AI evaluation results save karo.
    
    scores = dict with 7 category scores + overall_score
    critical_flags = list of critical issues
    feedback = dict with category-wise detailed feedback
    suggestions = list of actionable suggestions
    has_critical = boolean (True/False)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO evaluations 
           (submission_id, overall_score, factual_accuracy, regulatory_compliance,
            brand_identity, visual_consistency, campaign_effectiveness,
            accessibility, overall_design, critical_flags, feedback, suggestions,
            has_critical_issues, evaluated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            submission_id,
            scores.get("overall_score", 0),
            scores.get("factual_accuracy", 0),
            scores.get("regulatory_compliance", 0),
            scores.get("brand_identity", 0),
            scores.get("visual_consistency", 0),
            scores.get("campaign_effectiveness", 0),
            scores.get("accessibility", 0),
            scores.get("overall_design", 0),
            json.dumps(critical_flags),   # List → JSON string
            json.dumps(feedback),          # Dict → JSON string
            json.dumps(suggestions),       # List → JSON string
            1 if has_critical else 0,      # Boolean → 0 or 1
            datetime.now().isoformat()
        )
    )
    eval_id = cursor.lastrowid
    
    # Submission ka status bhi update karo
    conn.execute(
        "UPDATE submissions SET status = 'evaluated' WHERE id = ?",
        (submission_id,)
    )
    
    conn.commit()
    conn.close()
    return eval_id


def get_evaluation(eval_id):
    """Ek specific evaluation nikalo."""
    conn = get_connection()
    ev = conn.execute(
        "SELECT * FROM evaluations WHERE id = ?", (eval_id,)
    ).fetchone()
    conn.close()
    if ev:
        ev = dict(ev)
        # JSON strings ko wapas Python objects mein convert karo
        ev["critical_flags"] = json.loads(ev["critical_flags"])
        ev["feedback"] = json.loads(ev["feedback"])
        ev["suggestions"] = json.loads(ev["suggestions"])
        return ev
    return None


def get_evaluations_for_submission(sub_id):
    """Ek submission ke saare evaluations nikalo (revision history)."""
    conn = get_connection()
    evs = conn.execute(
        "SELECT * FROM evaluations WHERE submission_id = ? ORDER BY evaluated_at DESC",
        (sub_id,)
    ).fetchall()
    conn.close()
    results = []
    for ev in evs:
        ev = dict(ev)
        ev["critical_flags"] = json.loads(ev["critical_flags"])
        ev["feedback"] = json.loads(ev["feedback"])
        ev["suggestions"] = json.loads(ev["suggestions"])
        results.append(ev)
    return results


def get_latest_evaluation(sub_id):
    """Ek submission ka sabse recent evaluation nikalo."""
    conn = get_connection()
    ev = conn.execute(
        "SELECT * FROM evaluations WHERE submission_id = ? ORDER BY evaluated_at DESC LIMIT 1",
        (sub_id,)
    ).fetchone()
    # LIMIT 1 → sirf 1 result do (sabse naya, kyunki DESC order hai)
    conn.close()
    if ev:
        ev = dict(ev)
        ev["critical_flags"] = json.loads(ev["critical_flags"])
        ev["feedback"] = json.loads(ev["feedback"])
        ev["suggestions"] = json.loads(ev["suggestions"])
        return ev
    return None


# ─── REVIEWS ────────────────────────────────────────────────────────────────

def save_review(submission_id, evaluation_id, reviewer_name, decision, comments):
    """Human reviewer ka decision save karo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO reviews (submission_id, evaluation_id, reviewer_name, 
           decision, comments, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (submission_id, evaluation_id, reviewer_name, decision, comments,
         datetime.now().isoformat())
    )
    
    # Submission ka status bhi update karo based on decision
    new_status = {
        "approved": "approved",
        "rejected": "rejected",
        "revision_needed": "pending"
    }.get(decision, "pending")
    
    conn.execute(
        "UPDATE submissions SET status = ? WHERE id = ?",
        (new_status, submission_id)
    )
    
    review_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return review_id


def get_reviews_for_submission(sub_id):
    """Ek submission ke saare review decisions nikalo."""
    conn = get_connection()
    revs = conn.execute(
        "SELECT * FROM reviews WHERE submission_id = ? ORDER BY reviewed_at DESC",
        (sub_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in revs]


def get_reviewable_submissions():
    """
    Wo submissions nikalo jo human review ke liye ready hain.
    Condition: status = 'evaluated' AND latest eval score >= 85 AND no critical issues
    """
    conn = get_connection()
    subs = conn.execute("""
        SELECT s.*, e.overall_score, e.has_critical_issues, e.id as eval_id
        FROM submissions s
        JOIN evaluations e ON e.submission_id = s.id
        WHERE s.status = 'sent_for_review'
        AND e.id = (
            SELECT MAX(e2.id) FROM evaluations e2 
            WHERE e2.submission_id = s.id
        )
        ORDER BY s.created_at DESC
    """).fetchall()
    # JOIN → do tables ko merge karo (submissions + evaluations)
    # Subquery → har submission ka latest evaluation dhundho
    conn.close()
    return [dict(s) for s in subs]


# ─── DASHBOARD / ANALYTICS ─────────────────────────────────────────────────

def get_dashboard_stats():
    """Dashboard ke liye overall statistics nikalo."""
    conn = get_connection()
    
    stats = {}
    
    # Total submissions
    stats["total_submissions"] = conn.execute(
        "SELECT COUNT(*) FROM submissions"
    ).fetchone()[0]
    # COUNT(*) → total rows gino
    
    # Status-wise counts
    for status in ["pending", "evaluated", "sent_for_review", "approved", "rejected"]:
        stats[f"{status}_count"] = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = ?", (status,)
        ).fetchone()[0]
    
    # Average score
    avg = conn.execute(
        "SELECT AVG(overall_score) FROM evaluations"
    ).fetchone()[0]
    stats["average_score"] = round(avg, 1) if avg else 0
    # AVG() → average calculate karo
    
    # Total documents in knowledge base
    stats["total_documents"] = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE is_active = 1"
    ).fetchone()[0]
    
    conn.close()
    return stats


# ─── INITIALIZATION ─────────────────────────────────────────────────────────


# ─── USERS / AUTHENTICATION (Improvement 1) ──────────────────────────────

def register_user(username, password, role="creator"):
    """New user register karo with bcrypt hashed password."""
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username.strip(), password_hash, role, datetime.now().isoformat()),
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def authenticate_user(username, password):
    """Username + password verify karo. Returns user dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    user = dict(row)
    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return user
    return None


def get_approved_submissions():
    """All submissions that were approved by a human reviewer."""
    conn = get_connection()
    subs = conn.execute("""
        SELECT s.*, e.overall_score, e.id as eval_id
        FROM submissions s
        LEFT JOIN evaluations e ON e.id = (
            SELECT MAX(e2.id) FROM evaluations e2 WHERE e2.submission_id = s.id
        )
        WHERE s.status = 'approved'
        ORDER BY s.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(s) for s in subs]


def delete_all_submissions():
    """Delete all submissions, evaluations, and reviews (clear history)."""
    conn = get_connection()
    conn.execute("DELETE FROM reviews")
    conn.execute("DELETE FROM evaluations")
    conn.execute("DELETE FROM submissions")
    conn.commit()
    conn.close()


def get_submissions_by_creator(creator_name):
    """Sirf ek specific creator ke submissions nikalo (Improvement 1 — own history only)."""
    conn = get_connection()
    subs = conn.execute(
        "SELECT * FROM submissions WHERE creator_name = ? ORDER BY created_at DESC",
        (creator_name,),
    ).fetchall()
    conn.close()
    return [dict(s) for s in subs]


# ─── ANALYTICS QUERIES (Improvement 3) ───────────────────────────────────

def get_score_distribution():
    """Score distribution for histogram (buckets of 10)."""
    conn = get_connection()
    rows = conn.execute("SELECT overall_score FROM evaluations ORDER BY overall_score").fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_category_averages():
    """Average score per category for radar chart."""
    conn = get_connection()
    row = conn.execute("""
        SELECT
            AVG(factual_accuracy)       AS factual_accuracy,
            AVG(regulatory_compliance)  AS regulatory_compliance,
            AVG(brand_identity)         AS brand_identity,
            AVG(visual_consistency)     AS visual_consistency,
            AVG(campaign_effectiveness) AS campaign_effectiveness,
            AVG(accessibility)          AS accessibility,
            AVG(overall_design)         AS overall_design
        FROM evaluations
    """).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}


def get_approval_trend():
    """Daily approval trend — count of approved/rejected per day."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DATE(reviewed_at) AS day, decision, COUNT(*) AS cnt
        FROM reviews
        GROUP BY day, decision
        ORDER BY day
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_common_failure_categories():
    """Most common failure categories (categories where avg score < 70)."""
    conn = get_connection()
    row = conn.execute("""
        SELECT
            AVG(factual_accuracy)       AS factual_accuracy,
            AVG(regulatory_compliance)  AS regulatory_compliance,
            AVG(brand_identity)         AS brand_identity,
            AVG(visual_consistency)     AS visual_consistency,
            AVG(campaign_effectiveness) AS campaign_effectiveness,
            AVG(accessibility)          AS accessibility,
            AVG(overall_design)         AS overall_design
        FROM evaluations
    """).fetchone()
    conn.close()
    if not row:
        return []
    data = dict(row)
    failures = [(cat.replace("_", " ").title(), round(score or 0, 1))
                for cat, score in data.items() if (score or 0) < 70]
    failures.sort(key=lambda x: x[1])
    return failures


# Jab ye file import hogi, automatically database initialize ho jayega
init_db()
