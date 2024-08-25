"""
Email Setup and Notification Module

This module provides functions to set up email configurations and send email notifications.

Functions:
    send_email(too_email, subject, body): Sends an email to the specified recipients.
    notify_success(subject, body): Sends a success notification email.
    notify_failure(subject, body): Sends a failure notification email.
"""

from email_setup.email_config import *
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(too_email, subject, body):
    """
    This function is used to send emails whenever there are changes in CRUD operations
    :param too_email: list of email addresses needed to be sent
    :param subject: The subject of the email
    :param body: The message which user needs to be notified
    :return: None
    """
    if too_email is None:
        too_email = []

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(too_email)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, PASSWORD)
        server.sendmail(SENDER_EMAIL, too_email, msg.as_string())


def notify_success(subject, body):
    """
       Sends an email notification for successful operations.

       :param subject: Subject of the success email.
       :param body: Body content of the success email.
       :return: None
       """
    send_email(RECEIVER_EMAIL, subject, body)


def notify_failure(subject, body):
    """
        Sends an email notification for failed operations.

        :param subject: Subject of the failure email.
        :param body: Body content of the failure email.
        :return: None
        """
    send_email(ERROR_HANDLING_GROUP_EMAIL, subject, body)
