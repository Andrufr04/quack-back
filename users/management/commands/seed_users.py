import uuid
from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from profiles.models import Person, Profile
from education.models import StudyGroup, Student, Subject, Task, TaskType, Teacher

User = get_user_model()

class Command(BaseCommand):
    help = "Seed the database with Users, Persons, Profiles, and Education data"

    def handle(self, *args, **kwargs):
        first_names = ["Олександр", "Марія", "Дмитро", "Анна", "Андрій", "Олена", "Сергій", "Вікторія", "Ігор", "Юлія"]
        last_names = ["Шевченко", "Бондаренко", "Коваленко", "Бойко", "Ткаченко", "Кравченко", "Олійник", "Поліщук", "Козак", "Марченко"]

        task_type, _ = TaskType.objects.get_or_create(name="Практична робота")

        persons = []
        curator_user = None

        roles_names = ["student", "teacher", "curator", "administration", "founder", "parent"]
        roles = [Group.objects.get_or_create(name=name)[0] for name in roles_names]

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
                defaults={'description': "Цей користувач найкрутіший на платформі Quack. Його багатозначна задача — це створювати максимально круті речі та ламати систему."}
            )

            if email == "user1@test.com":
                curator_user = user

            
            user.groups.add(roles[1] if user.email == "user1@test.com" else roles[0])

            if user.email == "user1@test.com":
                user.groups.add(roles[3])

        self.stdout.write(self.style.SUCCESS("Users, Persons, Roles and Profiles created."))

        group, _ = StudyGroup.objects.get_or_create(
            name="КНП-67",
            defaults={'curator': curator_user}
        )
        self.stdout.write(self.style.SUCCESS(f"Group {group.name} created with curator."))

        for person in persons[1:]:
            Student.objects.get_or_create(
                person=person,
                study_group=group
            )
        teacher_person = persons[0] 

        teacher, created = Teacher.objects.get_or_create(
            person=teacher_person,
            defaults={
                'teaching_group': group
            }
        )
        self.stdout.write(self.style.SUCCESS("Students and teacher assigned to the group."))

        subject_names = ["Основи управління проектами. Командний проект.", "Фізика", "Біологія", "C#"]
        subjects = [Subject.objects.get_or_create(name=name)[0] for name in subject_names]
        self.stdout.write(self.style.SUCCESS("Subjects created."))