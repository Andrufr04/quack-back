from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['roles'] = list(user.groups.values_list('name', flat=True))
        # token['full_name'] = f"{user.person.name} {user.person.surname}"
        
        return token