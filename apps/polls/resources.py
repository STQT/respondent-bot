from django.utils import timezone
from import_export.fields import Field
from import_export.resources import ModelResource

from apps.polls.models import Respondent


class RespondentExportResource(ModelResource):
    def __init__(self, poll=None, include_unfinished=False):
        super().__init__()
        self._poll = poll
        self._include_unfinished = include_unfinished
        self._dynamic_fields = []

        if self._poll:
            for question in self._poll.questions.all().order_by("order"):
                field_name = f"Q{question.order}"
                self._dynamic_fields.append((field_name, question.id))
                self.fields[field_name] = Field(column_name=field_name)

        # ⬇️ Статические поля
        self.fields['tg_user_id'] = Field(attribute='tg_user_id', column_name='TG ID')
        self.fields['fullname'] = Field(attribute='fullname', column_name='ФИО')
        self.fields['started_at'] = Field(attribute='started_at', column_name='Бошланган вақт')
        self.fields['finished_at'] = Field(attribute='finished_at', column_name='Якунланган вақт')
        dynamic_fields = [f for f, _ in self._dynamic_fields]
        self.export_order = [
                                'tg_user_id', 'fullname', 'started_at', 'finished_at'
                            ] + dynamic_fields

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
        )

    # ✅ Статические поля
    def dehydrate_tg_user_id(self, respondent):
        return respondent.tg_user.id

    def dehydrate_fullname(self, respondent):
        return respondent.tg_user.fullname

    def dehydrate_started_at(self, respondent):
        if respondent.started_at:
            return respondent.started_at.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")
        return ""

    def dehydrate_finished_at(self, respondent):
        if respondent.finished_at:
            return respondent.finished_at.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")
        return ""

    def get_export_fields(self, resource=None):
        base_fields = [
            self.fields['tg_user_id'],
            self.fields['fullname'],
            self.fields['started_at'],
            self.fields['finished_at'],
        ]
        dynamic_fields = [self.fields[name] for name, _ in self._dynamic_fields]
        return base_fields + dynamic_fields

    def export_resource(self, respondent, *args, **kwargs):
        row = {
            'tg_user_id': self.dehydrate_tg_user_id(respondent),
            'fullname': self.dehydrate_fullname(respondent),
            'started_at': self.dehydrate_started_at(respondent),
            'finished_at': self.dehydrate_finished_at(respondent),
        }

        # Заполняем ответы по каждому динамическому вопросу
        answers_map = {a.question_id: a for a in respondent.answers.all()}
        for field_name, question_id in self._dynamic_fields:
            answer = answers_map.get(question_id)
            if not answer:
                row[field_name] = ""
            elif answer.open_answer:
                row[field_name] = answer.open_answer.strip()
            else:
                selected = answer.selected_choices.all().order_by("order")
                row[field_name] = ", ".join(str(c.order) for c in selected)

        return row

    class Meta:
        model = Respondent
