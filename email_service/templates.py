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


def analysis_report_email(
    result: dict,
    llm_out: dict,
    filename: str,
) -> tuple[str, str]:
    verdict      = result.get("verdict", "Unknown")
    combined     = result.get("combined_risk", 0)
    flag_score   = result.get("flag_score", 0)
    n_flags      = result.get("n_flags", 0)
    n_anomalous  = result.get("n_anomalous", 0)
    total_chunks = result.get("total_chunks", 0)
    red_flags    = result.get("red_flags", [])
    llm_text     = (llm_out or {}).get("explanation", "")

    # Verdict colour
    risk_pct = int(combined * 100)
    if combined >= 0.65:
        verdict_colour = "#ef4444"   # red
        verdict_bg     = "#450a0a"
        verdict_label  = "HIGH RISK"
    elif combined >= 0.35:
        verdict_colour = "#f59e0b"   # amber
        verdict_bg     = "#451a03"
        verdict_label  = "MODERATE RISK"
    else:
        verdict_colour = "#22c55e"   # green
        verdict_bg     = "#052e16"
        verdict_label  = "LOW RISK"

    doc_label = f'<strong style="color:#a78bfa">{filename}</strong>' if filename else "your document"

    # Red flags section — each item is a dict {flag, snippet, severity, severity_label}
    if red_flags:
        flag_items = "".join(
            f'<tr><td style="padding:8px 12px;border-bottom:1px solid #27272a;font-size:14px;color:#fca5a5">⚠️ {f["flag"] if isinstance(f, dict) else f}'
            + (f'<span style="float:right;font-size:11px;color:#71717a">{f["severity_label"]}</span>' if isinstance(f, dict) else "")
            + '</td></tr>'
            for f in red_flags
        )
        flags_section = f"""
        <p style="color:#fff;font-size:16px;font-weight:600;margin:28px 0 10px">🚩 Red Flags Detected ({n_flags})</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1c1917;border-radius:10px;border:1px solid #3f3f46;overflow:hidden">
          {flag_items}
        </table>
        """
    else:
        flags_section = '<p style="color:#22c55e">✅ No red flags detected.</p>'

    # Anomalous clauses section — result["details"] is a pandas DataFrame
    details = result.get("details")
    anomaly_rows = ""
    try:
        if details is not None and hasattr(details, "iterrows"):
            # Find the anomaly boolean column (last bool-dtype column)
            bool_cols = [c for c in details.columns if details[c].dtype == bool]
            anomaly_col = bool_cols[-1] if bool_cols else None
            if anomaly_col:
                anomalous_df = details[details[anomaly_col]].head(10)
                text_col = details.columns[0]
                sim_col  = "similarity" if "similarity" in details.columns else None
                for _, row in anomalous_df.iterrows():
                    clause_text = str(row[text_col])
                    snippet = clause_text[:200] + ("…" if len(clause_text) > 200 else "")
                    sim_str = f"{float(row[sim_col]):.0%}" if sim_col else ""
                    anomaly_rows += f"""
                    <tr>
                      <td style="padding:10px 14px;border-bottom:1px solid #27272a;font-size:13px;color:#e4e4e7">{snippet}</td>
                      <td style="padding:10px 14px;border-bottom:1px solid #27272a;font-size:12px;color:#f87171;text-align:right;white-space:nowrap">
                        {f"sim {sim_str}" if sim_str else "anomalous"}
                      </td>
                    </tr>"""
    except Exception:
        pass

    clauses_section = ""
    if anomaly_rows:
        clauses_section = f"""
        <p style="color:#fff;font-size:16px;font-weight:600;margin:28px 0 10px">📋 Anomalous Clauses ({n_anomalous} of {total_chunks})</p>
        <p style="color:#71717a;font-size:13px;margin:0 0 10px">These clauses are significantly different from the 510 real contracts in our database.</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1c1917;border-radius:10px;border:1px solid #3f3f46;overflow:hidden">
          <tr style="background:#27272a">
            <th style="padding:8px 14px;font-size:11px;color:#71717a;text-align:left;font-weight:600;text-transform:uppercase">Clause</th>
            <th style="padding:8px 14px;font-size:11px;color:#71717a;text-align:right;font-weight:600;text-transform:uppercase">Match</th>
          </tr>
          {anomaly_rows}
        </table>
        """

    # LLM explanation
    llm_section = ""
    if llm_text:
        llm_section = f"""
        <p style="color:#fff;font-size:16px;font-weight:600;margin:28px 0 10px">🤖 AI Analysis</p>
        <div style="background:#1e1b4b;border-radius:10px;border:1px solid #3730a3;padding:16px 20px;font-size:14px;color:#c7d2fe;line-height:1.7">
          {llm_text.replace(chr(10), "<br>")}
        </div>
        """

    subject = f"RentalGuard Report — {verdict_label} ({risk_pct}% risk)"
    body = f"""
    <p style="color:#fff;font-size:18px;font-weight:600;margin:0 0 8px">Your Analysis Report</p>
    <p style="margin:0 0 24px">Here are the results for {doc_label}.</p>

    <!-- Verdict banner -->
    <div style="background:{verdict_bg};border:1px solid {verdict_colour};border-radius:12px;padding:20px 24px;display:flex;align-items:center;gap:16px;margin-bottom:8px">
      <div>
        <p style="margin:0;font-size:28px;font-weight:800;color:{verdict_colour}">{risk_pct}%</p>
        <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:{verdict_colour};letter-spacing:.05em">{verdict_label}</p>
      </div>
      <div style="border-left:1px solid {verdict_colour};opacity:.3;height:48px;margin:0 8px"></div>
      <div>
        <p style="margin:0;font-size:15px;font-weight:600;color:#fff">{verdict}</p>
        <p style="margin:4px 0 0;font-size:13px;color:#a1a1aa">{n_flags} red flags · {n_anomalous}/{total_chunks} clauses anomalous</p>
      </div>
    </div>

    {flags_section}
    {clauses_section}
    {llm_section}

    <p style="margin:28px 0 0;font-size:13px;color:#52525b">
      This report is for informational purposes only and does not constitute legal advice.
      If you suspect fraud, contact your local consumer protection agency.
    </p>
    """
    html = _BASE.format(subtitle="Analysis Report", body=body)
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
