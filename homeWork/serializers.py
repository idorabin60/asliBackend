import json
from rest_framework import serializers
from .models import (
    Homework,
    VocabularyMatch,
    FillInBlank,
    GrammaticalPhenomenon
)


class VocabularyMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = VocabularyMatch
        fields = ['id', 'arabic_word', 'hebrew_word', 'homework']


class FillInBlankSerializer(serializers.ModelSerializer):
    class Meta:
        model = FillInBlank
        fields = ['id', 'sentence', 'options',
                  'correct_option', 'homework', 'hebrew_sentence']


class GrammaticalPhenomenonSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrammaticalPhenomenon
        fields = ['id', 'text', 'homework']


class HomeworkSerializer(serializers.ModelSerializer):
    vocab_matches = VocabularyMatchSerializer(many=True, read_only=True)
    fill_in_blanks = FillInBlankSerializer(many=True, read_only=True)
    grammatical_phenomenon = GrammaticalPhenomenonSerializer(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Homework
        fields = [
            'id',
            'user',
            'due_date',
            'vocab_matches',
            'fill_in_blanks',
            'grammatical_phenomenon',

        ]
