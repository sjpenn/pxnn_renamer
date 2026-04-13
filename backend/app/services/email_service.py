import logging
from datetime import datetime, timezone

import resend
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database.models import User

logger = logging.getLogger(__name__)


def _get_admin_emails(db: Session) -> list[str]:
    admins = db.query(User).filter(User.is_admin.is_(True), User.email.isnot(None)).all()
    return [a.email for a in admins if a.email]


def _send_admin_email(db: Session, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping admin email: %s", subject)
        return

    recipients = _get_admin_emails(db)
    if not recipients:
        logger.warning("No admin emails found — skipping: %s", subject)
        return

    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM_ADDRESS,
            "to": recipients,
            "subject": subject,
            "html": html,
        })
    except Exception:
        logger.exception("Failed to send admin email: %s", subject)


def _email_wrapper(body_content: str) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px;">
        <div style="border-bottom: 2px solid #111; padding-bottom: 12px; margin-bottom: 20px;">
            <strong style="font-size: 14px; letter-spacing: 0.5px;">PXNN ADMIN</strong>
        </div>
        {body_content}
        <div style="margin-top: 24px; padding-top: 12px; border-top: 1px solid #e5e5e5; color: #888; font-size: 12px;">
            {now}
        </div>
    </div>
    """


def _detail_row(label: str, value: str) -> str:
    return f'<tr><td style="padding: 4px 12px 4px 0; color: #666; font-size: 14px;">{label}</td><td style="padding: 4px 0; font-size: 14px;"><strong>{value}</strong></td></tr>'


def notify_new_signup(db: Session, user: User, method: str = "form") -> None:
    body = f"""
    <h2 style="margin: 0 0 16px; font-size: 18px;">New User Signup</h2>
    <table style="border-collapse: collapse;">
        {_detail_row("Username", user.username)}
        {_detail_row("Email", user.email or "—")}
        {_detail_row("Method", method.title())}
    </table>
    """
    _send_admin_email(db, f"New User Signup: {user.username}", _email_wrapper(body))


def notify_purchase(db: Session, user: User, plan_key: str, amount_cents: int, plan_type: str) -> None:
    amount = f"${amount_cents / 100:.2f}"
    body = f"""
    <h2 style="margin: 0 0 16px; font-size: 18px;">New Purchase</h2>
    <table style="border-collapse: collapse;">
        {_detail_row("Username", user.username)}
        {_detail_row("Email", user.email or "—")}
        {_detail_row("Plan", plan_key)}
        {_detail_row("Type", plan_type.replace("_", " ").title())}
        {_detail_row("Amount", amount)}
    </table>
    """
    _send_admin_email(db, f"New Purchase: {plan_key} by {user.username}", _email_wrapper(body))


def notify_account_paused(db: Session, user: User) -> None:
    body = f"""
    <h2 style="margin: 0 0 16px; font-size: 18px;">Account Paused</h2>
    <table style="border-collapse: collapse;">
        {_detail_row("Username", user.username)}
        {_detail_row("Email", user.email or "—")}
        {_detail_row("Plan", user.subscription_plan or "—")}
    </table>
    """
    _send_admin_email(db, f"Account Paused: {user.username}", _email_wrapper(body))


def notify_service_canceled(db: Session, user: User, subscription_id: str) -> None:
    body = f"""
    <h2 style="margin: 0 0 16px; font-size: 18px;">Service Canceled</h2>
    <table style="border-collapse: collapse;">
        {_detail_row("Username", user.username)}
        {_detail_row("Email", user.email or "—")}
        {_detail_row("Previous Plan", user.subscription_plan or "—")}
        {_detail_row("Subscription ID", subscription_id or "—")}
    </table>
    """
    _send_admin_email(db, f"Service Canceled: {user.username}", _email_wrapper(body))
