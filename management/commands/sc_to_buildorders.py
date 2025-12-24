from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction

from warranty.models import SafetyCultureRecord


def get_model(app_label, *names):
    for n in names:
        try:
            return apps.get_model(app_label, n)
        except Exception:
            pass
    raise RuntimeError(f"Could not find model in {app_label}: tried {names}")


def has_field(Model, name: str) -> bool:
    return any(f.name == name for f in Model._meta.fields)


class Command(BaseCommand):
    help = "Create/Update Manufacturing Build Orders from Warranty SafetyCultureRecord rows (reference-safe)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit number of records processed (0 = all)")
        parser.add_argument("--dry-run", action="store_true", help="Do not write anything")
        parser.add_argument("--category", default="SafetyCulture Units", help="Part category name to use/create")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"]
        cat_name = opts["category"]

        PartCategory = get_model("part", "PartCategory")
        Part = get_model("part", "Part")
        Build = get_model("build", "Build", "BuildOrder")

        # Common build fields
        part_field = "part"
        qty_field = "quantity" if has_field(Build, "quantity") else "quantity"
        title_field = "title" if has_field(Build, "title") else None
        notes_field = "notes" if has_field(Build, "notes") else ("description" if has_field(Build, "description") else None)

        qs = SafetyCultureRecord.objects.order_by("unit_sn")
        if limit and limit > 0:
            qs = qs[:limit]

        created_parts = 0
        created_builds = 0
        updated_builds = 0
        skipped = 0

        cat, _ = PartCategory.objects.get_or_create(name=cat_name)

        part_cache = {}

        def get_or_make_part(model_number: str):
            nonlocal created_parts
            key = (model_number or "").strip().upper() or "UNKNOWN"
            if key in part_cache:
                return part_cache[key]

            # Prefer IPN match if present
            p = None
            if has_field(Part, "IPN"):
                p = Part.objects.filter(IPN=key).first()

            if not p:
                p = Part.objects.filter(name__iexact=f"Unit {key}").first()

            if not p:
                if dry:
                    part_cache[key] = None
                    return None
                fields = {
                    "name": f"Unit {key}",
                    "category": cat,
                    "description": "Auto-created from SafetyCulture warranty sync",
                }
                if has_field(Part, "IPN"):
                    fields["IPN"] = key
                p = Part.objects.create(**fields)
                created_parts += 1

            part_cache[key] = p
            return p

        def marker(unit_sn: str) -> str:
            return f"SC_UNIT_SN={unit_sn}"

        for r in qs:
            unit_sn = (r.unit_sn or "").strip().upper()
            if not unit_sn:
                skipped += 1
                continue

            p = get_or_make_part(r.model_number)
            if dry and p is None:
                skipped += 1
                continue

            # Find existing build order for this unit
            existing = None
            if title_field:
                existing = Build.objects.filter(**{title_field: unit_sn}).first()
            elif notes_field:
                existing = Build.objects.filter(**{f"{notes_field}__contains": marker(unit_sn)}).first()

            # Compose notes/description (helps traceability)
            note = f"{marker(unit_sn)} | audit_id={r.audit_id} | audit_date={r.audit_date} | warranty_expiry={r.warranty_expiry}"

            with transaction.atomic():
                if existing:
                    if dry:
                        updated_builds += 1
                        continue

                    changed = False
                    if getattr(existing, part_field, None) != p:
                        setattr(existing, part_field, p)
                        changed = True
                    if has_field(Build, qty_field) and getattr(existing, qty_field) != 1:
                        setattr(existing, qty_field, 1)
                        changed = True
                    if title_field and getattr(existing, title_field, "") != unit_sn:
                        setattr(existing, title_field, unit_sn)
                        changed = True
                    if notes_field:
                        cur = getattr(existing, notes_field) or ""
                        if marker(unit_sn) not in cur:
                            setattr(existing, notes_field, note)
                            changed = True
                        elif cur != note:
                            setattr(existing, notes_field, note)
                            changed = True

                    if changed:
                        existing.save()
                    updated_builds += 1

                else:
                    if dry:
                        created_builds += 1
                        continue

                    fields = {
                        part_field: p,
                        qty_field: 1,
                    }

                    # IMPORTANT: Do NOT set reference. InvenTree will auto-generate BO-####.
                    if title_field:
                        fields[title_field] = unit_sn
                    if notes_field:
                        fields[notes_field] = note

                    Build.objects.create(**fields)
                    created_builds += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. parts_created={created_parts} builds_created={created_builds} builds_updated={updated_builds} skipped={skipped} dry_run={dry}"
        ))
