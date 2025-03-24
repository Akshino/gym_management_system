from django import template

register = template.Library()

@register.filter
def filter_by_status(enrollments, status):
    if not enrollments:
        return []
    return enrollments.filter(status=status)

@register.filter
def filter_by_package(enrollments, package):
    if not enrollments:
        return None
    return enrollments.filter(package=package).first()
