# warranty/models.py
"""
Django models for the Warranty plugin.

Contains:
- SafetyCultureRecord: a normalized row per device/unit pulled from SafetyCulture.
  Uses `unit_sn` (e.g., IG1…) as the primary key to prevent duplicates for the same unit.

Notes:
- Keep this module import-light (no requests, no plugin imports).
- Business logic that touches external APIs should live in admin.py or services modules.
"""

from django.db import models
from django.core.validators import RegexValidator


class SafetyCultureRecord(models.Model):
    # NEW: the SafetyCulture audit id (unique)
    audit_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)

    # NEW: the audit's modified timestamp from SC (UTC)
    sc_modified_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Primary key = Unit Serial Number (must start with IG1…)
    unit_sn = models.CharField(
        max_length=64,
        primary_key=True,
        validators=[RegexValidator(r"^IG1[A-Z0-9]+$", "Unit Serial Number must start with IG1")],
    )

    model_number = models.CharField(max_length=16, blank=True)

    ums_sn = models.CharField(
        max_length=9, blank=True, null=True,
        validators=[RegexValidator(r"^\d{4}-\d{4}$", "UMS SN must be in xxxx-xxxx format")],
    )

    audit_date = models.DateField()
    warranty_expiry = models.DateField(blank=True, null=True)
    tm_device_id = models.CharField(max_length=32, blank=True, null=True)
    payload = models.JSONField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        # Useful default ordering when listing in admin/UI
        ordering = ["-audit_date", "unit_sn"]
        verbose_name = "SafetyCulture Record"
        verbose_name_plural = "SafetyCulture Records"

        # Add DB indexes for common filters/sorts
        indexes = [
            models.Index(fields=["audit_date"]),
            models.Index(fields=["model_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.unit_sn} ({self.model_number})"

    # --- helpers ---------------------------------------------------------------------

    def _add_years(self, d, years: int):
        """
        Add whole years to a date while handling leap years.
        Tries dateutil.relativedelta if available, else falls back to naive replace().
        """
        try:
            from dateutil.relativedelta import relativedelta  # local import (optional dep)
            return d + relativedelta(years=years)
        except Exception:
            try:
                return d.replace(year=d.year + years)
            except ValueError:
                # Handle Feb 29 → Feb 28 for non-leap target years
                return d.replace(month=2, day=28, year=d.year + years)

    # --- persistence hooks ------------------------------------------------------------

    def save(self, *args, **kwargs):
        """
        Normalize/derive fields before persisting:
          - model_number = first 3 chars of unit_sn (uppercased)
          - warranty_expiry = audit_date + 3 years (if not already provided)
          - ums_sn digits are normalized into 'xxxx-xxxx' when possible
        """
        # Derive model_number
        if self.unit_sn:
            self.model_number = (self.unit_sn or "").upper()[:3]

        # Auto-calc warranty if audit_date present and expiry not explicitly set
        if self.audit_date and not self.warranty_expiry:
            self.warranty_expiry = self._add_years(self.audit_date, 3)

        # Normalize UMS serial into "xxxx-xxxx" if digits available
        if self.ums_sn:
            digits = "".join(ch for ch in str(self.ums_sn) if ch.isdigit())
            if len(digits) >= 8:
                self.ums_sn = f"{digits[:4]}-{digits[4:8]}"

        return super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# NOTE on `last_audit_id`:
# The line `last_audit_id = models.CharField(...)` at module level (outside of
# any model class) would *not* create a valid database field and would raise
# errors during import/migrations. If you need to persist the "last processed
# audit id" for incremental syncs, use a small state model like below.
# ─────────────────────────────────────────────────────────────────────────────

class WarrantySyncState(models.Model):
    """
    Tiny key/value row to persist incremental sync cursors (e.g., last_audit_id).

    Use a single predictable primary key (e.g., 'default') so you can:
        obj, _ = WarrantySyncState.objects.get_or_create(pk="default")
        obj.last_audit_id = "audit_123"
        obj.save()
    """

    id = models.CharField(primary_key=True, max_length=32, default="default")
    last_audit_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="Cursor of the last processed SafetyCulture audit_id for incremental sync.",
    )
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Warranty Sync State"
        verbose_name_plural = "Warranty Sync State"

    def __str__(self) -> str:
        return f"WarrantySyncState(pk={self.pk}, last_audit_id={self.last_audit_id or '-'})"
