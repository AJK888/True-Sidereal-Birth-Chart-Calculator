"""
Email service for sending emails via SendGrid.

This module handles all email sending functionality including:
- Snapshot reading emails
- Full reading emails with PDF attachments
- Synastry analysis emails
"""

import os
import base64
import logging
from datetime import datetime
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# --- Configuration ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")


def send_snapshot_email_via_sendgrid(
    snapshot_text: str,
    recipient_email: str,
    chart_name: str,
    birth_date: str,
    birth_time: str,
    location: str
) -> bool:
    """Send snapshot reading email via SendGrid (text only, no PDF)."""
    if not SENDGRID_API_KEY or not SENDGRID_FROM_EMAIL:
        logger.warning("SendGrid not configured - cannot send snapshot email")
        return False
    
    try:
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=recipient_email,
            subject=f"Chart Snapshot: {chart_name}",
            html_content=f"""
            <html>
            <body>
                <h2>Your Chart Snapshot</h2>
                <p><strong>Name:</strong> {chart_name}</p>
                <p><strong>Birth Date:</strong> {birth_date}</p>
                <p><strong>Birth Time:</strong> {birth_time}</p>
                <p><strong>Location:</strong> {location}</p>
                <hr>
                <div style="white-space: pre-wrap;">{snapshot_text.replace(chr(10), '<br>')}</div>
            </body>
            </html>
            """
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 202]:
            logger.info(f"Snapshot email sent successfully to {recipient_email}")
            return True
        else:
            logger.error(f"SendGrid returned status {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending snapshot email: {e}", exc_info=True)
        return False


