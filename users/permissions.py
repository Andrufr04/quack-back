from rest_framework import permissions

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='student').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'student'
    

class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='teacher').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'teacher'

class IsCurator(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='curator').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'curator'
    
class IsAdministration(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='administration').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'administration'
    
class IsParent(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='parent').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'parent'
    
class IsFounder(permissions.BasePermission):
    def has_permission(self, request, view):
        is_in_group = request.user.groups.filter(name='founder').exists()
        active_role = request.headers.get('X-Active-Role')
        return is_in_group and active_role == 'founder'