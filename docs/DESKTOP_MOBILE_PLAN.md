# SirHENRY — Desktop & Mobile Platform Plan

## Executive Summary

SirHENRY's architecture is already 80% ready for a local desktop app. The API runs locally, data lives in SQLite on the user's machine, and there's no cloud dependency beyond Plaid (bank sync) and Anthropic (AI). The key work is: wrapping it in a native shell, adding security, and building a mobile companion that lets users snap photos of documents and send them to their desktop instance.

---

## Part 1: Local Desktop App

### Architecture: Tauri (Recommended)

**Why Tauri over Electron:**
- ~10MB installer vs ~150MB+ (Electron ships all of Chromium)
- Uses the OS's native webview (WebKit on macOS, WebView2 on Windows)
- Rust backend = fast, secure, small footprint
- SQLite access is native — no Node.js overhead
- Auto-updater, system tray, and file system access built in

**How it works:**

```
┌─────────────────────────────────────────────────┐
│                  Tauri Shell                     │
│  ┌───────────────┐    ┌───────────────────────┐  │
│  │   Frontend     │    │   Sidecar: FastAPI    │  │
│  │   (Next.js     │───▶│   (Python process)    │  │
│  │    webview)    │    │   localhost:8000       │  │
│  └───────────────┘    └──────────┬────────────┘  │
│                                  │               │
│                       ┌──────────▼────────────┐  │
│                       │  ~/.sirhenry/data/     │  │
│                       │  financials.db         │  │
│                       │  imports/              │  │
│                       └───────────────────────┘  │
└─────────────────────────────────────────────────┘
```

1. **Tauri launches two things:** the webview (Next.js static export or standalone) and the FastAPI server as a sidecar process
2. **Frontend** loads from local files (no network needed for the UI itself)
3. **API** runs on `127.0.0.1:8000` — never exposed to the network
4. **Data** stays at `~/.sirhenry/data/` — the path the codebase already defaults to

### Security Model

**Layer 1: OS-Level Isolation**
- API binds to `127.0.0.1` only — already the case in our Docker config
- No ports exposed to the network by default
- SQLite file lives in the user's home directory with standard OS file permissions
- No remote access unless the user explicitly enables it

**Layer 2: Encryption at Rest**
- SQLite database encrypted with SQLCipher (transparent encryption, AES-256)
- Key derived from a user-set passphrase via PBKDF2 (or from the OS keychain)
- On macOS: store the DB encryption key in Keychain
- On Windows: store in Windows Credential Manager
- On Linux: store in libsecret / GNOME Keyring
- Plaid tokens already encrypted with Fernet — no change needed

**Layer 3: App-Level Authentication**
- Local passphrase unlock on app launch (same key that decrypts the DB)
- Optional biometric unlock on supported hardware (Touch ID, Windows Hello)
- Auto-lock after configurable idle timeout (default: 15 minutes)
- No network auth needed — this is a single-user local app

**Layer 4: Secure Communication (for mobile pairing)**
- When mobile companion connects, use mTLS or a shared secret established via QR code
- All data in transit between mobile and desktop encrypted with TLS 1.3
- Pairing is explicit and user-initiated — no auto-discovery

**Layer 5: Update Security**
- Tauri's built-in updater with code signing
- Updates served over HTTPS with signature verification
- macOS: notarized and signed with Apple Developer ID
- Windows: signed with EV code signing certificate

### Desktop Build Pipeline

```
Next.js (static export) ──▶ Tauri webview assets
FastAPI (PyInstaller)    ──▶ Tauri sidecar binary
SQLite + SQLCipher       ──▶ Bundled with sidecar
─────────────────────────────────────────────────
Output: .dmg (macOS) / .msi (Windows) / .AppImage (Linux)
```

### What Changes in the Codebase

| Area | Change | Effort |
|------|--------|--------|
| `frontend/next.config.ts` | Enable `output: "export"` for static build | Small |
| `api/main.py` | Add SQLCipher support, optional local auth | Medium |
| New: `desktop/` | Tauri project (Rust shell, config, icons) | Medium |
| New: `desktop/sidecar/` | PyInstaller spec for bundling FastAPI | Medium |
| `pipeline/db/` | SQLCipher integration in engine creation | Small |
| `frontend/lib/api-client.ts` | Detect desktop mode, use fixed localhost URL | Small |

---

## Part 2: Mobile Companion App

### Philosophy: Companion, Not Full App

The mobile app is **not** a second copy of the desktop app. It's a companion focused on **capture and quick review**:

