# ALX Travel App with Celery & RabbitMQ

This project implements background task processing with Celery and RabbitMQ for the ALX Travel booking application.

## Features

- Asynchronous email notifications for bookings
- Payment confirmation emails
- Booking reminders
- Admin notifications
- Task monitoring and management

## Prerequisites

- Python 3.8+
- Django 4.0+
- RabbitMQ
- PostgreSQL (or your preferred database)
- Redis (optional, for result backend)

## Installation

### 1. Clone and Setup Project

```bash
# Clone the project
git clone <repository-url>
cd alx_travel_app_0x03

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
