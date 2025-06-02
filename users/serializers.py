from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password',
                  'email', 'first_name', 'last_name']


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    # Write-only field for password
    password = serializers.CharField(write_only=True, required=True)

    # Expose the reverse relationship: teacher → [students]
    students = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'role',
            'teacher',
            'students',
            'password',
            'first_name',      # NEW
            'last_name',
        ]
        read_only_fields = ['students']

    def validate(self, data):
        """
        Enforce that:
          - A student must have a teacher
          - A teacher cannot have a teacher
        """
        role = data.get('role', getattr(self.instance, 'role', None))
        teacher = data.get('teacher', getattr(self.instance, 'teacher', None))

        if role == User.ROLE_STUDENT and teacher is None:
            raise serializers.ValidationError({
                'teacher': 'Students must be assigned a teacher.'
            })
        if role == User.ROLE_TEACHER and teacher is not None:
            raise serializers.ValidationError({
                'teacher': 'Teachers cannot have a teacher.'
            })
        return data

    def create(self, validated_data):
        # Extract and remove password from validated_data
        password = validated_data.pop('password')

        # Create the user instance without the password
        user = User(**validated_data)

        # Hash and set the password
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
