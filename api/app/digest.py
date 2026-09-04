"""The daily digest email.

The digest is the *other* half of the product: the decision inbox is where the
agent asks, and this is where it accounts for everything it did without asking.
On a good day it is one line long.

**This is the only outbound email in the system.** It goes to the household's own
address, it is composed entirely from the `DailyBrief` the agent already wrote,
and nothing here can send on the user's behalf — there is no recipient except the
user, no reply path, and no free text from the model. Everything the agent sends
*outward* is a draft (`docs/status/DECISIONS.md`, 2026-08-21, "drafts and
requests, never sends and transfers").

`send_digest()` is never called by a route. Sending is an explicit action taken by
a scheduled job with `QH_DIGEST_TO` and `QH_SES_SENDER` both set; without them it
raises. `render_digest()` is pure and is what the preview route serves.

Email HTML is not web HTML: tables, inline styles, no flexbox or grid, no external
stylesheet. `prefers-color-scheme` is honoured by Apple Mail and modern Outlook
and ignored safely everywhere else.
"""

from __future__ import annotations

import os
from html import escape

from quiet_hours_contracts import DailyBrief, Household, Money

INK = "#14161a"
MUTED = "#6b7280"
LINE = "#e6e8ec"
PAPER = "#ffffff"
CANVAS = "#f6f7f9"
ACCENT = "#b45309"
"""The one accent colour, reserved for 'this needs you'. Nothing else uses it."""


def format_money(amount: Money | None) -> str:
    """Mirror of `formatMoney()` in `contracts/typescript/index.ts`.

    The one place in Python outside the contracts where `amount_minor` is divided
    by 100 — an email cannot call the TypeScript helper.
    """
    if amount is None:
        return ""
    symbol = {"GBP": "£", "EUR": "€", "USD": "$"}.get(amount.currency, "")
    value = f"{amount.amount_minor / 100:,.2f}"
    value = value.removesuffix(".00")
    return f"{symbol}{value}" if symbol else f"{amount.currency} {value}"


def subject_for(brief: DailyBrief) -> str:
    """The subject line is the whole message on a quiet day. It says what
    happened, not that a report is available."""
    pending = len(brief.pending_decision_ids)
    if pending == 0:
        return "Quiet Hours: nothing needs you today"
    if pending == 1:
        return "Quiet Hours: one thing needs you"
    return f"Quiet Hours: {pending} things need you"


def render_text(brief: DailyBrief, household: Household, *, app_url: str = "") -> str:
    """The plain-text alternative. Sent alongside the HTML, and the reason the
    digest still reads correctly in a client that strips markup."""
    lines = [brief.headline, ""]
    pending = len(brief.pending_decision_ids)
    if pending:
        lines += [
            f"{pending} decision{'s' if pending != 1 else ''} waiting for you"
            + (f": {app_url}" if app_url else ""),
            "",
        ]
    if brief.handled_silently:
        lines.append("Handled without asking:")
        lines += [f"  - {item}" for item in brief.handled_silently]
        lines.append("")
    if brief.savings_this_month:
        lines += [f"Saved this month: {format_money(brief.savings_this_month)}", ""]
    lines.append(f"{round(brief.autonomy_rate * 100)}% of actions handled without asking.")
    lines.append("")
    lines.append(f"Quiet Hours for {household.display_name}")
    return "\n".join(lines)


def _row(item: str) -> str:
    return (
        f'<tr><td style="padding:7px 0;border-bottom:1px solid {LINE};'
        f'font-size:15px;color:{INK};line-height:1.45">'
        f'<span style="color:{MUTED};padding-right:10px">&#10003;</span>{escape(item)}'
        "</td></tr>"
    )


