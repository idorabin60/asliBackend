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


@api_view(['POST'])
def login(request):
    user = get_object_or_404(User, email=request.data['username'])
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

        # Extract password separately to hash it later
        password = validated_data.pop('password', None)

        # Create the user with validated data (including first_name and last_name)
        user = User(**validated_data)

        # Hash the password before saving
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