- Snap photos of receipts, tax documents, pay stubs, insurance cards
- Quick-view dashboards and recent transactions
- Get push notifications for insights and reminders
- Review and approve AI categorizations on the go

The heavy lifting (imports, analysis, planning, chat) stays on desktop.

### Architecture Options

#### Option A: React Native (Recommended)

```
┌─────────────────────────────────────────┐
│          React Native App               │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │  Camera /    │  │  Dashboard      │   │
│  │  Document    │  │  Views          │   │
│  │  Scanner     │  │  (read-only)    │   │
│  └──────┬──────┘  └────────┬────────┘   │
│         │                  │            │
│         ▼                  ▼            │
│  ┌──────────────────────────────────┐   │
│  │       Sync Layer                  │   │
│  │  (connects to desktop API)        │   │
│  └──────────────┬───────────────────┘   │
└─────────────────┼───────────────────────┘
                  │
          LAN / Tailscale / Relay
                  │
┌─────────────────▼───────────────────────┐
│         Desktop (Tauri + FastAPI)        │
│         localhost:8000                   │
└─────────────────────────────────────────┘
```

**Why React Native:**
- Share TypeScript types and API client code with the Next.js frontend
- Expo for camera, document scanning, push notifications
- Reuse `frontend/types/` and `frontend/lib/api-*.ts` directly
- Single codebase for iOS and Android

#### Option B: Progressive Web App (Simpler, Fewer Features)

- Serve the Next.js frontend as a PWA with `next-pwa`
- Camera access via browser APIs (`getUserMedia`, `<input type="file" capture>`)
- Works on any device with a browser, no app store needed
- Limitations: no background sync, no push notifications (iOS), limited camera control

**Recommendation:** Start with PWA for v1 (fastest to ship), plan React Native for v2.

### Mobile ↔ Desktop Connection

#### How They Find Each Other

**Step 1 — Pairing (one-time setup):**
1. User opens desktop app → Settings → "Connect Mobile"
2. Desktop generates a QR code containing: `{ ip: "192.168.1.x", port: 8000, secret: "<random-32-bytes>" }`
3. User scans QR code with mobile app
4. Mobile stores the connection details in secure storage (iOS Keychain / Android Keystore)
5. Both devices now share a secret for authenticating requests

**Step 2 — Ongoing Connection:**
- **Same Wi-Fi:** Mobile connects directly to desktop's LAN IP on port 8000
- **Away from home:** Two options:
  - **Tailscale/ZeroTier** (peer-to-peer VPN) — most secure, but requires setup
  - **Relay server** (optional SirHENRY cloud relay) — E2E encrypted, we never see the data, just forward encrypted blobs between paired devices

**Step 3 — Offline Mobile Usage:**
- Mobile caches recent dashboard data in local SQLite (via Expo SQLite or WatermelonDB)
- Photos/documents queued locally when desktop is unreachable
- Auto-sync when connection is restored — queue processed in order

### Mobile Document Capture Flow

This is the killer mobile feature — snap a photo, it becomes structured financial data:

```
User snaps photo of receipt/document
         │
         ▼
┌─────────────────────────┐
│  On-Device Processing   │
│  • Edge detection       │
│  • Auto-crop            │
│  • Perspective correct  │
│  • Enhance contrast     │
│  (ML Kit / Vision API)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Classify Document Type │
│  • Receipt              │
│  • Tax document (W-2)   │
│  • Pay stub             │
│  • Insurance card       │
│  • Investment statement  │
│  (on-device ML or       │
│   quick Claude call)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Send to Desktop API    │
│  POST /import/upload    │
│  (multipart form, same  │
│   endpoint that exists) │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Desktop Pipeline       │
│  • OCR + AI extraction  │
│  • Categorization       │
│  • DB storage           │
│  • Push notification    │
│    back to mobile:      │
│    "Imported: $142.50   │
│     at Whole Foods,     │
│     categorized as      │
│     Groceries"          │
└─────────────────────────┘
```

**Key detail:** The existing `POST /import/upload` endpoint already accepts `.jpg`, `.png`, and `.pdf` up to 50MB. The mobile app just needs to POST to it. No new API endpoints required for basic document capture.

### Mobile UX Priorities

1. **Camera-first home screen** — big "Scan Document" button front and center
2. **Batch scanning** — scan multiple pages of a tax document in one session
3. **Smart preview** — after scanning, show extracted data before sending ("We found: W-2, Employer: Acme Corp, Wages: $185,000 — Send to SirHENRY?")
4. **Dashboard glance** — swipeable cards: net worth, monthly spend, budget status
5. **Notification center** — "Your credit card statement was imported", "Unusual charge: $2,400 at Best Buy", "Tax document deadline in 30 days"
6. **Quick categorize** — swipe left/right on uncategorized transactions (Tinder-style)