def render_html(brief: DailyBrief, household: Household, *, app_url: str = "") -> str:
    """The digest, as an email.

    Structured so the first thing read is the headline and the second is the one
    thing that needs a human — in that order, because most days there is no
    second thing.
    """
    pending = len(brief.pending_decision_ids)
    handled = "".join(_row(item) for item in brief.handled_silently)
    autonomy = round(brief.autonomy_rate * 100)

    needs_you = ""
    if pending:
        label = "1 decision needs you" if pending == 1 else f"{pending} decisions need you"
        button = (
            f'<a href="{escape(app_url)}" style="display:inline-block;margin-top:12px;'
            f"background:{ACCENT};color:#ffffff;text-decoration:none;padding:11px 18px;"
            'border-radius:8px;font-size:15px;font-weight:600">Open your inbox</a>'
            if app_url
            else ""
        )
        needs_you = (
            f'<tr><td style="padding:18px 0 4px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:{CANVAS};border-left:3px solid {ACCENT};border-radius:8px">'
            f'<tr><td style="padding:16px 18px">'
            f'<div style="font-size:15px;font-weight:600;color:{INK}">{label}</div>'
            f'<div style="font-size:14px;color:{MUTED};padding-top:4px">'
            "Everything else below was handled without asking.</div>"
            f"{button}</td></tr></table></td></tr>"
        )

    savings = ""
    if brief.savings_this_month:
        savings = (
            f'<tr><td style="padding:14px 0 0;font-size:14px;color:{MUTED}">'
            f'Saved this month <strong style="color:{INK}">'
            f"{escape(format_money(brief.savings_this_month))}</strong>"
            f"&nbsp;&middot;&nbsp;{autonomy}% handled without asking</td></tr>"
        )

    handled_block = (
        f'<tr><td style="padding:22px 0 6px;font-size:13px;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:.06em;color:{MUTED}">'
        "Handled without asking</td></tr>"
        f'<tr><td><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0">{handled}</table></td></tr>'
        if brief.handled_silently
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{escape(subject_for(brief))}</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">
{escape(brief.headline)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="background:{CANVAS};padding:28px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="max-width:560px;background:{PAPER};border:1px solid {LINE};border-radius:14px">
<tr><td style="padding:26px 26px 24px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="font-size:12px;font-weight:600;letter-spacing:.10em;
 text-transform:uppercase;color:{MUTED}">Quiet Hours</td></tr>
<tr><td style="padding:10px 0 0;font-size:24px;line-height:1.25;font-weight:600;
 color:{INK}">{escape(brief.headline)}</td></tr>
{needs_you}
{handled_block}
{savings}
<tr><td style="padding:22px 0 0;border-top:1px solid {LINE};font-size:12px;
 color:{MUTED};line-height:1.5">
Quiet Hours never sends a message or moves money on your behalf without asking.
Everything above is in your activity trail, with the reasoning behind it.
</td></tr>
</table>
</td></tr>
</table>
<div style="font-size:12px;color:{MUTED};padding:14px 0">
{escape(household.display_name)}</div>
</td></tr>
</table>
</body>
</html>"""


def send_digest(brief: DailyBrief, household: Household, *, app_url: str = "") -> str:
    """Send the digest through SES. Never called by a route.

    Raises rather than silently doing nothing when it is not configured — a
    digest that quietly fails to send is a product that quietly stops existing.
    """
    to_address = os.environ.get("QH_DIGEST_TO", "").strip()
    sender = os.environ.get("QH_SES_SENDER", "").strip()
    if not to_address or not sender:
        raise RuntimeError(
            "the digest needs QH_DIGEST_TO and QH_SES_SENDER. It is only ever sent to the "
            "household's own address."
        )

    import boto3

    client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    result = client.send_email(
        Source=sender,
        Destination={"ToAddresses": [to_address]},
        Message={
            "Subject": {"Data": subject_for(brief), "Charset": "UTF-8"},
            "Body": {
                "Text": {
                    "Data": render_text(brief, household, app_url=app_url),
                    "Charset": "UTF-8",
                },
                "Html": {
                    "Data": render_html(brief, household, app_url=app_url),
                    "Charset": "UTF-8",
                },
            },
        },
    )
    return str(result.get("MessageId", ""))
