from django.core.management.base import BaseCommand

from apps.polls.models import Question, Choice, Poll


class Command(BaseCommand):
    help = "Add 'Distrust Causes' question to a specific poll for all question types"

    def add_arguments(self, parser):
        parser.add_argument('--poll_id', type=int, required=True, help='ID of the poll')

    def handle(self, *args, **options):
        poll_id = options['poll_id']

        try:
            poll = Poll.objects.get_or_create(
                name="Сабохат опа саволнома тест",
                description=(
                    "Ассалому алайкум Сабохат опа! \n\n"
                    "Бу тест соровнома, қуйида сиз юборган саволлар кетма-кетлиги берилган"
                )
            )
        except Poll.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Poll with id={poll_id} does not exist."))
            return

        question_text = "Сизнингча, одамларда бир-бирига нисбатан ишончсизликнинг ортишига нима сабаб бўлмоқда?"
        choices = [
            "Фирибгарлик ҳолатлари кўплиги туфайли",
            "Одамларнинг асабий таранглиги туфайли",
            "Боқимондачилик кайфияти ривожланмоқда",
            "Уйишмаслик сабабли",
            "Инсонларда сабр-тоқатлиликнинг сусайиши сабабли",
            "Аҳил-иноқлик фазилатларининг камайганлиги",
            "Ижтимоий тармоқларда тарқалаётган ёлғон маълумотлар кўплиги учун",
            "Қадриятлар инқирози сабабли (одоб-ахлоқ, тарбиянинг сусайиши)",
            "Одамлар ўртасидаги тафовутлар сабабли (иқтисодий, таълим, мақом)",
            "Инсонларда ўзаро рақобат кучайиши сабабли",
            "Қўшничилик ва жамоавий муносабатлар сусайгани",
            "Махфийлик ва шубҳачанлик руҳиятининг кучайиши",
            "Инсонлар ўртасидаги мулоқотнинг камайиши",
        ]

        for idx, q_type in enumerate([
            Question.QuestionTypeChoices.CLOSED_SINGLE,
            Question.QuestionTypeChoices.CLOSED_MULTIPLE,
            Question.QuestionTypeChoices.OPEN,
            Question.QuestionTypeChoices.MIXED
        ], start=1):
            question = Question.objects.create(
                poll=poll,
                text=question_text,
                type=q_type,
                max_choices=1,
                order=idx + 100  # to avoid collision with existing
            )

            if q_type != "open":
                for order, choice_text in enumerate(choices, start=1):
                    Choice.objects.create(
                        question=question,
                        text=choice_text,
                        order=order
                    )

            self.stdout.write(self.style.SUCCESS(f"Added '{q_type}' question with id={question.id}"))