---

## Part 3: Cross-Platform UX Strategy

### Design Principles

1. **Desktop = Command Center.** Full analysis, planning, chat with Sir Henry, detailed views.
2. **Mobile = Quick Capture + Glance.** Scan, review, approve. In and out in 30 seconds.
3. **Same data, right interface.** Both apps show the same data but optimized for their context.
4. **Offline-capable.** Desktop always works (local DB). Mobile caches essentials.

### Shared Code Strategy

```
shared/
  types/          ← from frontend/types/ (TypeScript interfaces)
  api-client/     ← from frontend/lib/api-client.ts (fetch wrapper)
  constants/      ← brand colors, categories, formatters

frontend/         ← Next.js (desktop webview + PWA)
mobile/           ← React Native (companion app)
desktop/          ← Tauri (native shell)
```

### Responsive Breakpoints (for PWA / shared components)

| Breakpoint | Target | Layout |
|-----------|--------|--------|
| < 640px | Phone | Single column, bottom nav, camera FAB |
| 640–1024px | Tablet | Two-column, side nav collapsed |
| > 1024px | Desktop | Full sidebar, multi-panel views |

### Notification Architecture

```
Desktop (Tauri)  ──▶  OS native notifications (already supported)
Mobile (RN)      ──▶  Push notifications via:
                      • Direct: local push when on same LAN
                      • Remote: optional relay for away-from-home
                      • Scheduled: local notifications for reminders
```

---

## Part 4: Implementation Phases

### Phase 1 — Desktop App (4–6 weeks)
- [ ] Add Tauri project shell (`desktop/`)
- [ ] Bundle FastAPI as PyInstaller sidecar
- [ ] SQLCipher encryption for the database
- [ ] OS keychain integration for encryption key
- [ ] Local passphrase unlock screen
- [ ] Next.js static export for webview
- [ ] Auto-updater with code signing
- [ ] macOS .dmg and Windows .msi builds

### Phase 2 — PWA Mobile (2–3 weeks)
- [ ] Add `next-pwa` to the frontend
- [ ] Responsive layouts for phone screens
- [ ] Camera capture via `<input type="file" accept="image/*" capture>`
- [ ] Service worker for offline dashboard caching
- [ ] Install prompt / "Add to Home Screen"

### Phase 3 — Desktop-Mobile Pairing (3–4 weeks)
- [ ] QR code pairing flow in desktop settings
- [ ] Shared secret auth for mobile → desktop API calls
- [ ] CORS update to allow paired mobile origin
- [ ] LAN discovery with fallback to manual IP entry
- [ ] Connection status indicator on both platforms

### Phase 4 — React Native App (6–8 weeks)
- [ ] Expo project setup with shared types
- [ ] Document scanner (ML Kit edge detection + crop)
- [ ] Camera capture → upload to desktop API
- [ ] Dashboard glance views (net worth, budget, recent)
- [ ] Push notifications for import confirmations
- [ ] Quick-categorize swipe UI
- [ ] Offline queue with auto-sync
- [ ] App Store and Play Store submission

### Phase 5 — Advanced (Future)
- [ ] Biometric unlock (Touch ID / Face ID / Windows Hello)
- [ ] Optional cloud relay for away-from-home access
- [ ] Multi-device sync (two desktops, or desktop + NAS)
- [ ] Apple Watch / Wear OS glance widget
- [ ] Siri / Google Assistant integration ("Hey Siri, how much did I spend on groceries?")

---

## Security Summary

| Layer | Desktop | Mobile |
|-------|---------|--------|
| Data at rest | SQLCipher AES-256 | OS secure storage for credentials only; full data lives on desktop |
| Data in transit | N/A (localhost) | TLS 1.3 + shared secret from QR pairing |
| Authentication | Passphrase → OS keychain | Biometric + stored pairing secret |
| Network exposure | `127.0.0.1` only by default | LAN only; optional Tailscale or relay |
| Key storage | OS keychain (macOS/Win/Linux) | iOS Keychain / Android Keystore |
| Updates | Signed + notarized auto-updates | App store distribution |
| Plaid tokens | Fernet encrypted (existing) | N/A — Plaid only runs on desktop |

**Core principle:** Financial data never leaves the user's device unless they explicitly connect to Plaid (bank sync) or Claude (AI features). No SirHENRY cloud. No centralized database. The user owns their data, period.
