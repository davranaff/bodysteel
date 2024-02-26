from rest_framework import serializers

from users.models import User


class SignupSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
