"""Outbound mail behind a port. Backends: console (dev), smtp (production), recording (tests)."""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from packages.settings import settings

log = logging.getLogger("nexussaas.mail")


@dataclass
class Mail:
    to: str
    subject: str
    text: str


class MailPort(Protocol):
    def send(self, mail: Mail) -> None: ...


class ConsoleMailer:
    def send(self, mail: Mail) -> None:
        log.info("MAIL to=%s subject=%r\n%s", mail.to, mail.subject, mail.text)
        print(f"--- MAIL to {mail.to}: {mail.subject}\n{mail.text}\n---", flush=True)


@dataclass
class RecordingMailer:
    sent: list[Mail] = field(default_factory=list)

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)


class SMTPMailer:
    def send(self, mail: Mail) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.MAIL_FROM, mail.to, mail.subject
        msg.set_content(mail.text)
        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
        with server:
            if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)


_mailer: MailPort | None = None


def get_mailer() -> MailPort:
    global _mailer
    if _mailer is None:
        backend = settings.MAIL_BACKEND
        if backend == "smtp":
            if not settings.SMTP_HOST:
                raise RuntimeError("MAIL_BACKEND=smtp requires SMTP_HOST")
            _mailer = SMTPMailer()
        elif backend == "recording":
            _mailer = RecordingMailer()
        else:
            _mailer = ConsoleMailer()
    return _mailer


def set_mailer(m: MailPort | None) -> None:
    global _mailer
    _mailer = m
