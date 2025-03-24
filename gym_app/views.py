from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.template.loader import render_to_string
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime, timedelta
import io
import os
from .models import Package, TrainerProfile, Specialization, CustomUser, PackageEnrollment, Attendance, Progress, Notes, Message
from .forms import UserRegistrationForm, UserProfileForm, NotesForm
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string

class PDF:
    def header(self):
        # Set font
        self.set_font('Arial', 'B', 15)
        # Title
        self.cell(0, 10, 'Gym Management System', 0, 1, 'C')
        # Line break
        self.ln(10)

    def footer(self):
        # Position cursor at 1.5 cm from bottom
        self.set_y(-15)
        # Set font
        self.set_font('Arial', 'I', 8)
        # Print centered page number
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def index(request):
    # Get active specializations
    specializations = Specialization.objects.filter(is_active=True)
    
    # Get active packages with trainer info
    packages = Package.objects.filter(is_active=True).select_related('trainer', 'trainer__user', 'trainer__specialization')
    
    # Get active trainers with their specializations
    trainers = TrainerProfile.objects.filter(is_active=True).select_related('user', 'specialization')
    
    # Calculate statistics
    stats = {
        'total_members': CustomUser.objects.filter(is_trainer=False, is_staff=False).count(),
        'total_trainers': TrainerProfile.objects.filter(is_active=True).count(),
        'total_packages': Package.objects.filter(is_active=True).count(),
        'specializations_count': Specialization.objects.filter(is_active=True).count(),
    }
    
    return render(request, 'gym_app/index.html', {
        'specializations': specializations,
        'packages': packages,
        'trainers': trainers,
        'stats': stats,
    })

def is_trainer(user):
    return user.is_trainer

def trainer_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            trainer = TrainerProfile.objects.get(user__username=username)
            if trainer.phone_number == password:
                login(request, trainer.user)
                return redirect('trainer_dashboard')
            else:
                messages.error(request, 'Invalid credentials')
        except TrainerProfile.DoesNotExist:
            messages.error(request, 'Trainer not found')
        
    return render(request, 'gym_app/trainer_login.html')

@login_required
def trainer_logout(request):
    logout(request)
    return redirect('index')

@login_required
@user_passes_test(is_trainer)
def trainer_dashboard(request):
    trainer = get_object_or_404(TrainerProfile, user=request.user)
    
    # Get all packages associated with this trainer
    packages = Package.objects.filter(trainer=trainer)
    
    # Get total active packages
    total_active_packages = packages.filter(is_active=True).count()
    
    # Get enrollment requests for this trainer's packages
    enrollment_requests = PackageEnrollment.objects.filter(
        package__trainer=trainer
    ).select_related('user', 'package').order_by('-enrollment_date')
    
    # Count pending requests
    pending_requests = enrollment_requests.filter(status='pending').count()
    
    # Get enrolled users for each package
    current_date = timezone.now().date()
    for package in packages:
        enrollments = PackageEnrollment.objects.filter(
            package=package,
            status='approved'
        ).select_related('user')
        
        # Add payment status and remaining days for each enrollment
        for enrollment in enrollments:
            if enrollment.end_date:
                remaining_days = (enrollment.end_date - current_date).days
                enrollment.remaining_days = max(0, remaining_days)
            else:
                enrollment.remaining_days = None
        
        package.enrolled_users = enrollments
    
    context = {
        'trainer': trainer,
        'packages': packages,
        'current_date': timezone.now().strftime('%B %d, %Y'),
        'total_packages': total_active_packages,
        'trainer_name': trainer.user.get_full_name(),
        'trainer_specialization': trainer.specialization,
        'trainer_experience': trainer.experience,
        'trainer_phone': trainer.phone_number,
        'enrollment_requests': enrollment_requests,
        'pending_requests': pending_requests
    }
    
    return render(request, 'gym_app/trainer_dashboard.html', context)

