from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Homework
from .serializers import HomeworkSerializer
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def homework_list_create(request):
    if request.method == 'GET':
        homeworks = Homework.objects.filter(user=request.user)
        serializer = HomeworkSerializer(homeworks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def homework_detail(request, pk):
    homework = get_object_or_404(
        Homework, pk=pk, user=request.user)  # Ensure user owns it

    if request.method == 'GET':
        serializer = HomeworkSerializer(homework)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        serializer = HomeworkSerializer(
            homework, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        homework.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def get_all_hw(request):
    homeworks = Homework.objects.all()
    serializer = HomeworkSerializer(homeworks, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def student_homeworks(request, student_id):
    """
    GET /students/<student_id>/homeworks/
    Returns all Homework objects for that user, but only if:
     - the requester is authenticated,
     - AND (optionally) the requester is the teacher of this student.
    """
    # Optional: enforce that only a teacher can fetch their own students
    if request.user.role != User.ROLE_TEACHER or request.user.id != get_object_or_404(
        User, pk=student_id, role=User.ROLE_STUDENT, teacher=request.user
    ).teacher_id:
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    student = get_object_or_404(User, pk=student_id, role=User.ROLE_STUDENT)

    qs = Homework.objects.filter(user=student)
    serializer = HomeworkSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def student_homework_detail(request, student_id, homework_id):
    """
    GET /students/{student_id}/homeworks/{homework_id}/
    Only a teacher may fetch an individual homework of their own student.
    """
    # 1. Ensure requester is a teacher
    if request.user.role != User.ROLE_TEACHER:
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    # 2. Verify the student exists and belongs to this teacher
    student = get_object_or_404(
        User,
        pk=student_id,
        role=User.ROLE_STUDENT,
        teacher=request.user
    )

    # 3. Fetch that exact homework for the student (404 if not found)
    hw = get_object_or_404(
        Homework,
        pk=homework_id,
        user=student
    )

    # 4. Serialize and return
    serializer = HomeworkSerializer(hw)
    return Response(serializer.data, status=status.HTTP_200_OK)
