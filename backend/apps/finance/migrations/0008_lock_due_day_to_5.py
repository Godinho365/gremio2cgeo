"""Vencimento passa a ser travado: dia 5 pra todo mundo (RN pedida pelo
usuário). Recalcula due_date/status das mensalidades ainda em aberto e o
financial_status de cada perfil — mensalidades já pagas ficam como estão
(histórico não se reescreve)."""
import calendar
from datetime import date

from django.db import migrations

DEFAULT_DUE_DAY = 5
DUE_SOON_DAYS = 5
DELINQUENT_AFTER_DAYS = 15
OPEN_STATUSES = ("pending", "due_soon", "due_today", "overdue", "delinquent")


def _due_date_for(period, due_day):
    last_day = calendar.monthrange(period.year, period.month)[1]
    return period.replace(day=min(due_day, last_day))


def _status_for(due_date, today):
    days_late = (today - due_date).days
    if days_late > DELINQUENT_AFTER_DAYS:
        return "delinquent"
    if days_late > 0:
        return "overdue"
    if days_late == 0:
        return "due_today"
    if days_late >= -DUE_SOON_DAYS:
        return "due_soon"
    return "pending"


def _financial_status_for(dues, today):
    open_dues = [d for d in dues if d.status in OPEN_STATUSES]
    precedence = (
        ("delinquent", "delinquent"),
        ("overdue", "overdue"),
        ("due_today", "due_today"),
        ("due_soon", "due_soon"),
    )
    for due_status, financial_status in precedence:
        if any(d.status == due_status for d in open_dues):
            return financial_status
    paid = [d for d in dues if d.status == "paid"]
    latest_paid = max(paid, key=lambda d: d.period, default=None)
    if latest_paid and latest_paid.period > today.replace(day=1):
        return "paid_in_advance"
    return "up_to_date"


def lock_due_day_to_5(apps, schema_editor):
    BillingProfile = apps.get_model("finance", "BillingProfile")
    Due = apps.get_model("finance", "Due")
    today = date.today()

    BillingProfile.objects.exclude(due_day=DEFAULT_DUE_DAY).update(due_day=DEFAULT_DUE_DAY)

    for profile in BillingProfile.objects.all():
        dues = list(Due.objects.filter(billing_profile=profile))
        for due in dues:
            if due.status in OPEN_STATUSES:
                new_due_date = _due_date_for(due.period, DEFAULT_DUE_DAY)
                new_status = _status_for(new_due_date, today)
                if due.due_date != new_due_date or due.status != new_status:
                    due.due_date = new_due_date
                    due.status = new_status
                    due.save(update_fields=["due_date", "status"])
        if dues:
            new_financial_status = _financial_status_for(dues, today)
            if profile.financial_status != new_financial_status:
                profile.financial_status = new_financial_status
                profile.save(update_fields=["financial_status"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0007_alter_billingprofile_plan"),
    ]

    operations = [
        migrations.RunPython(lock_due_day_to_5, noop),
    ]