@login_required
@user_passes_test(is_trainer)
def add_package(request):
    if request.method == 'POST':
        trainer = get_object_or_404(TrainerProfile, user=request.user)
        package = Package.objects.create(
            trainer=trainer,
            name=request.POST.get('name'),
            duration=request.POST.get('duration'),
            price=request.POST.get('price'),
            description=request.POST.get('description'),
            is_active=request.POST.get('is_active') == 'true'
        )
        messages.success(request, 'Package added successfully!')
        return redirect('trainer_dashboard')
    return redirect('trainer_dashboard')

@login_required
@user_passes_test(is_trainer)
def delete_package(request, pk):
    if request.method == 'POST':
        package = get_object_or_404(Package, pk=pk, trainer__user=request.user)
        package.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
@user_passes_test(is_trainer)
def toggle_package_status(request, pk):
    if request.method == 'POST':
        package = get_object_or_404(Package, pk=pk, trainer__user=request.user)
        package.is_active = not package.is_active
        package.save()
        return JsonResponse({
            'success': True,
            'is_active': package.is_active
        })
    return JsonResponse({'success': False}, status=400)

@login_required
@user_passes_test(is_trainer)
def approve_enrollment(request, enrollment_id):
    if request.method == 'POST':
        enrollment = get_object_or_404(
            PackageEnrollment, 
            id=enrollment_id,
            package__trainer__user=request.user,
            status='pending'
        )
        enrollment.status = 'approved'
        enrollment.save()
        messages.success(request, f'Enrollment request for {enrollment.user.get_full_name()} has been approved.')
    return redirect('trainer_dashboard')