def send_chart_email_via_sendgrid(
    pdf_bytes: bytes,
    recipient_email: str,
    subject: str,
    chart_name: str
) -> bool:
    """Send email with PDF attachment using SendGrid API."""
    # Create log file path
    log_file_path = "sendgrid_connection.log"
    
    def write_to_log(message: str, is_error: bool = False):
        """Write message to both logger and log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        logger.info(message) if not is_error else logger.error(message)
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as log_error:
            logger.error(f"Failed to write to log file: {log_error}")
    
    write_to_log("="*60)
    write_to_log("SendGrid Email Sending Attempt")
    write_to_log("="*60)
    
    if not SENDGRID_API_KEY:
        error_msg = "SendGrid API key not configured. Cannot send email."
        write_to_log(error_msg, is_error=True)
        write_to_log(f"  SENDGRID_API_KEY value: {SENDGRID_API_KEY}")
        write_to_log(f"  SENDGRID_API_KEY length: {len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 0}")
        return False
    
    if not SENDGRID_FROM_EMAIL:
        error_msg = "SendGrid FROM email not configured. Cannot send email."
        write_to_log(error_msg, is_error=True)
        write_to_log(f"  SENDGRID_FROM_EMAIL value: {SENDGRID_FROM_EMAIL}")
        return False
    
    write_to_log(f"SendGrid Configuration Check:")
    write_to_log(f"  API Key present: Yes (length: {len(SENDGRID_API_KEY)} characters)")
    write_to_log(f"  From Email: {SENDGRID_FROM_EMAIL}")
    write_to_log(f"  To Email: {recipient_email}")
    write_to_log(f"  Subject: {subject}")
    write_to_log(f"  Chart name: {chart_name}")
    write_to_log(f"  PDF size: {len(pdf_bytes)} bytes")

    try:
        # Create email message
        write_to_log("Creating email message object...")
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=recipient_email,
            subject=subject,
            html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Your Astrology Chart Report</h2>
                <p>Dear {chart_name},</p>
                <p>Thank you for using Synthesis Astrology. Your complete astrological chart report is attached as a PDF.</p>
                <p>The PDF includes:</p>
                <ul>
                    <li>Your natal chart wheels (Sidereal and Tropical)</li>
                    <li>Your complete AI Astrological Synthesis</li>
                    <li>Full astrological data and positions</li>
                </ul>
                <p>We hope this report provides valuable insights into your personality, life patterns, and spiritual growth.</p>
                <p>Best regards,<br>Synthesis Astrology<br><a href="https://synthesisastrology.com" style="color: #1b6ca8;">synthesisastrology.com</a></p>
            </body>
            </html>
            """
        )
        write_to_log("Email message object created successfully")
        
        # Attach PDF
        write_to_log("Encoding PDF attachment...")
        encoded_pdf = base64.b64encode(pdf_bytes).decode()
        attachment = Attachment(
            FileContent(encoded_pdf),
            FileName(f"Astrology_Report_{chart_name.replace(' ', '_')}.pdf"),
            FileType('application/pdf'),
            Disposition('attachment')
        )
        message.add_attachment(attachment)
        write_to_log(f"PDF attachment added (encoded size: {len(encoded_pdf)} characters)")
        
        # Initialize SendGrid client
        write_to_log("Initializing SendGrid client...")
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            write_to_log("SendGrid client initialized successfully")
        except Exception as init_error:
            error_msg = f"Failed to initialize SendGrid client: {type(init_error).__name__}: {init_error}"
            write_to_log(error_msg, is_error=True)
            import traceback
            write_to_log(f"Initialization traceback: {traceback.format_exc()}", is_error=True)
            return False
        
        # Attempt to send email
        write_to_log("Attempting to send email via SendGrid API...")
        try:
            response = sg.send(message)
            write_to_log(f"SendGrid API call completed")
            write_to_log(f"Response status code: {response.status_code}")
            
            # Log response details
            if hasattr(response, 'headers'):
                write_to_log(f"Response headers: {dict(response.headers)}")
            if hasattr(response, 'body'):
                try:
                    if isinstance(response.body, bytes):
                        response_body = response.body.decode('utf-8')
                    else:
                        response_body = str(response.body)
                    write_to_log(f"Response body: {response_body[:500]}")  # First 500 chars
                except Exception as decode_error:
                    write_to_log(f"Could not decode response body: {decode_error}")
            
            if response.status_code in [200, 202]:
                success_msg = f"Email with PDF sent successfully via SendGrid to {recipient_email} (status: {response.status_code})"
                write_to_log(success_msg)
                write_to_log("="*60)
                return True
            else:
                # Get response body properly - SendGrid response has body as bytes
                try:
                    if hasattr(response, 'body'):
                        if isinstance(response.body, bytes):
                            response_body = response.body.decode('utf-8')
                        else:
                            response_body = str(response.body)
                    else:
                        response_body = f"No body attribute. Response: {response}"
                except Exception as decode_error:
                    response_body = f"Error decoding response body: {decode_error}. Response object: {response}"
                
                error_msg = f"SendGrid returned non-success status: {response.status_code}"
                write_to_log(error_msg, is_error=True)
                write_to_log(f"SendGrid response body: {response_body}", is_error=True)
                write_to_log(f"SendGrid response headers: {getattr(response, 'headers', 'N/A')}", is_error=True)
                write_to_log("="*60)
                return False
                
        except Exception as send_error:
            error_msg = f"Exception during SendGrid send() call: {type(send_error).__name__}: {send_error}"
            write_to_log(error_msg, is_error=True)
            import traceback
            write_to_log(f"Send error traceback: {traceback.format_exc()}", is_error=True)
            write_to_log("="*60)
            return False
            
    except Exception as e:
        error_msg = f"Error sending email via SendGrid to {recipient_email}: {type(e).__name__}: {e}"
        write_to_log(error_msg, is_error=True)
        import traceback
        write_to_log(f"Full traceback: {traceback.format_exc()}", is_error=True)
        write_to_log("="*60)
        return False


def send_synastry_email(analysis_text: str, recipient_email: str) -> bool:
    """Send synastry analysis via email using SendGrid."""
    if not SENDGRID_API_KEY or not SENDGRID_FROM_EMAIL:
        logger.warning("SendGrid not configured, skipping email send")
        return False
    
    try:
        # Create HTML email
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #1b6ca8;">Synastry Analysis</h2>
            <p>Your comprehensive synastry analysis is complete.</p>
            <div style="white-space: pre-wrap; background: #f9f9f9; padding: 1.5em; border-radius: 6px; margin-top: 1em;">
{analysis_text}
            </div>
            <p style="margin-top: 2em; color: #666; font-size: 0.9em;">
                This analysis was generated by Synthesis Astrology using true sidereal astrology, numerology, and Chinese zodiac.
            </p>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=recipient_email,
            subject="Your Comprehensive Synastry Analysis",
            html_content=html_content
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 202]:
            logger.info(f"Synastry analysis email sent successfully to {recipient_email}")
            return True
        else:
            logger.error(f"Failed to send email: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending synastry email: {e}", exc_info=True)
        return False

