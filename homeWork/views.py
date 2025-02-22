from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Homework
from serializers import HomeworkSerializer


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
