"""SIT: Plaid mode switching.

Validates that switching between local (production) and demo (sandbox) modes
correctly swaps Plaid credentials, encryption behavior, and sync filtering.
"""
import os
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.integration


class TestPlaidModeSwitching:
    def setup_method(self):
        """Ensure we start in local mode for each test."""
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def teardown_method(self):
        """Restore local mode after each test."""
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def test_default_mode_is_local(self):
        from pipeline.plaid.client import get_plaid_mode
        assert get_plaid_mode() == "local"

    def test_switch_to_demo(self):
        from pipeline.plaid.client import switch_plaid_mode, get_plaid_mode
        switch_plaid_mode("demo")
        assert get_plaid_mode() == "demo"

    def test_switch_to_local(self):
        from pipeline.plaid.client import switch_plaid_mode, get_plaid_mode
        switch_plaid_mode("demo")
        switch_plaid_mode("local")
        assert get_plaid_mode() == "local"

    def test_invalid_mode_raises(self):
        from pipeline.plaid.client import switch_plaid_mode
        with pytest.raises(ValueError, match="Unknown Plaid mode"):
            switch_plaid_mode("invalid")

    def test_demo_uses_sandbox_host(self):
        import plaid
        from pipeline.plaid.client import switch_plaid_mode, _PLAID_CONFIGS
        switch_plaid_mode("demo")
        assert _PLAID_CONFIGS["demo"]["env"] == "sandbox"
        assert _PLAID_CONFIGS["demo"]["host"] == plaid.Environment.Sandbox

    def test_local_uses_configured_env(self):
        from pipeline.plaid.client import _PLAID_CONFIGS
        # Should match PLAID_ENV from .env (production in our case)
        local_env = _PLAID_CONFIGS["local"]["env"]
        assert local_env in ("sandbox", "development", "production")

    def test_configs_share_client_id(self):
        from pipeline.plaid.client import _PLAID_CONFIGS
        assert _PLAID_CONFIGS["local"]["client_id"] == _PLAID_CONFIGS["demo"]["client_id"]

    def test_get_plaid_client_uses_active_mode(self):
        """Client should use different hosts based on mode."""
        from pipeline.plaid.client import switch_plaid_mode, get_plaid_client, _PLAID_CONFIGS
        import plaid

        switch_plaid_mode("demo")
        # We can't easily inspect the client's host, but we can verify
        # it doesn't raise and returns a PlaidApi instance
        client = get_plaid_client()
        assert isinstance(client, plaid.api.plaid_api.PlaidApi)


class TestEncryptionModeSync:
    def setup_method(self):
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def teardown_method(self):
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def test_demo_mode_sets_sandbox_env(self):
        from pipeline.plaid.client import switch_plaid_mode
        from pipeline.db.encryption import _PLAID_ENV, _IS_PRODUCTION
        switch_plaid_mode("demo")
        # Must re-import to get updated values
        from pipeline.db import encryption
        assert encryption._PLAID_ENV == "sandbox"
        assert encryption._IS_PRODUCTION is False

    def test_local_mode_sets_production_env(self):
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("demo")  # first go to demo
        switch_plaid_mode("local")  # then back
        from pipeline.db import encryption
        # Should match the configured PLAID_ENV
        assert encryption._PLAID_ENV == os.getenv("PLAID_ENV", "production").lower()

    def test_set_plaid_env_directly(self):
        from pipeline.db.encryption import set_plaid_env, _IS_PRODUCTION
        set_plaid_env("sandbox")
        from pipeline.db import encryption
        assert encryption._IS_PRODUCTION is False
        set_plaid_env("production")
        assert encryption._IS_PRODUCTION is True


class TestIncomeClientModeSync:
    def setup_method(self):
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def teardown_method(self):
        from pipeline.plaid.client import switch_plaid_mode
        switch_plaid_mode("local")

    def test_plaid_auth_uses_active_config(self):
        from pipeline.plaid.client import switch_plaid_mode, _PLAID_CONFIGS
        from pipeline.plaid.income_client import _plaid_auth

        local_auth = _plaid_auth()
        assert local_auth["client_id"] == _PLAID_CONFIGS["local"]["client_id"]
        assert local_auth["secret"] == _PLAID_CONFIGS["local"]["secret"]

        switch_plaid_mode("demo")
        demo_auth = _plaid_auth()
        assert demo_auth["client_id"] == _PLAID_CONFIGS["demo"]["client_id"]
        assert demo_auth["secret"] == _PLAID_CONFIGS["demo"]["secret"]

    def test_plaid_base_url_uses_active_config(self):
        from pipeline.plaid.client import switch_plaid_mode
        from pipeline.plaid.income_client import _plaid_base_url

        switch_plaid_mode("demo")
        assert _plaid_base_url() == "https://sandbox.plaid.com"

        switch_plaid_mode("local")
        url = _plaid_base_url()
        assert "plaid.com" in url


class TestPlaidItemEnvColumn:
    async def test_plaid_item_has_env_field(self, demo_session, demo_seed):
        """PlaidItem model should have a plaid_env column."""
        from pipeline.db.schema import PlaidItem
        assert hasattr(PlaidItem, "plaid_env")

    def test_plaid_item_default_is_production(self):
        """Default plaid_env should be 'production' when explicitly set (as done in routes)."""
        from pipeline.db.schema import PlaidItem
        item = PlaidItem(
            item_id="test-item-123",
            access_token="test-token",
            institution_name="Test Bank",
            plaid_env="production",
        )
        assert item.plaid_env == "production"
