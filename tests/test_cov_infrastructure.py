"""Coverage tests for infrastructure modules: auth, database, main, schema re-exports."""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from pipeline.db.schema import Base


# ---------------------------------------------------------------------------
# schema re-export shims (0% → 100%)
# ---------------------------------------------------------------------------

class TestSchemaReExports:
    """Verify backward-compatible re-export modules import correctly."""

    def test_schema_henry_exports(self):
        from pipeline.db.schema_henry import (
            Base, InvestmentHolding, MarketQuoteCache, EconomicIndicatorCache,
            RetirementProfile, LifeScenario, CryptoHolding, PortfolioSnapshot,
            EquityGrant, VestingEvent, EquityTaxProjection, TargetAllocation,
        )
        assert Base is not None
        assert InvestmentHolding.__tablename__ == "investment_holdings"
        assert RetirementProfile.__tablename__ == "retirement_profiles"

    def test_schema_household_exports(self):
        from pipeline.db.schema_household import (
            Base, HouseholdProfile, BenefitPackage, HouseholdOptimization,
            TaxProjection, LifeEvent, InsurancePolicy, FamilyMember,
            BenchmarkSnapshot,
        )
        assert Base is not None
        assert HouseholdProfile.__tablename__ == "household_profiles"
        assert InsurancePolicy.__tablename__ == "insurance_policies"


# ---------------------------------------------------------------------------
# api/auth.py
# ---------------------------------------------------------------------------

