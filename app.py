"""
SignCollect — Multi-Signature PDF Collection App
================================================
Collects multiple signatures on a PDF document.
Each signer gets a unique signing link.
All signatures are embedded into the final PDF.

Routing via ?view= query params:
  (none)                     → Dashboard (list documents)
  ?view=upload               → Admin: upload PDF + add signers
  ?view=document&id=<uuid>   → Document detail + status
  ?view=sign&doc=<uuid>&signer=<uuid>  → Signer view
"""

import io
import base64
import datetime
import json
import numpy as np
import streamlit as st
from PIL import Image

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SignCollect",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Hide default Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* App shell */
  .app-header {
    background: linear-gradient(135deg, #0f2942 0%, #1e4d8c 100%);
    border-radius: 14px;
    padding: 22px 32px;
    margin-bottom: 28px;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 18px;
  }
  .app-header .logo { font-size: 2.2rem; }
  .app-header h1 { margin: 0; font-size: 1.7rem; font-weight: 800; letter-spacing: -.5px; }
  .app-header p  { margin: 4px 0 0; opacity: .75; font-size: .9rem; }

  /* Nav pills */
  .nav-bar { display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }
  .nav-pill {
    background: #e8f0fe; color: #1a56db;
    border-radius: 20px; padding: 6px 18px;
    font-size: .85rem; font-weight: 600;
    text-decoration: none; cursor: pointer;
    border: none;
  }
  .nav-pill.active { background: #1a56db; color: #fff; }

  /* Cards */
  .card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 22px 26px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }
  .card h3 { margin: 0 0 6px; font-size: 1.05rem; color: #111827; }
  .card p  { margin: 0; color: #6b7280; font-size: .88rem; }

  /* Status badges */
  .badge {
    display: inline-block;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .4px;
  }
  .badge-pending   { background: #fef3c7; color: #92400e; }
  .badge-partial   { background: #dbeafe; color: #1e40af; }
  .badge-complete  { background: #d1fae5; color: #065f46; }
  .badge-signed    { background: #d1fae5; color: #065f46; }

  /* Signer row */
  .signer-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 0;
    border-bottom: 1px solid #f3f4f6;
  }
  .signer-avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: #1e4d8c;
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: .95rem;
    flex-shrink: 0;
  }
  .signer-info { flex: 1; }
  .signer-info strong { display: block; font-size: .92rem; color: #111827; }
  .signer-info span   { font-size: .82rem; color: #6b7280; }

  /* Step indicator */
  .steps { display: flex; gap: 0; margin-bottom: 28px; }
  .step {
    flex: 1;
    padding: 10px 6px;
    text-align: center;
    font-size: .82rem;
    font-weight: 600;
    color: #9ca3af;
    border-bottom: 3px solid #e5e7eb;
  }
  .step.active { color: #1a56db; border-bottom-color: #1a56db; }
  .step.done   { color: #065f46; border-bottom-color: #10b981; }

  /* Signature canvas wrapper */
  .canvas-wrap {
    border: 2px dashed #93c5fd;
    border-radius: 10px;
    padding: 4px;
    background: #f8faff;
  }

  /* Info banner */
  .info-banner {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 12px 18px;
    color: #1e40af;
    font-size: .88rem;
    margin-bottom: 14px;
  }

  /* Copy-link box */
  .link-box {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: monospace;
    font-size: .82rem;
    color: #334155;
    word-break: break-all;
    margin: 6px 0;
  }

  /* Progress bar custom */
  .prog-bar-bg { background: #e5e7eb; border-radius: 9px; height: 10px; overflow: hidden; margin: 6px 0; }
  .prog-bar-fill { background: #10b981; height: 100%; border-radius: 9px; transition: width .4s; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Supabase client
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_supabase():
    from supabase import create_client

    def _get(key: str) -> str:
        """Try multiple secret layouts that users commonly have."""
        # 1. Flat top-level  →  SUPABASE_URL = "..."
        if key in st.secrets:
            return st.secrets[key]
        # 2. Under [supabase] section  →  url = "..."
        section_key = key.replace("SUPABASE_", "").lower()
        if "supabase" in st.secrets:
            sec = st.secrets["supabase"]
            if section_key in sec:
                return sec[section_key]
        # 3. Under [connections.supabase]  (Streamlit native connections)
        try:
            val = st.secrets["connections"]["supabase"][section_key]
            if val:
                return val
        except (KeyError, TypeError):
            pass
        # Nothing found — show helpful diagnostics
        available = list(st.secrets.keys())
        nested = {k: list(st.secrets[k].keys())
                  for k in available if isinstance(st.secrets.get(k), dict)}
        st.error(
            f"**Cannot find secret `{key}`.**\n\n"
            f"Top-level keys visible: `{available}`\n\n"
            f"Nested keys visible: `{nested}`\n\n"
            "Your `secrets.toml` (or Streamlit Cloud Secrets) should look like:\n\n"
            "```toml\n"
            'SUPABASE_URL = "https://xxxx.supabase.co"\n'
            'SUPABASE_KEY = "eyJ..."\n'
            'APP_URL      = "https://your-app.streamlit.app"\n'
            "```\n\n"
            "Make sure there is **no `[section]` header** above these lines."
        )
        st.stop()

    url = _get("SUPABASE_URL")
    key = _get("SUPABASE_KEY")
    return create_client(url, key)

BUCKET = "pdf-documents"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — Storage
# ══════════════════════════════════════════════════════════════════════════════
def upload_pdf_to_storage(sb, doc_id: str, pdf_bytes: bytes, filename: str = "original.pdf") -> str:
    path = f"{doc_id}/{filename}"
    sb.storage.from_(BUCKET).upload(
        path,
        pdf_bytes,
        {"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def download_pdf_from_storage(sb, path: str) -> bytes:
    res = sb.storage.from_(BUCKET).download(path)
    return res


def get_public_url(sb, path: str) -> str:
    return sb.storage.from_(BUCKET).get_public_url(path)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — Database
# ══════════════════════════════════════════════════════════════════════════════
def fetch_documents(sb):
    return (
        sb.table("documents")
        .select("*, signers(id, name, email, status, signed_at)")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def fetch_document(sb, doc_id: str):
    return (
        sb.table("documents")
        .select("*, signers(id, name, email, role, status, signed_at, order_index)")
        .eq("id", doc_id)
        .single()
        .execute()
        .data
    )


def fetch_signer(sb, signer_id: str):
    return (
        sb.table("signers")
        .select("*, documents(id, title, storage_path, status)")
        .eq("id", signer_id)
        .single()
        .execute()
        .data
    )


def fetch_signatures(sb, doc_id: str):
    return (
        sb.table("signatures")
        .select("*")
        .eq("document_id", doc_id)
        .order("created_at")
        .execute()
        .data
    )


def create_document(sb, title: str, file_name: str, storage_path: str) -> str:
    res = (
        sb.table("documents")
        .insert({"title": title, "file_name": file_name, "storage_path": storage_path, "status": "pending"})
        .execute()
    )
    return res.data[0]["id"]


def create_signer(sb, doc_id: str, name: str, email: str, role: str, order_index: int):
    sb.table("signers").insert({
        "document_id": doc_id,
        "name": name,
        "email": email,
        "role": role,
        "order_index": order_index,
        "status": "pending",
    }).execute()


def save_signature(sb, doc_id: str, signer_id: str, sig_b64: str, page: int,
                   x_pct: float, y_pct: float, w_pct: float,
                   signer_name: str, signer_role: str):
    sb.table("signatures").insert({
        "document_id": doc_id,
        "signer_id": signer_id,
        "signature_image": sig_b64,
        "page_number": page,
        "x_position": x_pct,
        "y_position": y_pct,
        "width_percent": w_pct,
        "signer_name": signer_name,
        "signer_role": signer_role,
        "signed_at": datetime.datetime.utcnow().isoformat(),
    }).execute()

    sb.table("signers").update({
        "status": "signed",
        "signed_at": datetime.datetime.utcnow().isoformat(),
    }).eq("id", signer_id).execute()


def refresh_document_status(sb, doc_id: str):
    signers = sb.table("signers").select("status").eq("document_id", doc_id).execute().data
    total   = len(signers)
    signed  = sum(1 for s in signers if s["status"] == "signed")

    if total == 0:
        new_status = "pending"
    elif signed == 0:
        new_status = "pending"
    elif signed < total:
        new_status = "partial"
    else:
        new_status = "complete"

    sb.table("documents").update({"status": new_status}).eq("id", doc_id).execute()
    return new_status, signed, total


# ══════════════════════════════════════════════════════════════════════════════
# PDF helpers
# ══════════════════════════════════════════════════════════════════════════════
def render_page_preview(pdf_bytes: bytes, page_index: int = 0) -> Image.Image | None:
    try:
        import fitz
        doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_index)
        pix  = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    except Exception:
        pass
    try:
        from pdf2image import convert_from_bytes
        imgs = convert_from_bytes(pdf_bytes, dpi=110,
                                  first_page=page_index + 1,
                                  last_page=page_index + 1)
        return imgs[0] if imgs else None
    except Exception:
        return None


def build_signed_pdf(pdf_bytes: bytes, signatures: list) -> bytes:
    """Overlay all collected signatures onto the PDF and return signed bytes."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader, PdfWriter

    reader   = PdfReader(io.BytesIO(pdf_bytes))
    overlays = {}  # page_index → overlay buffer

    for sig in signatures:
        page_idx = int(sig["page_number"]) - 1
        page_obj = reader.pages[page_idx]
        pw = float(page_obj.mediabox.width)
        ph = float(page_obj.mediabox.height)

        if page_idx not in overlays:
            buf = io.BytesIO()
            overlays[page_idx] = {"buf": buf, "canvas": rl_canvas.Canvas(buf, pagesize=(pw, ph)), "pw": pw, "ph": ph}

        c   = overlays[page_idx]["canvas"]
        margin = 14

        # Decode base64 signature image
        sig_bytes = base64.b64decode(sig["signature_image"])
        sig_img   = Image.open(io.BytesIO(sig_bytes)).convert("RGBA")

        sig_w_pt = pw * float(sig["width_percent"])
        sig_h_pt = sig_w_pt * (sig_img.height / sig_img.width)

        x_pt = pw * float(sig["x_position"])
        y_pt = ph * float(sig["y_position"])

        # Clamp to page bounds
        x_pt = max(margin, min(x_pt, pw - sig_w_pt - margin))
        y_pt = max(margin + 22, min(y_pt, ph - sig_h_pt - margin))

        buf_sig = io.BytesIO()
        sig_img.save(buf_sig, format="PNG")
        buf_sig.seek(0)
        c.drawImage(ImageReader(buf_sig), x_pt, y_pt, sig_w_pt, sig_h_pt, mask="auto")

        # Label
        c.setFont("Helvetica", 7.5)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        date_str = sig.get("signed_at", "")[:10]
        label = f"{sig['signer_name']}"
        if sig.get("signer_role"):
            label += f" · {sig['signer_role']}"
        label += f"  {date_str}"
        c.drawString(x_pt, y_pt - 10, label)
        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.5)
        c.line(x_pt, y_pt - 2, x_pt + sig_w_pt, y_pt - 2)

    # Finalise each overlay canvas
    merged_overlays = {}
    for page_idx, ov in overlays.items():
        ov["canvas"].save()
        ov["buf"].seek(0)
        merged_overlays[page_idx] = PdfReader(ov["buf"]).pages[0]

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in merged_overlays:
            page.merge_page(merged_overlays[i])
        writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(dict(reader.metadata))

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# UI — Shared components
# ══════════════════════════════════════════════════════════════════════════════
def render_header(subtitle="Multi-signature PDF collection"):
    st.markdown(f"""
    <div class="app-header">
      <div class="logo">✍️</div>
      <div>
        <h1>SignCollect</h1>
        <p>{subtitle}</p>
      </div>
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    mapping = {
        "pending":  ("badge-pending",  "Pending"),
        "partial":  ("badge-partial",  "Partially Signed"),
        "complete": ("badge-complete", "Complete"),
        "signed":   ("badge-signed",   "Signed"),
    }
    cls, label = mapping.get(status, ("badge-pending", status.title()))
    return f'<span class="badge {cls}">{label}</span>'


def progress_html(signed: int, total: int) -> str:
    pct = int(signed / total * 100) if total else 0
    return f"""
    <div style="font-size:.82rem;color:#6b7280;margin-bottom:4px">{signed} of {total} signed</div>
    <div class="prog-bar-bg"><div class="prog-bar-fill" style="width:{pct}%"></div></div>
    """


def app_url() -> str:
    """Best-effort: return the base URL of the running app."""
    try:
        # Works on Streamlit Cloud
        return st.secrets.get("APP_URL", "http://localhost:8501")
    except Exception:
        return "http://localhost:8501"


def signing_url(doc_id: str, signer_id: str) -> str:
    base = app_url().rstrip("/")
    return f"{base}/?view=sign&doc={doc_id}&signer={signer_id}"


def nav(active="dashboard"):
    st.markdown('<div class="nav-bar">', unsafe_allow_html=True)
    pages = [("dashboard", "🏠 Dashboard"), ("upload", "📤 Upload PDF")]
    for key, label in pages:
        cls = "nav-pill active" if active == key else "nav-pill"
        if st.button(label, key=f"nav_{key}"):
            st.query_params.clear()
            if key != "dashboard":
                st.query_params["view"] = key
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — Dashboard
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard(sb):
    render_header()
    nav("dashboard")

    docs = fetch_documents(sb)

    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.subheader(f"Documents ({len(docs)})")
    with col_btn:
        if st.button("+ Upload PDF", type="primary"):
            st.query_params["view"] = "upload"
            st.rerun()

    if not docs:
        st.info("No documents yet. Click **+ Upload PDF** to get started.")
        return

    for doc in docs:
        signers      = doc.get("signers", [])
        total        = len(signers)
        signed       = sum(1 for s in signers if s["status"] == "signed")
        status       = doc.get("status", "pending")

        with st.container():
            c1, c2, c3 = st.columns([5, 3, 1])
            with c1:
                st.markdown(f"""
                <div class="card" style="margin-bottom:0">
                  <h3>📄 {doc['title'] or doc['file_name']}</h3>
                  <p>Uploaded {doc['created_at'][:10]} &nbsp;·&nbsp; {doc['file_name']}</p>
                  {progress_html(signed, total)}
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div style="padding-top:28px">{status_badge(status)}</div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown("<div style='padding-top:22px'>", unsafe_allow_html=True)
                if st.button("Open →", key=f"open_{doc['id']}"):
                    st.query_params["view"] = "document"
                    st.query_params["id"]   = doc["id"]
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — Upload
# ══════════════════════════════════════════════════════════════════════════════
def page_upload(sb):
    render_header("Upload a new document for signing")
    nav("upload")

    st.markdown("### Step 1 — Upload PDF")
    uploaded = st.file_uploader("Choose a PDF", type=["pdf"])

    if not uploaded:
        st.info("Upload a PDF to continue.")
        return

    pdf_bytes = uploaded.read()
    st.success(f"✅ {uploaded.name} — {len(pdf_bytes)/1024:.1f} KB")

    # Quick preview
    preview = render_page_preview(pdf_bytes, 0)
    if preview:
        st.image(preview, caption="First page preview", width=320)

    st.divider()
    st.markdown("### Step 2 — Document details")
    title = st.text_input("Document title", value=uploaded.name.rsplit(".", 1)[0])

    st.divider()
    st.markdown("### Step 3 — Add signers")
    st.caption("Add everyone who needs to sign this document. They will each receive a unique signing link.")

    # Dynamic signer list in session state
    if "upload_signers" not in st.session_state:
        st.session_state.upload_signers = [{"name": "", "email": "", "role": ""}]

    for i, signer in enumerate(st.session_state.upload_signers):
        c1, c2, c3, c4 = st.columns([3, 3, 2, 0.6])
        with c1:
            st.session_state.upload_signers[i]["name"]  = st.text_input(
                "Full name", value=signer["name"], key=f"sname_{i}", placeholder="Jane Smith")
        with c2:
            st.session_state.upload_signers[i]["email"] = st.text_input(
                "Email", value=signer["email"], key=f"semail_{i}", placeholder="jane@company.com")
        with c3:
            st.session_state.upload_signers[i]["role"]  = st.text_input(
                "Role / Title", value=signer["role"], key=f"srole_{i}", placeholder="Manager")
        with c4:
            st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
            if st.button("✕", key=f"del_{i}", help="Remove") and len(st.session_state.upload_signers) > 1:
                st.session_state.upload_signers.pop(i)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("+ Add signer"):
        st.session_state.upload_signers.append({"name": "", "email": "", "role": ""})
        st.rerun()

    st.divider()
    st.markdown("### Step 4 — Submit")

    # Validate
    valid_signers = [s for s in st.session_state.upload_signers if s["name"].strip()]
    st.markdown(f"**{len(valid_signers)} signer(s)** will be added.")

    submit = st.button("🚀 Create Document & Generate Signing Links", type="primary", use_container_width=True)

    if submit:
        if not title.strip():
            st.error("Please enter a document title.")
            return
        if not valid_signers:
            st.error("Add at least one signer.")
            return

        with st.spinner("Uploading to Supabase…"):
            import uuid
            doc_id       = str(uuid.uuid4())
            storage_path = upload_pdf_to_storage(sb, doc_id, pdf_bytes, uploaded.name)
            create_document(sb, title.strip(), uploaded.name, storage_path)

            for idx, s in enumerate(valid_signers):
                create_signer(sb, doc_id, s["name"].strip(), s["email"].strip(), s["role"].strip(), idx)

        st.success("✅ Document created!")
        st.session_state.pop("upload_signers", None)

        # Show signing links immediately
        doc = fetch_document(sb, doc_id)
        st.markdown("### Signing links")
        st.info("Share each link with the corresponding signer.")
        for signer in doc.get("signers", []):
            url = signing_url(doc_id, signer["id"])
            st.markdown(f"**{signer['name']}** ({signer.get('role', '')})")
            st.markdown(f'<div class="link-box">{url}</div>', unsafe_allow_html=True)
            st.caption("Copy and send this link to the signer.")

        if st.button("← Back to Dashboard"):
            st.query_params.clear()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — Document Detail
# ══════════════════════════════════════════════════════════════════════════════
def page_document(sb, doc_id: str):
    doc = fetch_document(sb, doc_id)
    if not doc:
        st.error("Document not found.")
        return

    render_header(doc["title"] or doc["file_name"])
    nav()

    if st.button("← Dashboard"):
        st.query_params.clear()
        st.rerun()

    signers    = sorted(doc.get("signers", []), key=lambda s: s.get("order_index", 0))
    total      = len(signers)
    signed_ct  = sum(1 for s in signers if s["status"] == "signed")
    status, _, _ = refresh_document_status(sb, doc_id)

    # ── Status summary ────────────────────────────────────────────────────────
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(f"""
        <div class="card">
          <h3>📄 {doc['title']}</h3>
          <p style="margin-bottom:10px">{doc['file_name']} &nbsp;·&nbsp; Uploaded {doc['created_at'][:10]}</p>
          {progress_html(signed_ct, total)}
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown(f'<div style="padding-top:30px">{status_badge(status)}</div>', unsafe_allow_html=True)

    # ── Signers table ─────────────────────────────────────────────────────────
    st.markdown("### Signers")
    for s in signers:
        badge    = status_badge(s["status"])
        initials = "".join(w[0].upper() for w in s["name"].split()[:2])
        signed_info = f"Signed {s['signed_at'][:10]}" if s.get("signed_at") else "Awaiting signature"
        url = signing_url(doc_id, s["id"])

        st.markdown(f"""
        <div class="signer-row">
          <div class="signer-avatar">{initials}</div>
          <div class="signer-info">
            <strong>{s['name']}</strong>
            <span>{s.get('role', '')} &nbsp;·&nbsp; {s['email']} &nbsp;·&nbsp; {signed_info}</span>
          </div>
          <div>{badge}</div>
        </div>
        """, unsafe_allow_html=True)

        if s["status"] == "pending":
            with st.expander(f"🔗 Signing link for {s['name']}"):
                st.markdown(f'<div class="link-box">{url}</div>', unsafe_allow_html=True)
                st.caption("Copy and share this link with the signer.")

    # ── Download signed PDF ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### Download")

    if status == "complete":
        st.markdown('<div class="info-banner">🎉 All signers have signed. Download the fully signed PDF below.</div>', unsafe_allow_html=True)
    elif signed_ct > 0:
        st.markdown(f'<div class="info-banner">⏳ {total - signed_ct} signer(s) still pending. You can download a partially-signed PDF now.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-banner">No signatures collected yet.</div>', unsafe_allow_html=True)

    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        if st.button("⬇️ Download original PDF"):
            with st.spinner("Fetching…"):
                pdf_bytes = download_pdf_from_storage(sb, doc["storage_path"])
                st.download_button(
                    "📥 Download Original",
                    data=pdf_bytes,
                    file_name=doc["file_name"],
                    mime="application/pdf",
                )

    with col_dl2:
        if signed_ct > 0:
            if st.button("⬇️ Build & download signed PDF"):
                with st.spinner("Embedding signatures…"):
                    pdf_bytes  = download_pdf_from_storage(sb, doc["storage_path"])
                    sigs       = fetch_signatures(sb, doc_id)
                    signed_pdf = build_signed_pdf(pdf_bytes, sigs)

                    # Also save to Supabase storage
                    upload_pdf_to_storage(sb, doc_id, signed_pdf, "signed.pdf")

                    st.download_button(
                        "📥 Download Signed PDF",
                        data=signed_pdf,
                        file_name=f"signed_{doc['file_name']}",
                        mime="application/pdf",
                        key="dl_signed",
                    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — Sign
# ══════════════════════════════════════════════════════════════════════════════
def page_sign(sb, doc_id: str, signer_id: str):
    signer = fetch_signer(sb, signer_id)
    if not signer:
        st.error("Signer record not found. Check your link.")
        return

    doc = signer.get("documents") or {}

    if signer["status"] == "signed":
        render_header(f"Already signed — {doc.get('title', '')}")
        st.success(f"✅ You already signed this document on {signer['signed_at'][:10]}. Thank you!")
        return

    render_header(f"Sign: {doc.get('title', 'Document')}")

    st.markdown(f"""
    <div class="info-banner">
      You have been asked to sign <strong>{doc.get('title', 'this document')}</strong>.
      Draw your signature below and confirm.
    </div>
    """, unsafe_allow_html=True)

    # ── Steps ─────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="steps">
      <div class="step active">1 · Review</div>
      <div class="step active">2 · Draw Signature</div>
      <div class="step active">3 · Place & Confirm</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load PDF for preview ─────────────────────────────────────────────────
    pdf_bytes = None
    try:
        pdf_bytes = download_pdf_from_storage(sb, doc.get("storage_path", ""))
    except Exception:
        st.warning("Could not load PDF preview.")

    from pypdf import PdfReader
    total_pages = 1
    if pdf_bytes:
        try:
            total_pages = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
        except Exception:
            pass

    left_col, right_col = st.columns([5, 4])

    with right_col:
        st.markdown("#### ✍️ Draw your signature")
        try:
            from streamlit_drawable_canvas import st_canvas
            stroke_color = st.color_picker("Ink colour", "#000000", key="sig_ink")
            stroke_w     = st.slider("Stroke width", 1, 5, 3, key="sig_stroke")

            st.markdown('<div class="canvas-wrap">', unsafe_allow_html=True)
            canvas_result = st_canvas(
                fill_color="rgba(255,255,255,0)",
                stroke_width=stroke_w,
                stroke_color=stroke_color,
                background_color="#ffffff",
                height=150,
                width=400,
                drawing_mode="freedraw",
                key="sign_canvas",
                display_toolbar=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        except ImportError:
            st.error("Missing: `pip install streamlit-drawable-canvas`")
            return

        # Signer details
        st.markdown("#### Your details")
        signer_name_input = st.text_input("Full name", value=signer["name"])
        signer_role_input = st.text_input("Title / Role", value=signer.get("role", ""))
        sign_date = st.date_input("Date", value=datetime.date.today())

    with left_col:
        st.markdown("#### 📄 Document preview & placement")

        target_page = st.selectbox(
            "Place signature on page",
            list(range(1, total_pages + 1)),
            format_func=lambda x: f"Page {x}",
        ) - 1

        col_h, col_v = st.columns(2)
        with col_h:
            h_pos = st.selectbox("Horizontal", ["Left", "Centre", "Right"], index=2)
        with col_v:
            v_pos = st.selectbox("Vertical",   ["Top",  "Middle", "Bottom"], index=2)

        sig_scale = st.slider("Signature width (% of page)", 10, 50, 25)

        if pdf_bytes:
            preview = render_page_preview(pdf_bytes, target_page)
            if preview:
                st.image(preview, caption=f"Page {target_page + 1}", use_container_width=True)

    # ── Capture & submit ──────────────────────────────────────────────────────
    signature_ready = False
    sig_pil = None
    if canvas_result.image_data is not None:
        arr = canvas_result.image_data.astype(np.uint8)
        if arr[:, :, :3].sum() < (arr.shape[0] * arr.shape[1] * 3 * 255 - 500):
            sig_pil = Image.fromarray(arr, "RGBA")
            bbox = sig_pil.getbbox()
            if bbox:
                sig_pil = sig_pil.crop(bbox)
                signature_ready = True

    st.divider()

    if not signature_ready:
        st.warning("✋ Draw your signature in the pad above before submitting.")
    else:
        st.success("✅ Signature ready.")

    submit = st.button(
        "✅ Submit Signature",
        type="primary",
        use_container_width=True,
        disabled=not signature_ready,
    )

    if submit and signature_ready and sig_pil:
        # Compute position as fraction of page dimensions
        margin_frac = 0.02
        w_frac = sig_scale / 100

        if h_pos == "Left":
            x_frac = margin_frac
        elif h_pos == "Centre":
            x_frac = (1 - w_frac) / 2
        else:
            x_frac = 1 - w_frac - margin_frac

        sig_h_frac = w_frac * (sig_pil.height / sig_pil.width)
        label_frac  = 0.04

        if v_pos == "Top":
            y_frac = 1 - sig_h_frac - margin_frac
        elif v_pos == "Middle":
            y_frac = (1 - sig_h_frac - label_frac) / 2
        else:
            y_frac = margin_frac + label_frac

        # Encode signature as base64 PNG
        buf = io.BytesIO()
        sig_pil.save(buf, format="PNG")
        sig_b64 = base64.b64encode(buf.getvalue()).decode()

        with st.spinner("Saving signature…"):
            save_signature(
                sb, doc_id, signer_id, sig_b64,
                page=target_page + 1,
                x_pct=x_frac, y_pct=y_frac, w_pct=w_frac,
                signer_name=signer_name_input,
                signer_role=signer_role_input,
            )
            refresh_document_status(sb, doc_id)

        st.balloons()
        st.success("🎉 Your signature has been recorded. Thank you!")
        st.info("You can close this tab. The document owner will be notified.")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════════════════════
def main():
    try:
        sb = get_supabase()
    except Exception as e:
        st.error("⚠️ Could not connect to Supabase. Check your secrets configuration.")
        st.exception(e)
        st.stop()

    params = st.query_params
    view   = params.get("view", "dashboard")

    if view == "upload":
        page_upload(sb)
    elif view == "document":
        doc_id = params.get("id", "")
        if not doc_id:
            st.error("Missing document ID.")
        else:
            page_document(sb, doc_id)
    elif view == "sign":
        doc_id    = params.get("doc", "")
        signer_id = params.get("signer", "")
        if not doc_id or not signer_id:
            st.error("Invalid signing link — missing parameters.")
        else:
            page_sign(sb, doc_id, signer_id)
    else:
        page_dashboard(sb)


if __name__ == "__main__":
    main()
