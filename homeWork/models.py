# homeWork/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Homework(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    due_date = models.DateField(default=timezone.now)
    file_id = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"{self.user} – due {self.due_date}"


class VocabularyMatch(models.Model):
    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="vocab_matches"
    )
    arabic_word = models.CharField(max_length=200)
    hebrew_word = models.CharField(max_length=200)


class FillInBlank(models.Model):
    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name="fill_in_blanks"
    )
    sentence = models.TextField()
    hebrew_sentence = models.TextField()
    options = models.JSONField()
    correct_option = models.CharField(max_length=200)


class GrammaticalPhenomenon(models.Model):
    homework = models.OneToOneField(
        Homework,
        on_delete=models.CASCADE,
        related_name="grammatical_phenomenon"
    )
    text = models.TextField()
