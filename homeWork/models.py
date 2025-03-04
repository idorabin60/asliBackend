from django.db import models
from django.contrib.auth.models import User


class Homework(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="homeworks")
    created_at = models.DateTimeField(auto_now_add=True)
    # Store the Google Drive file ID
    file_id = models.CharField(max_length=255, unique=True, default='1')
    summary = models.TextField()
    new_vocabulary = models.TextField()
    grammatical_phenomenon = models.TextField()
    hw = models.TextField()

    def __str__(self):
        return f"Homework by {self.user.username}"


# Create your models here.
