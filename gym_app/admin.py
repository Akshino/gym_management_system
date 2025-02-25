from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html
from django import forms
from .models import CustomUser, TrainerProfile, Package, Specialization, PackageEnrollment
from .forms import TrainerProfileForm
from django.shortcuts import render
from django.http import JsonResponse
import json
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.urls import path

User = get_user_model()

# Custom Form for Trainer Creation
class TrainerCreationForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=15, required=True, help_text='This will be used as the password')
    specialization = forms.ModelChoiceField(queryset=Specialization.objects.filter(is_active=True), required=True)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'specialization')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["phone_number"])
        user.is_trainer = True
        if commit:
            user.save()
            TrainerProfile.objects.create(
                user=user,
                specialization=self.cleaned_data['specialization'],
                experience=0,
                available_time_slots='9 AM - 6 PM',
            )
        return user

class GymAdminSite(AdminSite):
    site_header = 'FitLife Gym Management'
    site_title = 'FitLife Gym Admin'
    index_title = 'Gym Management Dashboard'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('revenue-details/', self.revenue_details_view, name='revenue_details'),
        ]
        return custom_urls + urls

    def revenue_details_view(self, request):
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Get all approved enrollments with related data
        enrollments = PackageEnrollment.objects.filter(status='approved').select_related(
            'user', 'package'
        ).order_by('-enrollment_date')
        
        # Format the data for the response
        revenue_data = []
        for enrollment in enrollments:
            revenue_data.append({
                'date': enrollment.enrollment_date.isoformat(),
                'member': f"{enrollment.user.first_name} {enrollment.user.last_name}",
                'package': enrollment.package.name,
                'amount': enrollment.package.price
            })
        
        return JsonResponse(revenue_data, safe=False)
    
    def index(self, request, extra_context=None):
        from django.db.models import Count, Q
        from django.db.models.functions import TruncMonth
        import json

        # Get base queryset for each model
        users = CustomUser.objects.all()
        trainers = TrainerProfile.objects.all()
        packages = Package.objects.all()
        enrollments = PackageEnrollment.objects.all()
        
        # Get monthly enrollment statistics for the line graph
        monthly_stats = (
            enrollments
            .annotate(month=TruncMonth('enrollment_date'))
            .values('month')
            .annotate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected'))
            )
            .order_by('month')
        )

        # Convert monthly stats to list for JSON serialization
        monthly_data = []
        for stat in monthly_stats:
            monthly_data.append({
                'month': stat['month'].isoformat(),
                'total': stat['total'],
                'pending': stat['pending'],
                'approved': stat['approved'],
                'rejected': stat['rejected']
            })
        
        # Get package enrollment statistics for pie chart
        package_stats = (
            enrollments
            .filter(status='approved')
            .values('package__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Convert package stats to list and ensure proper JSON serialization
        package_data = []
        for stat in package_stats:
            if stat['package__name'] and stat['count'] > 0:
                package_data.append({
                    'package__name': stat['package__name'],
                    'count': stat['count']
                })
        
        print("DEBUG - Package Data:", json.dumps(package_data))
        
        # Calculate revenue from approved enrollments
        total_revenue = sum(
            enrollment.package.price
            for enrollment in enrollments.filter(status='approved')
        )
        
        # Calculate statistics
        context = {
            'total_members': users.count(),
            'active_trainers': trainers.filter(is_active=True).count(),
            'total_packages': packages.filter(is_active=True).count(),
            'total_enrollments': enrollments.filter(status='approved').count(),
            'total_revenue': total_revenue,
            'monthly_enrollment_data': monthly_data,
            'package_enrollment_data': package_data,
            'recent_enrollments': enrollments.select_related('user', 'package').order_by('-enrollment_date')[:5],
        }
        
        if extra_context:
            context.update(extra_context)
        
        return super().index(request, context)

# Register the custom admin site
admin_site = GymAdminSite(name='gym_admin')

# Custom Admin Classes
from django.contrib.auth.admin import UserAdmin
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'is_staff', 'is_trainer')
    list_filter = ('is_staff', 'is_trainer', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    ordering = ('username',)

admin_site.register(CustomUser, CustomUserAdmin)

@admin.register(Specialization, site=admin_site)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    # search_fields = ('name',)
    # list_filter = ('is_active',)

    def response_add(self, request, obj, post_url_continue=None):
        if '_popup' in request.POST:
            return self.response_popup(request, obj)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if '_popup' in request.POST:
            return self.response_popup(request, obj)
        return super().response_change(request, obj)

    def response_popup(self, request, obj):
        opts = obj._meta
        to_field = request.POST.get('_to_field', 'id')
        attr = str(getattr(obj, to_field))
        value = obj.pk
        new_value = obj.name
        popup_response_data = {
            'value': value,
            'obj': str(obj),
            'new_value': new_value
        }
        return self.popup_response(request, popup_response_data)

    def popup_response(self, request, popup_response_data):
        return render(
            request,
            'admin/popup_response.html',
            {'popup_response_data': json.dumps(popup_response_data)}
        )

class TrainerProfileAdmin(admin.ModelAdmin):
    form = TrainerProfileForm
    list_display = ('profile_picture_display', 'get_trainer_name', 'phone_number', 'specialization', 'experience', 'is_active')
    list_filter = ('specialization', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'phone_number')
    
    def get_trainer_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_trainer_name.short_description = 'Trainer Name'
    
    def profile_picture_display(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />', obj.profile_picture.url)
        return format_html('<img src="/static/img/default-profile.png" width="50" height="50" style="border-radius: 50%;" />')
    profile_picture_display.short_description = 'Profile Picture'

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return (
                (None, {
                    'fields': ('user', 'specialization', 'experience', 'available_time_slots', 'profile_picture')
                }),
            )
        return (
            (None, {
                'fields': ('specialization', 'experience', 'available_time_slots', 'profile_picture', 'is_active')
            }),
        )

    def get_fieldsets(self, request, obj=None):
        if obj:  # Editing existing trainer
            return (
                ('Personal Information', {
                    'fields': (
                        'username',
                        'first_name',
                        'last_name',
                        'phone_number',
                        'profile_picture',
                    ),
                }),
                ('Trainer Details', {
                    'fields': (
                        'specialization',
                        'experience',
                        'is_active',
                    ),
                }),
            )
        else:  # Adding new trainer
            return (
                ('Personal Information', {
                    'fields': (
                        'username',
                        'first_name',
                        'last_name',
                        'phone_number',
                        'profile_picture',
                    ),
                }),
                ('Trainer Details', {
                    'fields': (
                        'specialization',
                        'experience',
                        'is_active',
                    ),
                }),
            )
    

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'user' in form.base_fields:
            form.base_fields['user'].queryset = CustomUser.objects.filter(is_trainer=True, trainerprofile__isnull=True)
        return form

    def changelist_view(self, request, extra_context=None):
        # Get client count for each trainer through Package relationship
        trainers_with_clients = TrainerProfile.objects.annotate(
            client_count=Count(
                'package__enrollments',
                filter=Q(
                    package__enrollments__status='approved',
                    package__enrollments__payment_status=True
                ),
                distinct=True
            )
        ).values(
            'user__first_name',
            'user__last_name',
            'client_count'
        ).order_by('-client_count')[:5]

        if extra_context is None:
            extra_context = {}
        
        extra_context['trainers_with_clients'] = list(trainers_with_clients)
        return super().changelist_view(request, extra_context=extra_context)

admin_site.register(TrainerProfile, TrainerProfileAdmin)

@admin.register(Package, site=admin_site)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'trainer', 'duration', 'price', 'is_active')
    list_filter = ('is_active', 'trainer')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'trainer', 'duration', 'price', 'description', 'is_active')
        }),
    )
