import uuid
from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from profiles.models import Person, Profile
from education.models import StudyGroup, Student, Subject, Task, TaskType

User = get_user_model()

class Command(BaseCommand):
    help = "Seed the database with Users, Persons, Profiles, and Education data"

    def handle(self, *args, **kwargs):
        first_names = ["Олександр", "Марія", "Дмитро", "Анна", "Андрій", "Олена", "Сергій", "Вікторія", "Ігор", "Юлія"]
        last_names = ["Шевченко", "Бондаренко", "Коваленко", "Бойко", "Ткаченко", "Кравченко", "Олійник", "Поліщук", "Козак", "Марченко"]

        task_type, _ = TaskType.objects.get_or_create(name="Практична робота")

        persons = []
        curator_profile = None

        for i in range(1, 10):
            email = f"user{i}@test.com"
            user, created = User.objects.get_or_create(
                email=email
            )
            if created:
                if (i == 1):
                    user.set_password("!23456")
                else:
                    user.set_password("123456")
                user.save()

            person, _ = Person.objects.get_or_create(
                user=user,
                defaults={
                    'name': first_names[i-1],
                    'surname': last_names[i-1],
                    'birthdate': date(2000 + i, i, 10)
                }
            )
            persons.append(person)

            profile, _ = Profile.objects.get_or_create(
                person=person,
                defaults={'description': f"Профіль користувача {email}"}
            )

            if email == "user1@test.com":
                curator_profile = profile

        self.stdout.write(self.style.SUCCESS("Users, Persons, and Profiles created."))

        group, _ = StudyGroup.objects.get_or_create(
            name="КНП-67",
            defaults={'curator': curator_profile}
        )
        self.stdout.write(self.style.SUCCESS(f"Group {group.name} created with curator {curator_profile.person.surname}."))

        for person in persons[1:]:
            Student.objects.get_or_create(
                person=person,
                study_group=group
            )
        self.stdout.write(self.style.SUCCESS("Students assigned to the group."))

        subject_names = ["Основи управління проектами. Командний проект.", "Фізика"]
        subjects = [Subject.objects.get_or_create(name=name)[0] for name in subject_names]
        self.stdout.write(self.style.SUCCESS("Subjects created."))

        start_dt = timezone.make_aware(datetime(2026, 3, 2, 5, 0, 0))
        end_dt = timezone.make_aware(datetime(2026, 3, 4, 16, 0, 0))

        Task.objects.get_or_create(
            study_group=group,
            subject=subjects[0],
            theme="Тема найкрутішого завдання",
            defaults={
                'description': "Опис найкрутішого завдання",
                'start': start_dt,
                'end': end_dt
            }
        )
        self.stdout.write(self.style.SUCCESS("Task created successfully!"))