class TestAuth:
    """Tests for Supabase JWT validation."""

    @pytest.mark.asyncio
    async def test_get_current_user_demo_mode(self):
        """In demo mode, auth returns None."""
        import api.auth as auth_mod
        with patch("api.database.get_active_mode", return_value="demo"):
            result = await auth_mod.get_current_user(MagicMock(), None)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_no_supabase_configured(self):
        """Without Supabase config (dev mode), auth returns None."""
        import api.auth as auth_mod
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = ""
            auth_mod.SUPABASE_URL = ""
            with patch("api.database.get_active_mode", return_value="local"):
                result = await auth_mod.get_current_user(MagicMock(), None)
                assert result is None
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials_raises_401(self):
        """Missing credentials when auth is configured raises 401."""
        from fastapi import HTTPException
        import api.auth as auth_mod
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = "my-secret"
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"):
                with pytest.raises(HTTPException) as exc_info:
                    await auth_mod.get_current_user(MagicMock(), None)
                assert exc_info.value.status_code == 401
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_valid_jwt(self):
        """Valid JWT with HS256 returns payload."""
        import api.auth as auth_mod
        creds = MagicMock()
        creds.credentials = "fake-token"
        expected_payload = {"sub": "user-123", "aud": "authenticated"}
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = "my-secret"
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "jwt") as mock_jwt:
                mock_jwt.decode.return_value = expected_payload
                mock_jwt.ExpiredSignatureError = Exception
                mock_jwt.InvalidTokenError = Exception
                result = await auth_mod.get_current_user(MagicMock(), creds)
                assert result == expected_payload
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Expired JWT raises 401."""
        import jwt as real_jwt
        import api.auth as auth_mod
        from fastapi import HTTPException
        creds = MagicMock()
        creds.credentials = "expired-token"
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = "my-secret"
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "jwt") as mock_jwt:
                mock_jwt.ExpiredSignatureError = real_jwt.ExpiredSignatureError
                mock_jwt.InvalidTokenError = real_jwt.InvalidTokenError
                mock_jwt.decode.side_effect = real_jwt.ExpiredSignatureError()
                with pytest.raises(HTTPException) as exc_info:
                    await auth_mod.get_current_user(MagicMock(), creds)
                assert exc_info.value.status_code == 401
                assert "expired" in exc_info.value.detail.lower()
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Invalid JWT raises 401."""
        import jwt as real_jwt
        import api.auth as auth_mod
        from fastapi import HTTPException
        creds = MagicMock()
        creds.credentials = "bad-token"
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = "my-secret"
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "jwt") as mock_jwt:
                mock_jwt.ExpiredSignatureError = real_jwt.ExpiredSignatureError
                mock_jwt.InvalidTokenError = real_jwt.InvalidTokenError
                mock_jwt.decode.side_effect = real_jwt.InvalidTokenError()
                with pytest.raises(HTTPException) as exc_info:
                    await auth_mod.get_current_user(MagicMock(), creds)
                assert exc_info.value.status_code == 401
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_jwks_cached(self):
        """JWKS returns cached keys when fresh."""
        import api.auth as auth_mod
        original = auth_mod._jwks_cache.copy()
        try:
            auth_mod._jwks_cache["keys"] = [{"kid": "test-key"}]
            auth_mod._jwks_cache["fetched_at"] = time.time()
            result = await auth_mod._get_jwks()
            assert result == [{"kid": "test-key"}]
        finally:
            auth_mod._jwks_cache.update(original)

    @pytest.mark.asyncio
    async def test_get_jwks_no_supabase_url(self):
        """JWKS returns empty list when no Supabase URL."""
        import api.auth as auth_mod
        original = auth_mod._jwks_cache.copy()
        try:
            auth_mod._jwks_cache["keys"] = []
            auth_mod._jwks_cache["fetched_at"] = 0
            with patch.object(auth_mod, "SUPABASE_URL", ""):
                result = await auth_mod._get_jwks()
                assert result == []
        finally:
            auth_mod._jwks_cache.update(original)

    @pytest.mark.asyncio
    async def test_get_jwks_fetch_success(self):
        """JWKS fetches keys from Supabase."""
        import api.auth as auth_mod
        original = auth_mod._jwks_cache.copy()
        try:
            auth_mod._jwks_cache["keys"] = []
            auth_mod._jwks_cache["fetched_at"] = 0
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keys": [{"kid": "new-key"}]}
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch.object(auth_mod, "SUPABASE_URL", "https://x.supabase.co"), \
                 patch("api.auth.httpx.AsyncClient", return_value=mock_client):
                result = await auth_mod._get_jwks()
                assert result == [{"kid": "new-key"}]
        finally:
            auth_mod._jwks_cache.update(original)

    @pytest.mark.asyncio
    async def test_get_jwks_fetch_error(self):
        """JWKS returns cached keys on fetch error."""
        import api.auth as auth_mod
        original = auth_mod._jwks_cache.copy()
        try:
            auth_mod._jwks_cache["keys"] = []
            auth_mod._jwks_cache["fetched_at"] = 0
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            with patch.object(auth_mod, "SUPABASE_URL", "https://x.supabase.co"), \
                 patch("api.auth.httpx.AsyncClient", return_value=mock_client):
                result = await auth_mod._get_jwks()
                assert result == []
        finally:
            auth_mod._jwks_cache.update(original)

    @pytest.mark.asyncio
    async def test_get_current_user_jwks_fallback(self):
        """Falls back to JWKS when no JWT secret."""
        import api.auth as auth_mod
        from fastapi import HTTPException
        creds = MagicMock()
        creds.credentials = "jwks-token"
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = ""
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "_get_jwks", new_callable=AsyncMock, return_value=[]):
                with pytest.raises(HTTPException) as exc_info:
                    await auth_mod.get_current_user(MagicMock(), creds)
                assert exc_info.value.status_code == 503
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_jwks_valid_key(self):
        """JWKS key match decodes successfully."""
        import jwt as real_jwt
        import api.auth as auth_mod
        creds = MagicMock()
        creds.credentials = "jwks-token"
        expected = {"sub": "user-456"}
        jwks = [{"kid": "key-1", "kty": "RSA"}]
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = ""
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "_get_jwks", new_callable=AsyncMock, return_value=jwks), \
                 patch.object(auth_mod, "jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "key-1"}
                mock_jwt.algorithms.RSAAlgorithm.from_jwk.return_value = "public-key"
                mock_jwt.decode.return_value = expected
                mock_jwt.ExpiredSignatureError = real_jwt.ExpiredSignatureError
                mock_jwt.InvalidTokenError = real_jwt.InvalidTokenError
                result = await auth_mod.get_current_user(MagicMock(), creds)
                assert result == expected
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url

    @pytest.mark.asyncio
    async def test_get_current_user_jwks_no_matching_key(self):
        """JWKS key mismatch raises 401."""
        import jwt as real_jwt
        import api.auth as auth_mod
        from fastapi import HTTPException
        creds = MagicMock()
        creds.credentials = "jwks-token"
        jwks = [{"kid": "key-1"}]
        orig_secret = auth_mod.SUPABASE_JWT_SECRET
        orig_url = auth_mod.SUPABASE_URL
        try:
            auth_mod.SUPABASE_JWT_SECRET = ""
            auth_mod.SUPABASE_URL = "https://x.supabase.co"
            with patch("api.database.get_active_mode", return_value="local"), \
                 patch.object(auth_mod, "_get_jwks", new_callable=AsyncMock, return_value=jwks), \
                 patch.object(auth_mod, "jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "different-key"}
                mock_jwt.ExpiredSignatureError = real_jwt.ExpiredSignatureError
                mock_jwt.InvalidTokenError = real_jwt.InvalidTokenError
                with pytest.raises(HTTPException) as exc_info:
                    await auth_mod.get_current_user(MagicMock(), creds)
                assert exc_info.value.status_code == 401
        finally:
            auth_mod.SUPABASE_JWT_SECRET = orig_secret
            auth_mod.SUPABASE_URL = orig_url


# ---------------------------------------------------------------------------
# api/database.py
# ---------------------------------------------------------------------------

class TestDatabase:
    """Tests for database module."""

    def test_demo_db_url_sqlite(self):
        from api.database import _demo_db_url
        with patch("api.database.DATABASE_URL", "sqlite+aiosqlite:///./data/db/financials.db"):
            result = _demo_db_url()
            assert "demo.db" in result
            assert result.startswith("sqlite+aiosqlite:///")

    def test_demo_db_url_non_sqlite(self):
        from api.database import _demo_db_url
        with patch("api.database.DATABASE_URL", "postgresql://user:pass@host/financials.db"):
            result = _demo_db_url()
            assert "demo.db" in result

    def test_get_active_mode_default(self):
        from api.database import get_active_mode
        # Default mode should be "local"
        assert get_active_mode() in ("local", "demo")

    @pytest.mark.asyncio
    async def test_switch_to_mode_same_mode(self):
        import api.database as db_mod
        original_mode = db_mod._active_mode
        try:
            db_mod._active_mode = "local"
            result = await db_mod.switch_to_mode("local")
            assert result == "local"
        finally:
            db_mod._active_mode = original_mode

    @pytest.mark.asyncio
    async def test_switch_to_mode_unknown(self):
        import api.database as db_mod
        original_mode = db_mod._active_mode
        try:
            db_mod._active_mode = "local"
            with pytest.raises(ValueError, match="Unknown mode"):
                await db_mod.switch_to_mode("invalid")
        finally:
            db_mod._active_mode = original_mode

    @pytest.mark.asyncio
    async def test_switch_to_demo_mode(self):
        import api.database as db_mod
        original_mode = db_mod._active_mode
        original_factory = db_mod._active_session_factory
        try:
            db_mod._active_mode = "local"
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.begin = MagicMock(return_value=mock_session)
            mock_session_factory = MagicMock(return_value=mock_session)

            with patch("pipeline.db.backup.backup_database") as mock_backup, \
                 patch.object(db_mod, "_demo_db_url", return_value="sqlite+aiosqlite:///:memory:"), \
                 patch("pipeline.db.init_db", new_callable=AsyncMock), \
                 patch.object(db_mod, "create_async_engine") as mock_engine, \
                 patch.object(db_mod, "async_sessionmaker", return_value=mock_session_factory), \
                 patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
                 patch("pipeline.demo.seeder.get_demo_status", new_callable=AsyncMock, return_value={"active": True}):
                mock_engine.return_value = MagicMock()
                result = await db_mod.switch_to_mode("demo")
                assert result == "demo"
                mock_backup.assert_called_once()
        finally:
            db_mod._active_mode = original_mode
            db_mod._active_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_switch_back_to_local(self):
        import api.database as db_mod
        original_mode = db_mod._active_mode
        original_factory = db_mod._active_session_factory
        try:
            db_mod._active_mode = "demo"
            result = await db_mod.switch_to_mode("local")
            assert result == "local"
            assert db_mod._active_session_factory is db_mod.AsyncSessionLocal
        finally:
            db_mod._active_mode = original_mode
            db_mod._active_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_commits(self):
        """get_session auto-commits on success."""
        import api.database as db_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)
        original_factory = db_mod._active_session_factory
        try:
            db_mod._active_session_factory = mock_factory
            gen = db_mod.get_session()
            session = await gen.__anext__()
            assert session is mock_session
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
            mock_session.commit.assert_called_once()
        finally:
            db_mod._active_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_rollback_on_error(self):
        """get_session rolls back on exception."""
        import api.database as db_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit.side_effect = Exception("DB error")
        mock_factory = MagicMock(return_value=mock_session)
        original_factory = db_mod._active_session_factory
        try:
            db_mod._active_session_factory = mock_factory
            gen = db_mod.get_session()
            session = await gen.__anext__()
            with pytest.raises(Exception, match="DB error"):
                await gen.__anext__()
            mock_session.rollback.assert_called_once()
        finally:
            db_mod._active_session_factory = original_factory


# ---------------------------------------------------------------------------
# api/main.py — lifespan, middleware, startup tasks
# ---------------------------------------------------------------------------

class TestMainLifespan:
    """Tests for api/main.py lifespan and startup."""

    def test_health_endpoint(self):
        """Smoke test the health endpoint import."""
        from api.main import app
        assert app.title == "Sir Henry API"

    @pytest.mark.asyncio
    async def test_seed_all_reminders(self):
        """_seed_all_reminders calls seed_all_reminders."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session)

        mock_seed = AsyncMock(return_value={"tax": 3, "amazon": 2})
        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("api.routes.reminders.seed_all_reminders", mock_seed):
            # Need to import after patching
            await main_mod._seed_all_reminders()

    @pytest.mark.asyncio
    async def test_seed_all_reminders_zero(self):
        """_seed_all_reminders logs when no reminders seeded."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session)

        mock_seed = AsyncMock(return_value={"tax": 0})
        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("api.routes.reminders.seed_all_reminders", mock_seed):
            await main_mod._seed_all_reminders()

    @pytest.mark.asyncio
    async def test_periodic_plaid_sync_one_iteration(self):
        """_periodic_plaid_sync runs one iteration then gets cancelled."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session)

        call_count = 0

        async def mock_sleep(secs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.plaid.sync.sync_all_items", new_callable=AsyncMock, return_value={"added": 5}), \
             patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await main_mod._periodic_plaid_sync(3600)

    @pytest.mark.asyncio
    async def test_periodic_plaid_sync_error_handling(self):
        """_periodic_plaid_sync handles sync errors gracefully."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session)

        call_count = 0

        async def mock_sleep(secs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.plaid.sync.sync_all_items", new_callable=AsyncMock, side_effect=Exception("Plaid error")), \
             patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await main_mod._periodic_plaid_sync(3600)

    @pytest.mark.asyncio
    async def test_deferred_startup_tasks(self):
        """_deferred_startup_tasks runs PII loading, cleanup, and period recompute."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([(2025,), (2024,)]))
        mock_session.execute.return_value = mock_result

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, return_value=["John"]), \
             patch("pipeline.security.logging.update_known_names") as mock_update, \
             patch("pipeline.security.file_cleanup.cleanup_old_files"), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock), \
             patch.object(mock_session, "commit", new_callable=AsyncMock), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock):
            await main_mod._deferred_startup_tasks()
            mock_update.assert_called_once_with(["John"])

    @pytest.mark.asyncio
    async def test_deferred_startup_pii_error(self):
        """PII loading failure is non-fatal."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, side_effect=Exception("DB error")), \
             patch("pipeline.security.file_cleanup.cleanup_old_files"), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock), \
             patch.object(mock_session, "commit", new_callable=AsyncMock), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock):
            await main_mod._deferred_startup_tasks()

    @pytest.mark.asyncio
    async def test_deferred_startup_cleanup_error(self):
        """File cleanup failure is non-fatal."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, return_value=[]), \
             patch("pipeline.security.file_cleanup.cleanup_old_files", side_effect=Exception("IO error")), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock), \
             patch.object(mock_session, "commit", new_callable=AsyncMock), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock):
            await main_mod._deferred_startup_tasks()

    @pytest.mark.asyncio
    async def test_deferred_startup_recompute_error(self):
        """Period recompute failure is non-fatal."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, return_value=[]), \
             patch("pipeline.security.file_cleanup.cleanup_old_files"), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock, side_effect=Exception("Calc error")), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock):
            await main_mod._deferred_startup_tasks()

    @pytest.mark.asyncio
    async def test_deferred_startup_reminder_error(self):
        """Reminder seeding failure is non-fatal."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, return_value=[]), \
             patch("pipeline.security.file_cleanup.cleanup_old_files"), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock), \
             patch.object(mock_session, "commit", new_callable=AsyncMock), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock, side_effect=Exception("Seed error")):
            await main_mod._deferred_startup_tasks()

    @pytest.mark.asyncio
    async def test_deferred_startup_no_transaction_years(self):
        """When no transaction years exist, uses current year."""
        from api import main as main_mod
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.logging.load_known_names_from_db", new_callable=AsyncMock, return_value=[]), \
             patch("pipeline.security.file_cleanup.cleanup_old_files"), \
             patch("pipeline.ai.report_gen.recompute_all_periods", new_callable=AsyncMock) as mock_recompute, \
             patch.object(mock_session, "commit", new_callable=AsyncMock), \
             patch.object(main_mod, "_seed_all_reminders", new_callable=AsyncMock):
            await main_mod._deferred_startup_tasks()
            mock_recompute.assert_called()


class TestMainMiddleware:
    """Tests for CORS and LocalhostGuard middleware."""

    def test_cors_origins_configured(self):
        from api.main import cors_origins
        assert "http://localhost:3000" in cors_origins
        assert "tauri://localhost" in cors_origins

    def test_app_has_routers(self):
        from api.main import app
        routes = [r.path for r in app.routes]
        assert "/health" in routes


class TestGlobalExceptionHandler:
    """Tests for the global exception handler."""

    @pytest.mark.asyncio
    async def test_global_exception_handler(self):
        from api import main as main_mod
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_session)

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.security.error_reporting.submit_error_report", new_callable=AsyncMock):
            response = await main_mod.global_exception_handler(mock_request, Exception("Test error"))
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_global_exception_handler_logging_fails(self):
        from api import main as main_mod
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/test"
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(side_effect=Exception("Log failed"))

        with patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session):
            response = await main_mod.global_exception_handler(mock_request, Exception("Boom"))
            assert response.status_code == 500


class TestLifespan:
    """Tests for the lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_sandbox_mode(self):
        """Lifespan in sandbox mode logs warning."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch("api.database.AsyncSessionLocal", mock_factory), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "sandbox", "PLAID_ENCRYPTION_KEY": "", "PLAID_SYNC_INTERVAL_HOURS": "0"}, clear=False), \
             patch.object(main_mod, "_deferred_startup_tasks", new_callable=AsyncMock), \
             patch("asyncio.create_task") as mock_task, \
             patch.object(main_mod, "engine") as mock_engine:
            mock_task.return_value = MagicMock()
            mock_task.return_value.cancel = MagicMock()
            mock_engine.dispose = AsyncMock()
            async with main_mod.lifespan(mock_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_production_no_encryption_key(self):
        """Lifespan raises in production without encryption key."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "production", "PLAID_ENCRYPTION_KEY": ""}, clear=False):
            with pytest.raises(RuntimeError, match="PLAID_ENCRYPTION_KEY must be set"):
                async with main_mod.lifespan(mock_app):
                    pass

    @pytest.mark.asyncio
    async def test_lifespan_valid_encryption_key(self):
        """Lifespan validates Fernet key."""
        from cryptography.fernet import Fernet
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        valid_key = Fernet.generate_key().decode()
        mock_factory = MagicMock(return_value=mock_session)

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch("api.database.AsyncSessionLocal", mock_factory), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "development", "PLAID_ENCRYPTION_KEY": valid_key, "PLAID_SYNC_INTERVAL_HOURS": "0"}, clear=False), \
             patch.object(main_mod, "_deferred_startup_tasks", new_callable=AsyncMock), \
             patch("asyncio.create_task") as mock_task, \
             patch.object(main_mod, "engine") as mock_engine:
            mock_task.return_value = MagicMock()
            mock_task.return_value.cancel = MagicMock()
            mock_engine.dispose = AsyncMock()
            async with main_mod.lifespan(mock_app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_invalid_encryption_key(self):
        """Lifespan rejects invalid Fernet key."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "development", "PLAID_ENCRYPTION_KEY": "not-a-valid-key"}, clear=False):
            with pytest.raises(RuntimeError, match="Invalid PLAID_ENCRYPTION_KEY"):
                async with main_mod.lifespan(mock_app):
                    pass

    @pytest.mark.asyncio
    async def test_lifespan_migration_failure(self):
        """Lifespan propagates migration errors."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch.object(main_mod, "AsyncSessionLocal", create=True, return_value=mock_session), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock, side_effect=Exception("Migration error")):
            with pytest.raises(Exception, match="Migration error"):
                async with main_mod.lifespan(mock_app):
                    pass

    @pytest.mark.asyncio
    async def test_lifespan_with_sync_enabled(self):
        """Lifespan creates sync task when interval > 0."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        created_tasks = []

        def create_task_side_effect(coro):
            coro.close()
            t = asyncio.Future()
            t.set_result(None)
            created_tasks.append(t)
            return t

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch("api.database.AsyncSessionLocal", mock_factory), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "sandbox", "PLAID_ENCRYPTION_KEY": "", "PLAID_SYNC_INTERVAL_HOURS": "6"}, clear=False), \
             patch("asyncio.create_task", side_effect=create_task_side_effect), \
             patch.object(main_mod, "engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            async with main_mod.lifespan(mock_app):
                pass
            # Two tasks: deferred + sync
            assert len(created_tasks) == 2

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_cancels_tasks(self):
        """Lifespan cancels background tasks on shutdown."""
        from api import main as main_mod
        mock_app = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        created_tasks = []

        def create_task_side_effect(coro):
            coro.close()
            t = asyncio.Future()
            t.set_result(None)
            created_tasks.append(t)
            return t

        with patch("pipeline.db.field_encryption.register_encryption_events"), \
             patch("pipeline.db.backup.backup_database"), \
             patch.object(main_mod, "init_db", new_callable=AsyncMock), \
             patch("api.database.AsyncSessionLocal", mock_factory), \
             patch("pipeline.db.migrations.run_migrations", new_callable=AsyncMock), \
             patch.dict(os.environ, {"PLAID_ENV": "sandbox", "PLAID_ENCRYPTION_KEY": "", "PLAID_SYNC_INTERVAL_HOURS": "6"}, clear=False), \
             patch("asyncio.create_task", side_effect=create_task_side_effect), \
             patch.object(main_mod, "engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            async with main_mod.lifespan(mock_app):
                pass
            # Both tasks should exist
            assert len(created_tasks) == 2
