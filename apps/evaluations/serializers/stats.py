from rest_framework import serializers


class ScoreDistributionSerializer(serializers.Serializer):
    excellent = serializers.IntegerField(help_text="Nombre de scores excellents (≥80%)")
    good = serializers.IntegerField(help_text="Nombre de bons scores (60-79%)")
    average = serializers.IntegerField(help_text="Nombre de scores moyens (40-59%)")
    poor = serializers.IntegerField(help_text="Nombre de scores faibles (<40%)")


class QuestionStatisticSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(help_text="ID de la question")
    question_title = serializers.CharField(help_text="Texte de la question (tronqué)")
    total_answers = serializers.IntegerField(help_text="Nombre total de réponses")
    correct_answers = serializers.IntegerField(help_text="Nombre de réponses correctes")
    success_rate = serializers.FloatField(help_text="Taux de réussite en pourcentage")


class TopParticipantSerializer(serializers.Serializer):
    participant_name = serializers.CharField(help_text="Nom du participant")
    attempts_count = serializers.IntegerField(help_text="Nombre de tentatives")
    completed = serializers.IntegerField(help_text="Nombre de tentatives complétées")
    best_score = serializers.FloatField(help_text="Meilleur score obtenu")


class GlobalTopParticipantSerializer(serializers.Serializer):
    participant_name = serializers.CharField(help_text="Nom du participant")
    total_attempts = serializers.IntegerField(help_text="Nombre total de tentatives")
    completed_attempts = serializers.IntegerField(help_text="Nombre de tentatives complétées")
    best_score = serializers.FloatField(help_text="Meilleur score obtenu")
    average_score = serializers.FloatField(help_text="Score moyen")
    evaluations_participated = serializers.IntegerField(help_text="Nombre d'évaluations auxquelles il a participé")


class EvaluationStatisticsSerializer(serializers.Serializer):
    evaluation_id = serializers.IntegerField(help_text="ID de l'évaluation")
    evaluation_title = serializers.CharField(help_text="Titre de l'évaluation")
    total_attempts = serializers.IntegerField(help_text="Nombre total de tentatives")
    completed_attempts = serializers.IntegerField(help_text="Nombre de tentatives complétées")
    average_score = serializers.FloatField(help_text="Score moyen")
    max_score_possible = serializers.FloatField(help_text="Score maximum possible")
    min_score = serializers.FloatField(help_text="Score minimum obtenu")
    max_score = serializers.FloatField(help_text="Score maximum obtenu")
    completion_rate = serializers.FloatField(help_text="Taux de completion en pourcentage")
    total_participants = serializers.IntegerField(help_text="Nombre total de participants")
    questions_count = serializers.IntegerField(help_text="Nombre de questions")
    created_at = serializers.DateTimeField(help_text="Date de création")
    status = serializers.CharField(help_text="Statut de l'évaluation (active/inactive)")


class UserEvaluationStatisticsSerializer(serializers.Serializer):
    total_evaluations_created = serializers.IntegerField(help_text="Nombre total d'évaluations créées")
    active_evaluations = serializers.IntegerField(help_text="Nombre d'évaluations actives")
    total_attempts_received = serializers.IntegerField(help_text="Nombre total de tentatives reçues")
    total_completed_attempts = serializers.IntegerField(help_text="Nombre total de tentatives complétées")
    average_completion_rate = serializers.FloatField(help_text="Taux de completion moyen en pourcentage")
    total_participants = serializers.IntegerField(help_text="Nombre total de participants uniques")
    average_score = serializers.FloatField(help_text="Score moyen global")
    total_questions = serializers.IntegerField(help_text="Nombre total de questions dans toutes les évaluations")
    top_participants = GlobalTopParticipantSerializer(many=True, help_text="Top 10 des participants globaux")
    last_updated = serializers.DateTimeField(help_text="Dernière mise à jour")


class DetailedEvaluationStatisticsSerializer(serializers.Serializer):
    evaluation_id = serializers.IntegerField(help_text="ID de l'évaluation")
    evaluation_title = serializers.CharField(help_text="Titre de l'évaluation")
    evaluation_description = serializers.CharField(help_text="Description de l'évaluation")
    total_attempts = serializers.IntegerField(help_text="Nombre total de tentatives")
    completed_attempts = serializers.IntegerField(help_text="Nombre de tentatives complétées")
    average_score = serializers.FloatField(help_text="Score moyen")
    max_score_possible = serializers.FloatField(help_text="Score maximum possible")
    min_score = serializers.FloatField(help_text="Score minimum obtenu")
    max_score = serializers.FloatField(help_text="Score maximum obtenu")
    completion_rate = serializers.FloatField(help_text="Taux de completion en pourcentage")
    total_participants = serializers.IntegerField(help_text="Nombre total de participants")
    questions_count = serializers.IntegerField(help_text="Nombre de questions")
    average_time_minutes = serializers.FloatField(help_text="Temps moyen en minutes")
    score_distribution = ScoreDistributionSerializer(help_text="Distribution des scores")
    questions_statistics = QuestionStatisticSerializer(many=True, help_text="Statistiques par question")
    top_participants = TopParticipantSerializer(many=True, help_text="Top 10 des participants")
    created_at = serializers.DateTimeField(help_text="Date de création")
    archived = serializers.BooleanField(help_text="Statut actif de l'évaluation")
    last_updated = serializers.DateTimeField(help_text="Dernière mise à jour")
