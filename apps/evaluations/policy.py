from rest_access_policy import AccessPolicy, Statement


class EvaluationPolicy(AccessPolicy):
    statements = [
        Statement(
            action=['get_by_slug', 'list', 'retrieve', 'competitions', 'active_competitions'],
            principal='*',
            effect='allow',
        ),
        Statement(
            action=['get_attempts', 'my_attempts', 'all_my_attempts', 'results', 'result'],
            principal='authenticated',
            effect='allow',
        ),
        Statement(
            action=['create', 'statistics'],
            principal='authenticated',
            effect='allow',
            condition='is_creator',
        ),
        Statement(
            action=['test_skills', 'get_test_skills'],
            principal='authenticated',
            effect='allow',
            condition='is_developer',
        ),
        Statement(
            action=['update', 'partial_update', 'destroy', 'evaluation_statistics', 'invite_candidates',
                    'update_by_proportion', 'add_question', 'add_from_scratch', 'grouped'],
            principal='authenticated',
            effect='allow',
            condition_expression='is_creator and is_publisher',
        )
    ]

    def is_publisher(self, request, view, action) -> bool:
        return request.user == view.get_object().publisher


class EvaluationCandidatePolicy(AccessPolicy):
    statements = [
        Statement(
            action=['create'],
            principal='authenticated',
            effect='allow',
            condition='is_creator',
        ),
        Statement(
            action=['update', 'partial_update', 'destroy', 'list', 'retrieve'],
            principal='authenticated',
            effect='allow',
        ),
    ]
