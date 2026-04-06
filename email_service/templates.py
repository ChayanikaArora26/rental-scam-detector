"""email_service/templates.py — HTML email templates with inline CSS."""
from config import get_settings

settings = get_settings()

_BASE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#09090b;font-family:'Inter',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#18181b;border-radius:16px;border:1px solid #3f3f46;overflow:hidden">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#7c3aed,#4f46e5);padding:28px 40px">
          <p style="margin:0;font-size:20px;font-weight:700;color:#fff">🏠 RentalGuard</p>
          <p style="margin:4px 0 0;font-size:13px;color:#c4b5fd">{subtitle}</p>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:36px 40px;color:#a1a1aa;font-size:15px;line-height:1.7">
          {body}
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:20px 40px;border-top:1px solid #27272a;font-size:12px;color:#52525b">
          This email was sent by RentalGuard. If you didn't request this, you can safely ignore it.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

_BTN = '<a href="{url}" style="display:inline-block;margin:20px 0;padding:13px 28px;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;font-size:14px;font-weight:600;text-decoration:none;border-radius:10px">{label}</a>'


def verification_email(token: str) -> tuple[str, str]:
    url = f"{settings.API_URL}/auth/verify?token={token}"
    subject = "Verify your RentalGuard email"
    body = f"""
    <p style="color:#fff;font-size:18px;font-weight:600;margin:0 0 12px">Confirm your email address</p>
    <p>Thanks for signing up! Click the button below to verify your email. This link expires in <strong style="color:#a78bfa">24 hours</strong>.</p>
    {_BTN.format(url=url, label="Verify Email")}
    <p style="font-size:13px;color:#52525b">Or copy this link:<br>
    <span style="color:#7c3aed;word-break:break-all">{url}</span></p>
    """
    html = _BASE.format(subtitle="Email Verification", body=body)
    return subject, html


def password_reset_email(token: str) -> tuple[str, str]:
    url = f"{settings.APP_URL}/reset-password?token={token}"
    subject = "Reset your RentalGuard password"
    body = f"""
    <p style="color:#fff;font-size:18px;font-weight:600;margin:0 0 12px">Reset your password</p>
    <p>We received a request to reset your password. Click below — this link expires in <strong style="color:#f59e0b">15 minutes</strong>.</p>
    {_BTN.format(url=url, label="Reset Password")}
    <p style="font-size:13px;color:#52525b">If you didn't request this, your account is safe — just ignore this email.</p>
    """
    html = _BASE.format(subtitle="Password Reset", body=body)
    return subject, html


def login_alert_email(ip: str) -> tuple[str, str]:
    subject = "New login to your RentalGuard account"
    body = f"""
    <p style="color:#fff;font-size:18px;font-weight:600;margin:0 0 12px">New login detected</p>
    <p>Your account was just accessed from IP <strong style="color:#a78bfa">{ip}</strong>.</p>
    <p>If this was you, no action needed. If not, <a href="{settings.APP_URL}/forgot-password" style="color:#7c3aed">reset your password immediately</a>.</p>
    """
    html = _BASE.format(subtitle="Security Alert", body=body)
    return subject, html
