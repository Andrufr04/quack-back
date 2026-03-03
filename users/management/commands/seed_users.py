from django.core.management.base import BaseCommand
from users.models import User

class Command(BaseCommand):
    help = "Seed 10 test users"

    def handle(self, *args, **kwargs):
        for i in range(1, 2):
            email = f"user{i}@test.com"
            password = "123456"

            if not User.objects.filter(email=email).exists():
                User.objects.create_user(
                    email=email,
                    password=password
                )
                self.stdout.write(f"Created {email}")
            else:
                self.stdout.write(f"{email} already exists")

        self.stdout.write("Done.")
