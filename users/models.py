# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Role constants
    ROLE_TEACHER = 'teacher'
    ROLE_STUDENT = 'student'
    ROLE_CHOICES = [
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_STUDENT, 'Student'),
    ]

    # Indicates whether this user is a teacher or a student
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        help_text="Designates whether this user is a teacher or a student."
    )

    # For students only: link to their single teacher (self FK)
    teacher = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={'role': ROLE_TEACHER},
        related_name='students',
        help_text="If this user is a student, the teacher they belong to."
    )

    def save(self, *args, **kwargs):
        # Ensure that teachers never have a teacher assigned
        if self.role == self.ROLE_TEACHER:
            self.teacher = None
        super().save(*args, **kwargs)
