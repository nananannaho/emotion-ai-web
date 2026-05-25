"""Resend 우선 메일 발송 서비스."""

from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage
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

    def _send_message_smtp(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

    def _send_message_resend(self, *, to_email: str, subject: str, text: str) -> None:
        payload = json.dumps({
            "from": MAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "text": text,
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
            with request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status >= 400:
                    raise RuntimeError(f"resend_http_{resp.status}: {body}")
                logger.info("Resend 메일 발송 완료: %s", body)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"resend_http_{exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"resend_network_error: {exc.reason}") from exc

    def _send_text_email(self, *, to_email: str, subject: str, text: str) -> None:
        if self.provider == "resend":
            self._send_message_resend(to_email=to_email, subject=subject, text=text)
            return
        if self.provider == "smtp":
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = MAIL_FROM
            msg["To"] = to_email
            msg.set_content(text)
            self._send_message_smtp(msg)
            return
        raise RuntimeError("mail_not_configured")

    def send_signup_verification_email(
        self,
        *,
        to_email: str,
        verification_code: str,
    ) -> None:
        if not self.configured:
            raise RuntimeError("mail_not_configured")

        self._send_text_email(
            to_email=to_email,
            subject="[Felunai] 회원가입 이메일 인증번호",
            text=
            "\n".join([
                "Felunai 회원가입 이메일 인증 요청이 접수되었습니다.",
                "",
                f"인증번호: {verification_code}",
                "",
                "회원가입 화면에서 위 인증번호를 입력해 인증을 완료해 주세요.",
                "본인이 요청하지 않았다면 이 메일을 무시해 주세요.",
            ]),
        )
        logger.info("%s 회원가입 이메일 인증 메일 발송 완료: %s", self.provider, to_email)

    def send_password_reset_email(
        self,
        *,
        to_email: str,
        display_name: str,
        reset_url: str,
        reset_code: str,
    ) -> None:
        if not self.configured:
            raise RuntimeError("mail_not_configured")

        self._send_text_email(
            to_email=to_email,
            subject="[Felunai] 비밀번호 재설정 링크",
            text=
            "\n".join([
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
            ]),
        )
        logger.info("%s 비밀번호 재설정 메일 발송 완료: %s", self.provider, to_email)
