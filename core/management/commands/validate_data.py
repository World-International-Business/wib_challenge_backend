import json
from pathlib import Path
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Validate data integrity between profession_technologies and technologies"

    def handle(self, *args, **options):
        data_dir = Path(__file__).parent / "data"

        tech_path = data_dir / "technologies.json"
        with open(tech_path, "r", encoding="utf-8") as f:
            technologies = json.load(f)

        tech_names = set(tech["name"].lower() for tech in technologies)

        prof_tech_path = data_dir / "profession_technologies.json"
        with open(prof_tech_path, "r", encoding="utf-8") as f:
            profession_technologies = json.load(f)

        missing_techs = set()
        tech_usage = {}

        for prof_tech in profession_technologies:
            profession = prof_tech["profession"]
            techs = prof_tech["technologies"]

            for tech in techs:
                if tech.lower() not in tech_names:
                    missing_techs.add(tech)

                    if tech not in tech_usage:
                        tech_usage[tech] = []
                    tech_usage[tech].append(profession)

        if missing_techs:
            self.stdout.write(
                self.style.ERROR(
                    f"Found {len(missing_techs)} technologies that are missing in technologies.json:"
                )
            )
            for tech in sorted(missing_techs):
                professions = tech_usage[tech]
                self.stdout.write(
                    self.style.ERROR(f"- {tech} (used by: {', '.join(professions)})")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "All technologies referenced in profession_technologies.json exist in technologies.json"
                )
            )

        used_techs = set()
        for prof_tech in profession_technologies:
            used_techs.update(set([t.lower() for t in prof_tech["technologies"]]))

        unused_techs = tech_names - used_techs
        if unused_techs:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(unused_techs)} technologies that are not used by any profession:"
                )
            )
            for tech in sorted(unused_techs):
                self.stdout.write(self.style.WARNING(f"- {tech}"))
