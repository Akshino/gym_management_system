from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    # User URLs
    path('register/', views.user_register, name='user_register'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('update-profile/', views.update_profile, name='update_profile'),
    
    # Password Reset URLs
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # Package enrollment URLs
    path('packages/', views.package_list, name='package_list'),
    path('package/<int:package_id>/enroll/', views.enroll_package, name='enroll_package'),
    path('my-enrollments/', views.user_enrollments, name='user_enrollments'),
    path('trainer/enrollments/', views.trainer_enrollments, name='trainer_enrollments'),
    # Enrollment approval/rejection URLs
    path('trainer/enrollment/<int:enrollment_id>/approve/', views.approve_enrollment, name='approve_enrollment'),
    path('trainer/enrollment/<int:enrollment_id>/reject/', views.reject_enrollment, name='reject_enrollment'),
    # Payment URLs
    path('enrollment/<int:enrollment_id>/payment/', views.process_payment, name='process_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    # Progress URLs
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('progress/update/', views.update_progress, name='update_progress'),
    path('activity-dashboard/', views.user_activity_dashboard, name='user_activity_dashboard'),
    # Trainer URLs
    path('trainer/login/', views.trainer_login, name='trainer_login'),
    path('trainer/logout/', views.trainer_logout, name='trainer_logout'),
    path('trainer/dashboard/', views.trainer_dashboard, name='trainer_dashboard'),
    path('trainer/add-package/', views.add_package, name='add_package'),
    path('trainer/delete-package/<int:pk>/', views.delete_package, name='delete_package'),
    path('trainer/toggle-package-status/<int:pk>/', views.toggle_package_status, name='toggle_package_status'),
    # Notes URLs
    path('notes/', views.notes_list, name='notes_list'),
    path('notes/add/', views.add_note, name='add_note'),
    path('notes/<int:pk>/edit/', views.edit_note, name='edit_note'),
    path('notes/<int:pk>/delete/', views.delete_note, name='delete_note'),
    # PDF Download URLs
    path('download/attendance/', views.download_attendance_pdf, name='download_attendance_pdf'),
    path('download/payment/', views.download_payment_pdf, name='download_payment_pdf'),

    path('about/', views.about, name='about'),
    path('packages/', views.packages, name='packages'),
    path('trainers/', views.trainers, name='trainers'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
    # Message URLs
    path('send-message/', views.send_message, name='send_message'),
    path('get-messages/<int:user_id>/', views.get_messages, name='get_messages'),
    path('unread-message-count/', views.get_unread_message_count, name='unread_message_count'),
]
