# ✍️ SignCollect — Multi-Signature PDF Collection App

Collect multiple signatures on any PDF document.  
Upload a PDF → add signers → share unique links → download the signed document.

**Stack:** Streamlit · Supabase (Storage + Postgres) · ReportLab · pypdf

---

## ✨ Features

- 📤 Upload any PDF and store it securely in Supabase Storage
- 👥 Add multiple signers (name, email, role)
- 🔗 Unique signing link generated per signer
- ✍️ Freehand signature drawing pad in the browser
- 📍 Signers choose which page and position for their signature
- 📊 Real-time signing progress dashboard
- 📥 Download partially or fully signed PDF with all signatures embedded
- 🔄 Auto-updates document status (pending → partial → complete)

---

## 🚀 Quick Start (Local)

```bash
git clone https://github.com/YOUR_USERNAME/signcollect.git
cd signcollect

pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# → edit secrets.toml with your Supabase credentials

streamlit run app.py
```

---

## ☁️ Deploy to Streamlit Community Cloud (Free)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/signcollect.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click **New app** → select your repo → `app.py`
   - Click **Advanced settings → Secrets** and paste:
     ```toml
     SUPABASE_URL = "https://xxxx.supabase.co"
     SUPABASE_KEY = "eyJ..."
     APP_URL = "https://your-app-name.streamlit.app"
     ```
   - Click **Deploy** — done!

3. **Update `APP_URL`** in your secrets once you know your app's URL.

---

## 🗄️ Supabase Setup

### 1. Create a Supabase project
Go to [supabase.com](https://supabase.com) → New Project.

### 2. Run the database migrations
- Open **SQL Editor** in your Supabase dashboard
- Paste the full contents of `supabase_setup.sql`
- Click **Run**

This creates:
| Table | Purpose |
|-------|---------|
| `documents` | Uploaded PDF metadata + signing status |
| `signers` | One row per person who needs to sign |
| `signatures` | Stored signature images + position metadata |

And a Storage bucket: `pdf-documents`

### 3. Get your credentials
- **Project URL:** Settings → API → Project URL
- **Anon key:** Settings → API → `anon` `public`

---

## 📁 Project Structure

```
signcollect/
├── app.py                          # Main Streamlit app (all pages)
├── requirements.txt                # Python dependencies
├── supabase_setup.sql              # Run once in Supabase SQL Editor
├── .gitignore                      # Excludes secrets.toml
├── .streamlit/
│   └── secrets.toml.example        # Template — copy to secrets.toml
└── README.md
```

---

## 🔄 App Flow

```
Admin uploads PDF
      │
      ▼
Document created in Supabase (Storage + DB)
      │
      ▼
Signers added → unique links generated
      │
      ├─── Link sent to Signer 1 ──→ Signs ──→ Saved to DB
      ├─── Link sent to Signer 2 ──→ Signs ──→ Saved to DB
      └─── Link sent to Signer N ──→ Signs ──→ Saved to DB
                                          │
                                          ▼
                              Document status → "complete"
                              Admin downloads signed PDF
                              (all signatures embedded)
```

---

## 🔐 Security Notes

- **Signing links** contain the `signer_id` UUID — treat them as secrets
- **Row Level Security** is enabled on all tables (open for MVP; tighten for production)
- **Secrets** are stored in Streamlit Cloud's encrypted secrets manager — never in Git
- For production: add Supabase Auth so only authenticated users can upload/manage documents

---

## 🛠️ Tech Stack

| Library | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `supabase` | Python client for Supabase DB + Storage |
| `streamlit-drawable-canvas` | Freehand signature drawing |
| `pypdf` | PDF reading, page merging |
| `reportlab` | Rendering signature images onto PDF overlay |
| `pymupdf` | PDF-to-image for page previews |
| `Pillow` + `numpy` | Image processing |
