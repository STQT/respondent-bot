from django import forms

from apps.polls.models import Poll


class PollFilterForm(forms.Form):
    poll = forms.ModelChoiceField(queryset=Poll.objects.all(), label="Тема", required=True)
    include_unfinished = forms.BooleanField(label="Ҳаммани олиш (ҳатто якунланмаган)", required=False)
