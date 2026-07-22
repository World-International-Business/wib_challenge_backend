import json
import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wib_challenge.settings')
import django
django.setup()

from questions.models import Domain, Category, Criteria, Tag, Question, Choice

DATA_FILE = Path(__file__).resolve().parent / 'questions' / 'management' / 'commands' / 'data' / 'graphisme.json'

raw = json.loads(DATA_FILE.read_text(encoding='utf-8'))
items = raw if isinstance(raw, list) else [raw]

for item in items:
    domain, _ = Domain.objects.get_or_create(name=item['domain'].strip())
    category, _ = Category.objects.get_or_create(name=item['category'].strip(), domain=domain)
    criteria, _ = Criteria.objects.get_or_create(name=item['criteria'].strip(), category=category)

    tag_map = {}
    for tag_name in item.get('tags', []):
        tag, _ = Tag.objects.get_or_create(name=tag_name.strip(), criteria=criteria)
        tag_map[tag_name] = tag

    for q in item.get('questions', []):
        question, _ = Question.objects.get_or_create(
            title=q['title'].strip(),
            level=int(q['level']),
            question_type=q['question_type'].strip(),
            defaults={
                'category': category,
                'description': q.get('description'),
                'question_category': q.get('question_category', 'NORMAL'),
            }
        )
        q_tags = [tag_map[t] for t in q.get('tags', []) if t in tag_map]
        question.tags.set(q_tags)

        if question.question_type in (Question.QuestionType.MULTIPLE_CHOICE, Question.QuestionType.UNIQUE_CHOICE):
            for c in q.get('choices', []):
                Choice.objects.get_or_create(
                    question=question,
                    text=c['text'],
                    defaults={'is_correct': c['is_correct']}
                )

print('Graphisme importé avec succès.')
