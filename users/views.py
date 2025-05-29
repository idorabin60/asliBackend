from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSerializer
from homeWork.serializers import HomeworkSerializer  # Import Homework serializer
from homeWork.models import Homework  # Import Homework model
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(['POST'])
def login(request):
    user = get_object_or_404(User, email=request.data['email'])
    if not user.check_password(request.data['password']):
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    token, created = Token.objects.get_or_create(user=user)
    serializer = UserSerializer(instance=user)
    return Response({"token": token.key, "user": serializer.data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def signup(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        validated_data = serializer.validated_data
        email = validated_data.get('email')
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "User with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        password = validated_data.pop('password', None)

        user = User(**validated_data)

        if password:
            user.set_password(password)

        user.save()

        # Generate authentication token
        token, created = Token.objects.get_or_create(user=user)

        # Serialize the user AFTER saving to include the correct data
        user_serializer = UserSerializer(user)
        print(user_serializer)

        return Response({"token": token.key, "user": user_serializer.data}, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def test_token(request):
    return Response({})


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def user_homeworks(request):
    """ Get all homeworks for the logged-in user """
    homeworks = Homework.objects.filter(user=request.user)
    serializer = HomeworkSerializer(homeworks, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_homework_by_id(request, homework_id):
    """ Get a specific homework for the logged-in user by ID """
    try:
        homework = Homework.objects.get(id=homework_id, user=request.user)
    except Homework.DoesNotExist:
        return Response({"detail": "Homework not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = HomeworkSerializer(homework)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_all_teachers(request):
    try:
        teachers = User.objects.filter(role=User.ROLE_TEACHER)
    except User.DoesNotExist:
        return Response({"detail": "teachers not found."}, status=status.HTTP_404_NOT_FOUND)
    serializer = UserSerializer(teachers, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def students_of_teacher(request, teacher_id):
    """
    GET /api/teachers/{teacher_id}/students/
    Returns all users whose `teacher_id` matches and whose role is STUDENT.
    """
    teacher = get_object_or_404(User, pk=teacher_id, role=User.ROLE_TEACHER)
    students_qs = teacher.students.filter(role=User.ROLE_STUDENT)
    serializer = UserSerializer(students_qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_user_by_id(request, user_id):
    user = get_object_or_404(User, id=user_id)
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)