@login_required
@user_passes_test(is_trainer)
def reject_enrollment(request, enrollment_id):
    if request.method == 'POST':
        enrollment = get_object_or_404(
            PackageEnrollment, 
            id=enrollment_id,
            package__trainer__user=request.user,
            status='pending'
        )
        # Get the user before changing status
        user = enrollment.user
        
        # Update the enrollment status
        enrollment.status = 'rejected'
        enrollment.save()
        
        # Send a message to the user
        messages.warning(
            request, 
            f'Enrollment request for {enrollment.user.get_full_name()} has been rejected. The user will be able to select a different package.'
        )
        
        # Create a notification for the user
        messages.error(
            request._request if hasattr(request, '_request') else request,
            f'Your enrollment request for {enrollment.package.name} has been rejected by the trainer. Please select a different package.',
            extra_tags='user_{}'.format(user.id)
        )
    return redirect('trainer_dashboard')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        
        if user is not None and not user.is_trainer and not user.is_staff:
            login(request, user)
            messages.success(request, 'Successfully logged in!')
            
            # Check if user has an active enrollment
            active_enrollment = PackageEnrollment.objects.filter(
                user=user,
                status='approved',
                payment_status=True
            ).exists()
            
            if active_enrollment:
                return redirect('user_activity_dashboard')
            else:
                return redirect('user_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'gym_app/login.html')

def user_register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if not user.username:
                base_username = f"{user.first_name.lower()}{user.last_name.lower()}"
                username = base_username
                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                user.username = username
            user.save()
            
            # Send welcome email
            subject = 'Welcome to FitLife Gym!'
            html_message = render_to_string('gym_app/email/welcome_email.html', {
                'user': user,
                'gym_name': 'FitLife Gym',
                'gym_address': 'Kattappana',
                'gym_phone': '+9605940327',
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=html_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            login(request, user)
            messages.success(request, 'Registration successful! Welcome email has been sent to your email address.')
            return redirect('user_dashboard')
        else:
            for field in form.errors:
                for error in form[field].errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    return render(request, 'gym_app/register.html', {'form': form})

@login_required
def user_dashboard(request):
    if request.user.is_trainer:
        return redirect('trainer_dashboard')
    
    # Get user's enrollments
    enrollments = PackageEnrollment.objects.filter(user=request.user)
    
    # Base context that's always needed
    context = {
        'user': request.user,
        'user_enrollments': enrollments,
        'packages': Package.objects.filter(is_active=True),
        'trainers': TrainerProfile.objects.filter(is_active=True),
    }
    
    # Check for active (non-rejected) enrollments
    active_enrollment = enrollments.filter(status__in=['pending', 'approved'], payment_status=False).first()
    if active_enrollment:
        if active_enrollment.status == 'approved' and active_enrollment.payment_status:
            # Check if attendance is marked for today
            today_attendance = Attendance.objects.filter(
                enrollment=active_enrollment,
                date=timezone.now().date()
            ).exists()
            
            # Get progress entries
            progress_entries = Progress.objects.filter(enrollment=active_enrollment)
            
            context.update({
                'today_attendance': today_attendance,
                'progress_entries': progress_entries,
                'show_packages': False
            })
        else:
            context['show_packages'] = False
    else:
        # Show packages if no active enrollments or all are rejected
        context['show_packages'] = True
        
        # Get rejected enrollments for display
        rejected_enrollments = enrollments.filter(status='rejected')
        if rejected_enrollments.exists():
            context['rejected_enrollments'] = rejected_enrollments
    
    return render(request, 'gym_app/user_dashboard.html', context)

def user_logout(request):
    logout(request)
    messages.success(request, 'Successfully logged out!')
    return redirect('index')

@login_required
def enroll_package(request, package_id):
    package = get_object_or_404(Package, id=package_id, is_active=True)
    
    if request.method == 'POST':
        # Check if user already has a pending enrollment for this package
        existing_enrollment = PackageEnrollment.objects.filter(
            user=request.user,
            package=package,
            status='pending'
        ).exists()
        
        if existing_enrollment:
            messages.warning(request, 'You already have a pending enrollment request for this package.')
            return redirect('package_list')
        
        # Create new enrollment request
        enrollment = PackageEnrollment.objects.create(
            user=request.user,
            package=package
        )
        
        # Notify admin and trainer
        # TODO: Implement email notifications
        messages.success(request, 'Your enrollment request has been submitted successfully! We will contact you soon.')
        return redirect('user_dashboard')
        
    return render(request, 'gym_app/package_detail.html', {'package': package})

@login_required
def package_list(request):
    packages = Package.objects.filter(is_active=True)
    user_enrollments = PackageEnrollment.objects.filter(user=request.user)
    
    context = {
        'packages': packages,
        'user_enrollments': user_enrollments
    }
    return render(request, 'gym_app/package_list.html', context)

@login_required
def user_enrollments(request):
    enrollments = PackageEnrollment.objects.filter(user=request.user)
    return render(request, 'gym_app/user_enrollments.html', {'enrollments': enrollments})

@login_required
def trainer_enrollments(request):
    if not request.user.is_trainer:
        messages.error(request, 'Access denied.')
        return redirect('home')
        
    trainer_profile = request.user.trainerprofile
    enrollments = PackageEnrollment.objects.filter(
        package__trainer=trainer_profile
    ).select_related('user', 'package')
    
    return render(request, 'gym_app/trainer_enrollments.html', {'enrollments': enrollments})

@login_required
def process_payment(request, enrollment_id):
    enrollment = get_object_or_404(PackageEnrollment, id=enrollment_id, user=request.user)
    
    if enrollment.payment_status:
        messages.warning(request, 'Payment has already been completed.')
        return redirect('user_dashboard')
    
    # Initialize Razorpay client
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    # Create Razorpay order if not already created
    if not enrollment.razorpay_order_id:
        data = {
            'amount': enrollment.get_amount_in_paise(),
            'currency': settings.RAZORPAY_CURRENCY,
            'receipt': f'receipt_{enrollment.id}',
            'notes': {
                'package_name': enrollment.package.name,
                'user_email': enrollment.user.email,
            }
        }
        
        # Create order
        razorpay_order = client.order.create(data=data)
        enrollment.razorpay_order_id = razorpay_order['id']
        enrollment.save()
    
    # Prepare payment data for template
    payment_data = {
        'key': settings.RAZORPAY_KEY_ID,
        'amount': enrollment.get_amount_in_paise(),
        'currency': settings.RAZORPAY_CURRENCY,
        'name': 'FitLife Gym',
        'description': f'Payment for {enrollment.package.name}',
        'order_id': enrollment.razorpay_order_id,
        'callback_url': request.build_absolute_uri(reverse('payment_callback')),
        'prefill': {
            'name': request.user.get_full_name(),
            'email': request.user.email,
            'contact': request.user.phone_number,
        },
        'notes': {
            'package_name': enrollment.package.name,
            'enrollment_id': enrollment.id,
        }
    }
    
    return render(request, 'gym_app/payment.html', {
        'enrollment': enrollment,
        'payment_data': payment_data
    })

@csrf_exempt
@login_required
def payment_callback(request):
    if request.method == "POST":
        try:
            # Get the payment details from POST data
            payment_id = request.POST.get('razorpay_payment_id', '')
            order_id = request.POST.get('razorpay_order_id', '')
            signature = request.POST.get('razorpay_signature', '')
            
            # Initialize Razorpay client
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Verify payment signature
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            }
            
            try:
                client.utility.verify_payment_signature(params_dict)
                
                # Get enrollment by order_id
                enrollment = PackageEnrollment.objects.get(razorpay_order_id=order_id)
                
                # Update enrollment
                enrollment.payment_status = True
                enrollment.payment_date = timezone.now()
                enrollment.razorpay_payment_id = payment_id
                enrollment.razorpay_signature = signature
                enrollment.start_date = timezone.now().date()
                enrollment.end_date = timezone.now().date() + timezone.timedelta(days=30)  # Assuming 30 days package
                enrollment.save()
                
                messages.success(request, 'Payment successful! You can now access your activity dashboard.')
                return redirect('user_activity_dashboard')
                
            except Exception as e:
                messages.error(request, 'Payment verification failed. Please contact support.')
                return redirect('user_dashboard')
                
        except Exception as e:
            messages.error(request, 'Something went wrong. Please try again or contact support.')
            return redirect('user_dashboard')
    
    return redirect('user_dashboard')

@login_required
def user_activity_dashboard(request):
    try:
        # Get user's active enrollment
        enrollment = PackageEnrollment.objects.filter(
            user=request.user,
            status='approved',
            payment_status=True
        ).select_related('package', 'package__trainer').order_by('-enrollment_date').first()
        
        if not enrollment:
            messages.warning(request, 'No active enrollment found.')
            return redirect('user_dashboard')
            
        # Get trainer information
        trainer_profile = enrollment.package.trainer
        if not trainer_profile:
            messages.error(request, 'No trainer assigned to your package.')
            return redirect('user_dashboard')
        
        # Calculate total days based on package duration
        duration_mapping = {
            '1': 30,  # 1 month = 30 days
            '3': 90,  # 3 months = 90 days
            '6': 180, # 6 months = 180 days
            '12': 365 # 12 months = 365 days
        }
        total_days = duration_mapping.get(enrollment.package.duration, 30)
        
        # Get attendance records
        attendance_history = Attendance.objects.filter(
            enrollment=enrollment
        ).order_by('-date')
        
        # Check today's attendance
        today = timezone.now().date()
        today_attendance = attendance_history.filter(date=today).first()
        
        # Calculate progress
        days_attended = attendance_history.count()
        progress_percentage = min(round((days_attended / total_days) * 100), 100)
        
        # Get payment history
        payment_history = PackageEnrollment.objects.filter(
            user=request.user,
            payment_status=True
        ).select_related('package').order_by('-payment_date')
        
        context = {
            'active_enrollment': enrollment,
            'trainer_profile': trainer_profile,
            'attendance_history': attendance_history,
            'today_attendance': today_attendance,
            'days_attended': days_attended,
            'total_days': total_days,
            'progress_percentage': progress_percentage,
            'payment_history': payment_history,
        }
        
        return render(request, 'gym_app/user_activity_dashboard.html', context)
        
    except Exception as e:
        print(f"Error in user_activity_dashboard: {str(e)}")  # For debugging
        messages.error(request, 'An error occurred while loading your dashboard.')
        return redirect('user_dashboard')

@login_required
def mark_attendance(request):
    if request.method == 'POST':
        try:
            # Get user's active enrollment
            enrollment = PackageEnrollment.objects.get(
                user=request.user,
                status='approved',
                payment_status=True
            )
            
            # Check if attendance already marked for today
            today = timezone.now().date()
            if not Attendance.objects.filter(enrollment=enrollment, date=today).exists():
                Attendance.objects.create(enrollment=enrollment)
                messages.success(request, 'Attendance marked successfully!')
            else:
                messages.warning(request, 'Attendance already marked for today!')
                
        except PackageEnrollment.DoesNotExist:
            messages.error(request, 'No active enrollment found!')
            
    return redirect('user_activity_dashboard')

@login_required
def update_progress(request):
    if request.method == 'POST':
        try:
            # Get user's active enrollment
            enrollment = PackageEnrollment.objects.get(
                user=request.user,
                status='approved',
                payment_status=True
            )
            
            # Create progress entry
            Progress.objects.create(
                enrollment=enrollment,
                workout_notes=request.POST.get('workout_notes'),
                duration=request.POST.get('duration'),
                energy_level=request.POST.get('energy_level')
            )
            
            messages.success(request, 'Progress updated successfully!')
            
        except PackageEnrollment.DoesNotExist:
            messages.error(request, 'No active enrollment found!')
            
    return redirect('user_activity_dashboard')

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'gym_app/profile_form.html', {'form': form})

@login_required
def download_attendance_pdf(request):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_history_{timezone.now().strftime("%Y%m%d")}.pdf"'
    
    # Create the PDF object using reportlab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    
    # Add title
    elements.append(Paragraph('Attendance History', title_style))
    elements.append(Paragraph(f'User: {request.user.get_full_name()}', normal_style))
    elements.append(Paragraph(f'Generated on: {timezone.now().strftime("%B %d, %Y")}', normal_style))
    elements.append(Spacer(1, 12))
    
    # Get enrollment
    enrollment = PackageEnrollment.objects.filter(
        user=request.user,
        status='approved',
        payment_status=True
    ).order_by('-enrollment_date').first()
    
    if enrollment:
        # Get all dates from enrollment start to today
        start_date = enrollment.start_date
        end_date = min(enrollment.end_date or timezone.now().date(), timezone.now().date())
        
        if not start_date:
            elements.append(Paragraph('Enrollment start date not set.', normal_style))
            doc.build(elements)
            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)
            return response
        
        # Get all attendance records
        attendance_records = {
            attendance.date: attendance.time 
            for attendance in Attendance.objects.filter(enrollment=enrollment)
        }
        
        # Create table data
        data = [['Date', 'Time', 'Status']]  # Header row
        
        current_date = start_date
        while current_date <= end_date:
            if current_date in attendance_records:
                data.append([
                    current_date.strftime('%B %d, %Y'),
                    attendance_records[current_date].strftime('%I:%M %p'),
                    'Present'
                ])
            else:
                data.append([
                    current_date.strftime('%B %d, %Y'),
                    '-',
                    'Absent'
                ])
            current_date += timedelta(days=1)
        
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            # Color code for present/absent
            ('TEXTCOLOR', (-1, 1), (-1, -1), colors.HexColor('#006400')),  # Dark green for Present
            ('BACKGROUND', (-1, 1), (-1, -1), colors.HexColor('#FFFFFF')),  # White background
        ]))
        
        # Conditionally color absent rows
        for i in range(1, len(data)):
            if data[i][2] == 'Absent':
                table.setStyle(TableStyle([
                    ('TEXTCOLOR', (-1, i), (-1, i), colors.red),  # Red text for Absent
                ]))
        
        elements.append(table)
    else:
        elements.append(Paragraph('No active enrollment found.', normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

@login_required
def download_payment_pdf(request):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payment_history_{timezone.now().strftime("%Y%m%d")}.pdf"'
    
    # Create the PDF object using reportlab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    
    # Add title
    elements.append(Paragraph('Payment History', title_style))
    elements.append(Paragraph(f'User: {request.user.get_full_name()}', normal_style))
    elements.append(Paragraph(f'Generated on: {timezone.now().strftime("%B %d, %Y")}', normal_style))
    elements.append(Spacer(1, 12))
    
    # Get payment data
    payment_history = PackageEnrollment.objects.filter(
        user=request.user,
        payment_status=True
    ).select_related('package').order_by('-payment_date')
    
    # Create table data
    data = [['Package', 'Amount', 'Payment Date', 'Status']]  # Header row
    for payment in payment_history:
        data.append([
            payment.package.name,
            f'₹{payment.package.price}',
            payment.payment_date.strftime('%B %d, %Y'),
            'Paid'
        ])
    
    # Create table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

@login_required
def notes_list(request):
    notes = Notes.objects.filter(user=request.user)
    context = {
        'notes': notes,
    }
    return render(request, 'gym_app/notes_list.html', context)

@login_required
def add_note(request):
    if request.method == 'POST':
        form = NotesForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, 'Note added successfully!')
            return redirect('notes_list')
    else:
        form = NotesForm()
    
    context = {
        'form': form,
        'title': 'Add Note'
    }
    return render(request, 'gym_app/note_form.html', context)

@login_required
def edit_note(request, pk):
    note = get_object_or_404(Notes, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = NotesForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, 'Note updated successfully!')
            return redirect('notes_list')
    else:
        form = NotesForm(instance=note)
    
    context = {
        'form': form,
        'title': 'Edit Note'
    }
    return render(request, 'gym_app/note_form.html', context)

@login_required
def delete_note(request, pk):
    note = get_object_or_404(Notes, pk=pk, user=request.user)
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note deleted successfully!')
        return redirect('notes_list')
    return render(request, 'gym_app/note_confirm_delete.html', {'note': note})

def about(request):
    """View function for the about page."""
    return render(request, 'gym_app/about.html')
def packages(request):
    """View function for displaying all available packages."""
    all_packages = Package.objects.all()
    return render(request, 'gym_app/packages.html', {'packages': all_packages})

def trainers(request):
    """View function for displaying all trainers."""
    all_trainers = TrainerProfile.objects.select_related('user', 'specialization').prefetch_related('package_set').all()
    return render(request, 'gym_app/trainers.html', {'trainers': all_trainers})

def contact(request):
    """View function for the contact page."""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        # Here you would typically save the contact form data or send an email
        messages.success(request, 'Thank you for your message. We will get back to you soon!')
        return redirect('contact')
    return render(request, 'gym_app/contact.html')

def privacy(request):
    """View function for the privacy policy page."""
    return render(request, 'gym_app/privacy.html')

@login_required
def send_message(request):
    """Send a message to another user."""
    if request.method == 'POST':
        try:
            receiver_id = request.POST.get('receiver_id')
            content = request.POST.get('content')
            
            if not receiver_id or not content:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Receiver ID and content are required'
                }, status=400)

            try:
                receiver = CustomUser.objects.get(id=receiver_id)
            except CustomUser.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Receiver not found'
                }, status=404)
            
            # Create the message
            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Message sent successfully',
                'data': {
                    'id': message.id,
                    'content': message.content,
                    'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        except Exception as e:
            print(f"Error in send_message: {str(e)}")  # For debugging
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred while sending the message'
            }, status=500)
            
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

@login_required
def get_messages(request, user_id):
    """Get messages between the current user and another user."""
    try:
        other_user = get_object_or_404(CustomUser, id=user_id)
        
        # Get messages between the two users
        messages = Message.objects.filter(
            (Q(sender=request.user, receiver=other_user) |
             Q(sender=other_user, receiver=request.user))
        ).order_by('timestamp')
        
        # Mark received messages as read
        messages.filter(receiver=request.user, is_read=False).update(is_read=True)
        
        # Format messages for JSON response
        messages_data = [{
            'id': msg.id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_sender': msg.sender == request.user
        } for msg in messages]
        
        return JsonResponse({
            'status': 'success',
            'messages': messages_data
        })
    except Exception as e:
        print(f"Error in get_messages: {str(e)}")  # For debugging
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while fetching messages'
        }, status=500)

@login_required
def get_unread_message_count(request):
    count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return JsonResponse({'count': count})
