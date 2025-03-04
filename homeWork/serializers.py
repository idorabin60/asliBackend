from rest_framework import serializers
from .models import Homework


class HomeworkSerializer(serializers.ModelSerializer):
    # Ensures the user field is properly serialized
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Homework
        fields = [
            'id', 'user', 'created_at', 'file_id',
            'summary', 'new_vocabulary', 'grammatical_phenomenon', 'hw'
        ]
        read_only_fields = ['id', 'created_at', 'file_id']
