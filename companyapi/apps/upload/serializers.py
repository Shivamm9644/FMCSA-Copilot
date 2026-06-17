"""
File: apps/upload/serializers.py
Why it exists:
    Provides Django REST Framework serializers for Company, CMV, and ELDFile models.
    This manages validation and formats records for HTTP responses.

Inputs:
    - Model instances or JSON request structures.

Outputs:
    - Serialized data outputs.

Dependencies:
    - rest_framework.serializers (DRF)
    - django.contrib.auth.models.User (Django Auth)
    - apps.upload.models (Company, CMV, ELDFile definitions)
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from apps.upload.models import Company, CMV, ELDFile

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

class CMVSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMV
        fields = '__all__'

class ELDFileSerializer(serializers.ModelSerializer):
    driver = UserSerializer(read_only=True)
    cmv_details = CMVSerializer(source='cmv', read_only=True)
    events_count = serializers.SerializerMethodField()
    latest_run = serializers.SerializerMethodField()
    
    class Meta:
        model = ELDFile
        fields = (
            'id', 'driver', 'cmv', 'cmv_details', 'filename', 'file_path', 
            'status', 'uploaded_at', 'compliance_score', 'overall_status', 
            'raw_header_json', 'error_log', 'events_count', 'latest_run'
        )
        
    def get_events_count(self, obj) -> int:
        return obj.events.count()

    def get_latest_run(self, obj):
        from apps.validations.serializers import ValidationRunSerializer
        run = obj.validation_runs.order_by('-run_at').first()
        if run:
            return ValidationRunSerializer(run).data
        return None
