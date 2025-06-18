import csv

from django.contrib import admin
from django.http import HttpResponse

from apps.polls.models import Poll, Question, Choice, Respondent, Answer


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'deadline', 'is_active_status')
    inlines = [QuestionInline]

    def is_active_status(self, obj):
        return obj.is_active()

    is_active_status.boolean = True
    is_active_status.short_description = "Активен?"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'type', 'poll', 'order')
    inlines = [ChoiceInline]
    list_filter = ('poll', 'type')


@admin.register(Respondent)
class RespondentAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'poll', 'started_at', 'finished_at')
    list_filter = ('poll', 'finished_at')
    actions = ['export_respondents_with_answers']

    def export_respondents_with_answers(self, request, queryset):
        completed = queryset.filter(finished_at__isnull=False)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=completed_respondents.csv'

        writer = csv.writer(response)
        writer.writerow([
            'Respondent ID',
            'Gender',
            'Age',
            'Poll',
            'Question',
            'Selected Choices',
            'Open Answer',
            'Started At',
            'Finished At',
        ])

        for respondent in completed:
            for answer in respondent.answers.all():
                selected = ", ".join(choice.text for choice in answer.selected_choices.all())
                writer.writerow([
                    respondent.tg_user.id,
                    respondent.tg_user.gender,
                    respondent.tg_user.age,
                    respondent.poll.name,
                    answer.question.text,
                    selected,
                    answer.open_answer,
                    respondent.started_at,
                    respondent.finished_at,
                ])

        return response

    export_respondents_with_answers.short_description = "Экспорт завершённых респондентов с ответами"


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('respondent', 'question')
    list_filter = ('question__poll',)
