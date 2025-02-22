from rest_framework import serializers
from .models import Homework


class HomeworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ['id', 'user', 'text', 'created_at']
        read_only_fields = ['id', 'created_at']
