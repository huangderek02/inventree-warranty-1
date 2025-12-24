# warranty/core.py
"""
Core plugin class for the Warranty plugin.

Keep this module lightweight:
- Import heavy modules (e.g., requests, models) only inside functions/methods.
- Define user-visible plugin metadata and DB-backed settings here.
- (Optionally) register scheduled tasks which run via the InvenTree worker.
"""

from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, SettingsMixin
from django.utils.translation import gettext_lazy as _


class Warranty(AppMixin, SettingsMixin, InvenTreePlugin):
    """
    Warranty plugin integrating SafetyCulture audits into InvenTree.

    Responsibilities:
      - Expose plugin identity (TITLE/NAME/SLUG/VERSION)
      - Declare DB-persisted SETTINGS editable in the InvenTree UI
      - (Optional) define SCHEDULED_TASKS which call into the sync function
    """

    # --- Identity (shown in the UI / registry) ----------------------------------------
    TITLE = "Warranty"
    NAME = "warranty"   # Must match the identifier you enable in config.yaml / UI
    SLUG = "warranty"
    PLUGIN_VERSION = "0.2.0"

    __all__ = ["PLUGIN_VERSION"]

    # If you do not ship a custom admin frontend (Settings.js), keep this as None
    ADMIN_SOURCE = None

    # --- Plugin settings (stored in InvenTree DB; editable via UI) --------------------
    # Keep keys stable; changing keys will drop existing values in production.
    SETTINGS = {
        "SC_API_TOKEN": {
            "name": _("SafetyCulture API Token"),
            "description": _("Bearer token used for SafetyCulture API calls"),
            "validator": str,
            "default": "",
            "secret": True,  # hides value in UI and export
        },
        "SC_TEMPLATE_ID": {
            "name": _("Template ID"),
            "description": _("e.g. template_60dc405af153456289d32d0abb62f3a4"),
            "validator": str,
            "default": "",
        },
        "SC_BASE_URL": {
            "name": _("API Base URL"),
            "description": _("Usually https://api.safetyculture.io"),
            "validator": str,
            "default": "https://api.safetyculture.io",
        },
        # Label overrides so this plugin can adapt to differently-named fields
        "LABEL_AUDIT_DATE": {
            "name": _("Label: Audit Date"),
            "description": _("Label in the audit that holds the completed date"),
            "validator": str,
            "default": "Conducted on",
        },
        "LABEL_UMS_SN": {
            "name": _("Label: UMS SN"),
            "description": _("Label that contains the UMS serial (e.g. 'UMS QR Code')"),
            "validator": str,
            "default": "UMS QR Code",
        },
        "LABEL_TM_ID": {
            "name": _("Label: TM Device ID"),
            "description": _("Label for TM/Unit QR Code"),
            "validator": str,
            "default": "Unit QR Code",
        },
        "LABEL_UNIT_SN": {
            "name": _("Label: Unit Serial Number"),
            "description": _("Exact label in your audit for the primary unit serial"),
            "validator": str,
            "default": "Unit Serial Number",
        },
        # Serial→(model slice length, warranty years) rules in compact JSON form
        "SERIAL_PREFIX_RULES": {
            "name": _("Serial Rules (JSON)"),
            "description": _('Example: {"IG": {"length": 3, "warranty": 3}}'),
            "validator": str,
            "default": '{"IG": {"length": 3, "warranty": 3}}',
        },

        "SC_SYNC_CURSOR": {  # ISO-8601 string of last modified_at processed
            "name": _("Sync Cursor (modified_after)"),
            "description": _("Internal – last processed SafetyCulture modified_at"),
            "validator": str,
            "default": "",
        },
        "SC_SYNC_MODE": {
            "name": _("Sync Mode"),
            "description": _("incremental|full"),
            "validator": str,
            "default": "incremental",
        },
    }

    # --- Optional: background sync (requires inventree-worker running) ----------------
    # The worker loads the plugin and calls this function on the specified cadence.
    SCHEDULED_TASKS = {
        "warranty-sync-daily": {
            "func": "scheduled_sync_from_sc",
            "schedule": "I",
            "minutes": 1440,  # 24h
        },
    }

    def scheduled_sync_from_sc(self):
        """Daily worker job."""
        from . import admin as warranty_admin
        res = warranty_admin.run_sc_sync(incremental=True, print_each=False)
        __import__("logging").getLogger(__name__).info("Daily SC sync: %s", res)
