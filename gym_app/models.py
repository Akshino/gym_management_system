from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import uuid

# Create your models here.

class CustomUser(AbstractUser):
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=False)
    is_trainer = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.get_full_name() or self.username

class Specialization(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class TrainerProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='trainer_profiles/', null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    specialization = models.ForeignKey(Specialization, on_delete=models.SET_NULL, null=True)
    experience = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    available_time_slots = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            self.user.is_trainer = True
            self.user.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.specialization}"

class Package(models.Model):
    DURATION_CHOICES = [
        ('1', '1 Month'),
        ('3', '3 Months'),
        ('6', '6 Months'),
        ('12', '12 Months'),
    ]
    
    name = models.CharField(max_length=100)
    trainer = models.ForeignKey(TrainerProfile, on_delete=models.CASCADE)
    duration = models.CharField(max_length=2, choices=DURATION_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    features = models.TextField(help_text='Enter features separated by newlines')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} by {self.trainer.user.get_full_name()} - {self.get_duration_display()}"

class PackageEnrollment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='enrollments')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Razorpay payment fields
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.package.name}"

    def get_amount_in_paise(self):
        # Razorpay expects amount in paise (1 INR = 100 paise)
        return int(self.package.price * 100)

    class Meta:
        ordering = ['-enrollment_date']
        unique_together = ['user', 'package', 'status']

class Attendance(models.Model):
    enrollment = models.ForeignKey(PackageEnrollment, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)

    class Meta:
        unique_together = ['enrollment', 'date']

    def __str__(self):
        return f"{self.enrollment.user.get_full_name()} - {self.date}"

class Progress(models.Model):
    ENERGY_CHOICES = [
        (1, 'Low'),
        (2, 'Below Average'),
        (3, 'Average'),
        (4, 'Good'),
        (5, 'Excellent'),
    ]

    enrollment = models.ForeignKey(PackageEnrollment, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    workout_notes = models.TextField()
    duration = models.PositiveIntegerField(help_text='Duration in minutes')
    energy_level = models.IntegerField(choices=ENERGY_CHOICES)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Progress Entries'

    def __str__(self):
        return f"{self.enrollment.user.get_full_name()} - {self.date}"

class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender} to {self.receiver} at {self.timestamp}"

class Notes(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
