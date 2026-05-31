"""Resend 우선 메일 발송 서비스."""

from __future__ import annotations

import json
import logging
import smtplib
import time
from email.message import EmailMessage
from html import escape
from urllib import error, request

from config import (
    MAIL_FROM,
    RESEND_API_BASE,
    RESEND_API_KEY,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)

logger = logging.getLogger(__name__)


class MailService:
    @property
    def configured(self) -> bool:
        return self.provider is not None

    @property
    def provider(self) -> str | None:
        if RESEND_API_KEY and MAIL_FROM:
            return "resend"
        if SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and MAIL_FROM:
            return "smtp"
        return None

    @property
    def smtp_configured(self) -> bool:
        return bool(SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and MAIL_FROM)

    @property
    def resend_configured(self) -> bool:
        return bool(RESEND_API_KEY and MAIL_FROM)

    def _send_message_smtp(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

    @staticmethod
    def _normalize_site_url(site_url: str | None) -> str:
        return (site_url or "").strip().rstrip("/")

    def _build_email_html(
        self,
        *,
        site_url: str | None,
        title: str,
        subtitle: str,
        body_html: str,
        footer_note: str,
    ) -> str:
        origin = self._normalize_site_url(site_url)
        logo_html = ""
        if origin:
            logo_url = f"{origin}/static/img/felunai-mark.svg"
            logo_html = (
                f'<img src="{escape(logo_url)}" alt="Felunai" width="64" height="64" '
                'style="display:block;width:64px;height:64px;margin:0 auto 18px;border:0;outline:none;text-decoration:none;">'
            )

        return f"""\
<!doctype html>
<html lang="ko">
  <body style="margin:0;padding:24px;background:#070a14;font-family:'Noto Sans KR',Arial,sans-serif;color:#e8eaef;">
    <div style="max-width:560px;margin:0 auto;padding:32px 28px;background:#0f1320;border:1px solid rgba(255,255,255,0.08);border-radius:24px;">
      <div style="text-align:center;">
        {logo_html}
        <div style="font-size:28px;letter-spacing:0.18em;color:#f4f6fb;margin-bottom:8px;">Felunai</div>
        <div style="font-size:13px;color:#a6adbb;margin-bottom:24px;">{escape(subtitle)}</div>
      </div>
      <div style="font-size:24px;font-weight:700;line-height:1.35;margin-bottom:16px;color:#f8f9fc;">{escape(title)}</div>
      <div style="font-size:15px;line-height:1.8;color:#c9ced8;">{body_html}</div>
      <div style="margin-top:28px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.08);font-size:12px;line-height:1.7;color:#8e97a8;">
        {escape(footer_note)}
      </div>
    </div>
  </body>
</html>
"""

    def _send_message_resend(self, *, to_email: str, subject: str, text: str, html: str | None = None) -> None:
        payload = json.dumps({
            "from": MAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "text": text,
            "html": html or text.replace("\n", "<br>"),
        }).encode("utf-8")
        req = request.Request(
            f"{RESEND_API_BASE}/emails",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Felunai/1.0",
            },
        )
        try:
            with request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status >= 400:
                    raise RuntimeError(f"resend_http_{resp.status}: {body}")
                logger.info("Resend 메일 발송 완료: %s", body)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"resend_http_{exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"resend_network_error: {exc.reason}") from exc

    def _build_smtp_message(
        self,
        *,
        to_email: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        return msg

    def _send_email(
        self,
        *,
        to_email: str,
        subject: str,
        text: str,
        html: str | None = None,
    ) -> None:
        errors: list[str] = []
        msg = self._build_smtp_message(
            to_email=to_email,
            subject=subject,
            text=text,
            html=html,
        )

        if self.resend_configured:
            for attempt in range(2):
                try:
                    self._send_message_resend(to_email=to_email, subject=subject, text=text, html=html)
                    return
                except Exception as exc:
                    errors.append(f"resend:{exc}")
                    logger.warning("Resend 발송 실패 (시도 %s/2): %s", attempt + 1, exc)
                    if attempt == 0:
                        time.sleep(1.2)

        if self.smtp_configured:
            try:
                self._send_message_smtp(msg)
                logger.info("SMTP 폴백 메일 발송 완료: %s", to_email)
                return
            except Exception as exc:
                errors.append(f"smtp:{exc}")
                logger.exception("SMTP 발송 실패: %s", exc)

        if errors:
            raise RuntimeError(" | ".join(errors))
        raise RuntimeError("mail_not_configured")

    def send_signup_verification_email(
        self,
        *,
        to_email: str,
        verification_code: str,
        site_url: str | None = None,
    ) -> None:
        if not self.configured:
            raise RuntimeError("mail_not_configured")

        text = "\n".join([
            "Felunai 회원가입 이메일 인증 요청이 접수되었습니다.",
            "",
            f"인증번호: {verification_code}",
            "",
            "회원가입 화면에서 위 인증번호를 입력해 인증을 완료해 주세요.",
            "본인이 요청하지 않았다면 이 메일을 무시해 주세요.",
        ])
        html = self._build_email_html(
            site_url=site_url,
            title="회원가입 이메일 인증번호",
            subtitle="Brand Verification",
            body_html=(
                "<p style=\"margin:0 0 16px;\">Felunai 회원가입 이메일 인증 요청이 접수되었습니다.</p>"
                "<p style=\"margin:0 0 24px;\">아래 인증번호를 회원가입 화면에 입력해 인증을 완료해 주세요.</p>"
                f"<div style=\"margin:0 0 24px;padding:16px 20px;border-radius:18px;background:#151b2b;border:1px solid rgba(151,139,255,0.24);font-size:30px;font-weight:700;letter-spacing:0.32em;text-align:center;color:#b7b1ff;\">{escape(verification_code)}</div>"
                "<p style=\"margin:0;color:#98a1b3;\">본인이 요청하지 않았다면 이 메일을 무시해 주세요.</p>"
            ),
            footer_note="이 메일은 Felunai 회원가입 이메일 인증을 위해 자동 발송되었습니다.",
        )
        self._send_email(
            to_email=to_email,
            subject="[Felunai] 회원가입 이메일 인증번호",
            text=text,
            html=html,
        )
        logger.info("%s 회원가입 이메일 인증 메일 발송 완료: %s", self.provider, to_email)

    def send_password_reset_email(
        self,
        *,
        to_email: str,
        display_name: str,
        reset_url: str,
        reset_code: str,
        site_url: str | None = None,
    ) -> None:
        if not self.configured:
            raise RuntimeError("mail_not_configured")

        text = "\n".join([
            f"{display_name}님, 안녕하세요.",
            "",
            "Felunai 비밀번호 재설정 요청이 접수되었습니다.",
            "아래 링크를 눌러 새 비밀번호를 설정해 주세요.",
            "",
            reset_url,
            "",
            f"링크가 열리지 않으면 인증번호 {reset_code} 를 입력해서도 재설정할 수 있습니다.",
            "",
            "이 링크는 1회만 사용할 수 있으며 일정 시간이 지나면 만료됩니다.",
            "본인이 요청하지 않았다면 이 메일을 무시해 주세요.",
        ])
        html = self._build_email_html(
            site_url=site_url,
            title="비밀번호 재설정 안내",
            subtitle="Secure Password Reset",
            body_html=(
                f"<p style=\"margin:0 0 16px;\">{escape(display_name)}님, 안녕하세요.</p>"
                "<p style=\"margin:0 0 16px;\">Felunai 비밀번호 재설정 요청이 접수되었습니다. 아래 버튼을 눌러 새 비밀번호를 설정해 주세요.</p>"
                f"<div style=\"margin:0 0 24px;\"><a href=\"{escape(reset_url)}\" style=\"display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#8c84ff,#6a63e6);color:#ffffff;text-decoration:none;font-weight:700;\">비밀번호 재설정하기</a></div>"
                "<p style=\"margin:0 0 12px;\">링크가 열리지 않으면 아래 인증번호로도 재설정할 수 있습니다.</p>"
                f"<div style=\"margin:0 0 24px;padding:16px 20px;border-radius:18px;background:#151b2b;border:1px solid rgba(151,139,255,0.24);font-size:30px;font-weight:700;letter-spacing:0.32em;text-align:center;color:#b7b1ff;\">{escape(reset_code)}</div>"
                "<p style=\"margin:0;color:#98a1b3;\">이 요청을 본인이 하지 않았다면 이 메일을 무시해 주세요.</p>"
            ),
            footer_note="이 메일은 Felunai 비밀번호 재설정을 위해 자동 발송되었습니다.",
        )
        self._send_email(
            to_email=to_email,
            subject="[Felunai] 비밀번호 재설정 링크",
            text=text,
            html=html,
        )
        logger.info("%s 비밀번호 재설정 메일 발송 완료: %s", self.provider, to_email)
