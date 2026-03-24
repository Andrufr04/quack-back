from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['roles'] = list(user.groups.values_list('name', flat=True))
        
        group_id = None
        if hasattr(user, 'person') and hasattr(user.person, 'student'):
            student = user.person.student
            if student.study_group:
                group_id = str(student.study_group.id)
                
        token['group_id'] = group_id
        
        return token