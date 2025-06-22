from import_export.fields import Field
from import_export.resources import ModelResource
from django.utils import timezone
from apps.polls.models import Respondent, Question


class RespondentExportResource(ModelResource):
    tg_user_id = Field(attribute='tg_user__id', column_name='TG ID')
    fullname = Field(attribute='tg_user__fullname', column_name='ФИО')
    started_at = Field(attribute='started_at', column_name='Бошланган вақт')
    finished_at = Field(attribute='finished_at', column_name='Якунланган вақт')

    def __init__(self, poll=None, include_unfinished=False):
        super().__init__()
        self._poll = poll
        self._include_unfinished = include_unfinished

        # Добавляем динамические поля Q1, Q2, ...
        if self._poll:
            for question in self._poll.questions.all().order_by("order"):
                col = f"Q{question.order}"
                self.fields[col] = Field(column_name=col)

    def get_export_queryset(self, request):
        qs = Respondent.objects.all()
        if self._poll:
            qs = qs.filter(poll=self._poll)
        if not self._include_unfinished:
            qs = qs.filter(finished_at__isnull=False)

        return qs.prefetch_related(
            'answers__question__choices',
            'answers__selected_choices',
            'tg_user',
            'poll__questions'
        )

    def dehydrate(self, respondent, field):
        # Обработка ответов Q1, Q2 и т.д.
        if field.column_name.startswith("Q"):
            try:
                order_num = int(field.column_name.replace("Q", ""))
                question = respondent.poll.questions.filter(order=order_num).first()
                if not question:
                    return ""

                answer = respondent.answers.filter(question=question).first()
                if not answer:
                    return ""

                if answer.open_answer:
                    return answer.open_answer.strip()

                selected = answer.selected_choices.all().order_by("order")
                return ", ".join(str(choice.order) for choice in selected)

            except Exception:
                return ""

        # Обработка стандартных полей
        elif field.column_name == 'Бошланган вақт':
            if respondent.started_at:
                return respondent.started_at.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")
        elif field.column_name == 'Якунланган вақт':
            if respondent.finished_at:
                return respondent.finished_at.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")

        return super().dehydrate(respondent, field)

    class Meta:
        model = Respondent
        fields = ['tg_user_id', 'fullname', 'started_at', 'finished_at']
        export_order = ['tg_user_id', 'fullname', 'started_at', 'finished_at']
