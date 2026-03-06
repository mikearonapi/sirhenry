# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for bundling the SirHENRY FastAPI server as a Tauri sidecar.
Build with: pyinstaller sidecar/sirhenry-api.spec --distpath src-tauri/binaries --clean --noconfirm
"""
import os
import platform

block_cipher = None
project_root = os.path.dirname(os.path.dirname(os.path.abspath(SPECPATH)))

# Platform-specific sidecar name (Tauri expects architecture suffix)
arch = platform.machine()
if arch == "arm64":
    target_triple = "aarch64-apple-darwin"
elif arch == "x86_64" and platform.system() == "Darwin":
    target_triple = "x86_64-apple-darwin"
elif arch == "AMD64" or (arch == "x86_64" and platform.system() == "Windows"):
    target_triple = "x86_64-pc-windows-msvc"
else:
    target_triple = f"{arch}-unknown-{platform.system().lower()}"

a = Analysis(
    [os.path.join(project_root, "sidecar", "sidecar_entry.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "api"), "api"),
        (os.path.join(project_root, "pipeline"), "pipeline"),
    ],
    hiddenimports=[
        # --- Uvicorn internals ---
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # --- SQLAlchemy + async ---
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "aiosqlite",
        # --- Core deps ---
        "cryptography",
        "cryptography.fernet",
        "anthropic",
        "plaid",
        "yfinance",
        "pdfplumber",
        "pymupdf",
        "fitz",
        "pandas",
        "openpyxl",
        "httpx",
        "python_dotenv",
        "dotenv",
        "h11",
        "anyio",
        "sniffio",
        "starlette",
        "pydantic",
        # --- API routes ---
        "api.routes.account_links",
        "api.routes.accounts",
        "api.routes.assets",
        "api.routes.benchmarks",
        "api.routes.budget",
        "api.routes.budget_forecast",
        "api.routes.chat",
        "api.routes.documents",
        "api.routes.entities",
        "api.routes.equity_comp",
        "api.routes.family_members",
        "api.routes.goal_suggestions",
        "api.routes.goals",
        "api.routes.household",
        "api.routes.household_optimization",
        "api.routes.import_routes",
        "api.routes.income",
        "api.routes.insights",
        "api.routes.insurance",
        "api.routes.life_events",
        "api.routes.market",
        "api.routes.plaid",
        "api.routes.portfolio",
        "api.routes.portfolio_analytics",
        "api.routes.portfolio_crypto",
        "api.routes.privacy",
        "api.routes.recurring",
        "api.routes.reminders",
        "api.routes.reminders_seed",
        "api.routes.reports",
        "api.routes.retirement",
        "api.routes.retirement_scenarios",
        "api.routes.rules",
        "api.routes.scenarios",
        "api.routes.scenarios_calc",
        "api.routes.setup_status",
        "api.routes.smart_defaults",
        "api.routes.tax",
        "api.routes.tax_analysis",
        "api.routes.tax_modeling",
        "api.routes.tax_strategies",
        "api.routes.transactions",
        "api.routes.user_context",
        "api.routes.valuations",
        # --- Pipeline modules ---
        "pipeline.db",
        "pipeline.db.schema",
        "pipeline.db.schema_extended",
        "pipeline.db.schema_henry",
        "pipeline.db.schema_household",
        "pipeline.db.models",
        "pipeline.db.migrations",
        "pipeline.db.encryption",
        "pipeline.db.field_encryption",
        "pipeline.db.flow_classifier",
        "pipeline.ai",
        "pipeline.ai.chat",
        "pipeline.ai.chat_tools",
        "pipeline.ai.categorizer",
        "pipeline.ai.categories",
        "pipeline.ai.category_rules",
        "pipeline.ai.rule_generator",
        "pipeline.ai.tax_analyzer",
        "pipeline.ai.report_gen",
        "pipeline.ai.privacy",
        "pipeline.security",
        "pipeline.security.logging",
        "pipeline.security.file_cleanup",
        "pipeline.security.audit",
        "pipeline.utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook", "IPython"],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# One-dir mode: fast startup, code-signing friendly
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f"sirhenry-api-{target_triple}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="sirhenry-api",
)
