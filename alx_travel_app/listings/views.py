from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Booking, Listing, Payment
from .serializers import BookingSerializer, PaymentSerializer
from .tasks import send_booking_confirmation_email, send_payment_confirmation_email
import logging

logger = logging.getLogger(__name__)

class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling booking operations
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return only bookings for the current user"""
        return self.queryset.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create booking and trigger confirmation email"""
        booking = serializer.save(user=self.request.user)
        
        # Trigger confirmation email as background task
        try:
            task = send_booking_confirmation_email.delay(booking.id, self.request.user.id)
            logger.info(f'Triggered confirmation email task for booking #{booking.id}. Task ID: {task.id}')
        except Exception as e:
            logger.error(f'Failed to trigger confirmation email task: {e}')
            # Don't raise - booking should still be created
        
        return booking
    
    def create(self, request, *args, **kwargs):
        """Override create to include task info in response"""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            booking_id = response.data.get('id')
            response.data['message'] = 'Booking created successfully. Confirmation email will be sent shortly.'
        
        return response
    
    @action(detail=True, methods=['post'])
    def resend_confirmation(self, request, pk=None):
        """Resend confirmation email"""
        booking = self.get_object()
        
        try:
            task = send_booking_confirmation_email.delay(booking.id, request.user.id)
            return Response({
                'status': 'success',
                'message': 'Confirmation email will be resent shortly.',
                'task_id': task.id,
            })
        except Exception as e:
            logger.error(f'Failed to resend confirmation email: {e}')
            return Response({
                'status': 'error',
                'message': 'Failed to resend confirmation email.',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def task_status(self, request, pk=None):
        """Check status of email tasks for this booking"""
        from celery.result import AsyncResult
        from alx_travel_app.celery import app
        
        booking = self.get_object()
        task_ids = []
        
        # Get all tasks for this booking (you'd need to store task IDs)
        # This is a simplified example
        
        return Response({
            'booking_id': booking.id,
            'tasks': task_ids,
        })

class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling payment operations
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Create payment and trigger confirmation email"""
        payment = serializer.save()
        
        # Trigger payment confirmation email
        try:
            task = send_payment_confirmation_email.delay(payment.id)
            logger.info(f'Triggered payment confirmation email task. Task ID: {task.id}')
        except Exception as e:
            logger.error(f'Failed to trigger payment confirmation email task: {e}')
        
        return payment
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark payment as complete and trigger emails"""
        payment = self.get_object()
        
        if payment.status == 'completed':
            return Response({
                'error': 'Payment already completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update payment status
        payment.status = 'completed'
        payment.completed_at = timezone.now()
        payment.save()
        
        # Trigger booking confirmation email
        try:
            send_booking_confirmation_email.delay(payment.booking.id, payment.booking.user.id)
        except Exception as e:
            logger.error(f'Failed to trigger booking confirmation: {e}')
        
        # Trigger payment confirmation email
        try:
            send_payment_confirmation_email.delay(payment.id)
        except Exception as e:
            logger.error(f'Failed to trigger payment confirmation: {e}')
        
        return Response({
            'status': 'success',
            'message': 'Payment completed and confirmation emails triggered',
            'payment_id': payment.id,
        })
