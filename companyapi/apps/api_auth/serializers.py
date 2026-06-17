from django.contrib.auth.models import User, Group
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'roles')

    def get_roles(self, obj):
        return [group.name for group in obj.groups.all()]

class RegisterSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=['Admin', 'Safety Manager', 'Driver'], required=False, default='Driver')

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'first_name', 'last_name', 'role')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        role_name = validated_data.pop('role', 'Driver')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        group, created = Group.objects.get_or_create(name=role_name)
        user.groups.add(group)
        return user
