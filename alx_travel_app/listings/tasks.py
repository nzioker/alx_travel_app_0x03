import os
import django
from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alx_travel_app.settings')
django.setup()

from listings.models import Booking, Listing, Payment

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmation_email(self, booking_id, user_id):
    """
    Send booking confirmation email asynchronously
    
    Args:
        booking_id (int): ID of the booking
        user_id (int): ID of the user
    
    Returns:
        dict: Task result
    """
    try:
        # Get booking and user
        booking = Booking.objects.select_related('listing', 'user').get(id=booking_id)
        user = User.objects.get(id=user_id)
        
        # Prepare email content
        subject = f'ALX Travel - Booking Confirmation #{booking.id}'
        
        # HTML content
        html_content = render_to_string('emails/booking_confirmation.html', {
            'booking': booking,
            'user': user,
            'listing': booking.listing,
            'created_at': booking.created_at,
        })
        
        # Plain text content (fallback)
        text_content = f"""
        Dear {user.get_full_name() or user.username},
        
        Thank you for your booking with ALX Travel!
        
        Booking Details:
        - Booking ID: {booking.id}
        - Listing: {booking.listing.title}
        - Location: {booking.listing.city}, {booking.listing.country}
        - Check-in: {booking.check_in}
        - Check-out: {booking.check_out}
        - Number of Guests: {booking.number_of_guests}
        - Total Price: ${booking.total_price}
        
        We hope you enjoy your stay!
        
        Best regards,
        The ALX Travel Team
        """
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            cc=['bookings@alxtravel.com'],  # Optional: CC to admin
            reply_to=['support@alxtravel.com'],
        )
        email.attach_alternative(html_content, "text/html")
        
        # Optional: Attach PDF invoice
        # from django.core.files.base import ContentFile
        # from reportlab.pdfgen import canvas
        # pdf_content = generate_booking_pdf(booking)
        # email.attach(f'booking_{booking.id}.pdf', pdf_content, 'application/pdf')
        
        email.send(fail_silently=False)
        
        # Update booking status
        booking.confirmation_email_sent = True
        booking.confirmation_sent_at = timezone.now()
        booking.save(update_fields=['confirmation_email_sent', 'confirmation_sent_at'])
        
        # Log success
        logger.info(f'Confirmation email sent for booking #{booking.id} to {user.email}')
        
        return {
            'status': 'success',
            'message': f'Confirmation email sent for booking #{booking.id}',
            'booking_id': booking.id,
            'user_email': user.email,
            'sent_at': timezone.now().isoformat(),
        }
        
    except Exception as exc:
        logger.error(f'Failed to send confirmation email for booking #{booking_id}: {exc}')
        
        # Retry the task
        raise self.retry(exc=exc)

@shared_task
def send_payment_confirmation_email(payment_id):
    """
    Send payment confirmation email
    
    Args:
        payment_id (int): ID of the payment
    
    Returns:
        dict: Task result
    """
    try:
        payment = Payment.objects.select_related('booking', 'booking__user', 'booking__listing').get(id=payment_id)
        booking = payment.booking
        user = booking.user
        
        subject = f'ALX Travel - Payment Confirmation for Booking #{booking.id}'
        
        html_content = render_to_string('emails/payment_confirmation.html', {
            'payment': payment,
            'booking': booking,
            'user': user,
            'listing': booking.listing,
        })
        
        text_content = f"""
        Dear {user.get_full_name() or user.username},
        
        Your payment has been successfully processed!
        
        Payment Details:
        - Transaction ID: {payment.tx_ref}
        - Amount: ${payment.amount}
        - Booking ID: {booking.id}
        - Listing: {booking.listing.title}
        - Payment Date: {payment.created_at}
        
        Thank you for choosing ALX Travel!
        """
        
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )
        
        # Update payment status
        payment.confirmation_email_sent = True
        payment.save(update_fields=['confirmation_email_sent'])
        
        logger.info(f'Payment confirmation email sent for payment #{payment.id}')
        
        return {
            'status': 'success',
            'message': f'Payment confirmation email sent for payment #{payment.id}',
            'payment_id': payment.id,
        }
        
    except Exception as e:
        logger.error(f'Failed to send payment confirmation email: {e}')
        raise

@shared_task
def send_booking_reminders():
    """
    Send reminders for upcoming bookings (daily task)
    """
    try:
        tomorrow = timezone.now().date() + timezone.timedelta(days=1)
        
        # Find bookings with check-in tomorrow
        upcoming_bookings = Booking.objects.filter(
            check_in=tomorrow,
            confirmation_email_sent=True,
            reminder_email_sent=False,
            status='confirmed'
        ).select_related('user', 'listing')
        
        count = 0
        for booking in upcoming_bookings:
            user = booking.user
            
            subject = f'ALX Travel - Reminder: Your Booking Starts Tomorrow!'
            
            html_content = render_to_string('emails/booking_reminder.html', {
                'booking': booking,
                'user': user,
                'listing': booking.listing,
            })
            
            text_content = f"""
            Dear {user.get_full_name() or user.username},
            
            This is a reminder that your booking starts tomorrow!
            
            Booking Details:
            - Booking ID: {booking.id}
            - Listing: {booking.listing.title}
            - Address: {booking.listing.address}
            - Check-in: {booking.check_in}
            - Check-out: {booking.check_out}
            
            Please contact the host if you have any questions.
            
            Enjoy your stay!
            """
            
            send_mail(
                subject=subject,
                message=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=False,
            )
            
            booking.reminder_email_sent = True
            booking.save(update_fields=['reminder_email_sent'])
            count += 1
        
        logger.info(f'Sent {count} booking reminders for check-ins on {tomorrow}')
        return {
            'status': 'success',
            'message': f'Sent {count} booking reminders',
            'date': tomorrow.isoformat(),
            'count': count,
        }
        
    except Exception as e:
        logger.error(f'Failed to send booking reminders: {e}')
        raise

@shared_task
def cleanup_old_celery_tasks():
    """
    Clean up old Celery task results (daily maintenance task)
    """
    try:
        from django_celery_results.models import TaskResult
        from datetime import timedelta
        
        # Delete task results older than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count, _ = TaskResult.objects.filter(date_done__lt=cutoff_date).delete()
        
        logger.info(f'Cleaned up {deleted_count} old Celery task results')
        return {
            'status': 'success',
            'message': f'Cleaned up {deleted_count} old task results',
            'deleted_count': deleted_count,
        }
        
    except Exception as e:
        logger.error(f'Failed to cleanup old Celery tasks: {e}')
        raise

@shared_task
def send_admin_notification(notification_type, data):
    """
    Send notification to admin about important events
    
    Args:
        notification_type (str): Type of notification
        data (dict): Notification data
    
    Returns:
        dict: Task result
    """
    try:
        subject = f'ALX Travel Admin Notification: {notification_type}'
        
        html_content = render_to_string('emails/admin_notification.html', {
            'notification_type': notification_type,
            'data': data,
            'timestamp': timezone.now(),
        })
        
        text_content = f"""
        Admin Notification: {notification_type}
        
        Data: {data}
        
        Timestamp: {timezone.now()}
        """
        
        # Send to admin email(s)
        admin_emails = ['admin@alxtravel.com', 'operations@alxtravel.com']
        
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            html_message=html_content,
            fail_silently=False,
        )
        
        logger.info(f'Sent admin notification: {notification_type}')
        return {
            'status': 'success',
            'message': f'Admin notification sent: {notification_type}',
        }
        
    except Exception as e:
        logger.error(f'Failed to send admin notification: {e}')
        raise
