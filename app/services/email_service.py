import asyncio
import smtplib
from email.message import EmailMessage

from app.config import settings
from app.core.exceptions import ValidationError


class EmailService:
    def _ensure_configured(self) -> tuple[str, int, str, str, str, bool]:
        if not settings.smtp_host:
            raise ValidationError("SMTP сервер не настроен")
        if not settings.smtp_username or not settings.smtp_password:
            raise ValidationError("SMTP логин или пароль не настроены")
        if not settings.smtp_from_email:
            raise ValidationError("Адрес отправителя SMTP не настроен")
        return (
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_from_email,
            settings.smtp_use_tls,
        )

    async def send_feedback_email(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        host, port, username, password, from_email, use_tls = self._ensure_configured()

        message = EmailMessage()
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        await asyncio.to_thread(
            self._send_sync,
            host,
            port,
            username,
            password,
            use_tls,
            message,
        )

    @staticmethod
    def _send_sync(
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        message: EmailMessage,
    ) -> None:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
