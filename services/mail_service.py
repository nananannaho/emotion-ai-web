"""SMTP 메일 발송 서비스."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config import MAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME

logger = logging.getLogger(__name__)


class MailService:
    @property
    def configured(self) -> bool:
        return bool(SMTP_HOST and SMTP_PORT and SMTP_USERNAME and SMTP_PASSWORD and MAIL_FROM)

    def _send_message(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

    def send_signup_verification_email(
        self,
        *,
        to_email: str,
        verification_code: str,
    ) -> None:
        if not self.configured:
            raise RuntimeError("smtp_not_configured")

        msg = EmailMessage()
        msg["Subject"] = "[Felunai] 회원가입 이메일 인증번호"
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg.set_content(
            "\n".join([
                "Felunai 회원가입 이메일 인증 요청이 접수되었습니다.",
                "",
                f"인증번호: {verification_code}",
                "",
                "회원가입 화면에서 위 인증번호를 입력해 인증을 완료해 주세요.",
                "본인이 요청하지 않았다면 이 메일을 무시해 주세요.",
            ])
        )

        self._send_message(msg)
        logger.info("회원가입 이메일 인증 메일 발송 완료: %s", to_email)

    def send_password_reset_email(
        self,
        *,
        to_email: str,
        display_name: str,
        reset_url: str,
        reset_code: str,
    ) -> None:
        if not self.configured:
            raise RuntimeError("smtp_not_configured")

        msg = EmailMessage()
        msg["Subject"] = "[Felunai] 비밀번호 재설정 링크"
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg.set_content(
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
            ])
        )

        self._send_message(msg)
        logger.info("비밀번호 재설정 메일 발송 완료: %s", to_email)
