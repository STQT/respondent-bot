from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.polls.models import Choice
from apps.polls.models import Poll
from apps.polls.models import Question


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = [
            "name",
            "deadline",
            "reward",
            "description",
            "description_uz_latn",
            "description_ru",
        ]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "description_uz_latn": forms.Textarea(attrs={"rows": 3}),
            "description_ru": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline <= timezone.now():
            raise forms.ValidationError(_("Дедлайн должен быть в будущем."))
        return deadline


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            "text",
            "text_uz_latn",
            "text_ru",
            "type",
            "max_choices",
            "order",
        ]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 2}),
            "text_uz_latn": forms.Textarea(attrs={"rows": 2}),
            "text_ru": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        qtype = cleaned.get("type")
        max_choices = cleaned.get("max_choices")
        if qtype in (
            Question.QuestionTypeChoices.CLOSED_MULTIPLE,
            Question.QuestionTypeChoices.MIXED_MULTIPLE,
        ):
            if not max_choices or max_choices < 1:
                self.add_error("max_choices", _("Укажите max_choices (>=1) для множественного выбора."))
        else:
            cleaned["max_choices"] = None
        return cleaned


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ["text", "text_uz_latn", "text_ru", "order"]

