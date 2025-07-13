from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from import_export.admin import ExportMixin
from tablib import Dataset
from markdownx.admin import MarkdownxModelAdmin


from apps.polls.filters import PollFilterForm
from apps.polls.models import Poll, Question, Choice, Respondent, Answer
from apps.polls.resources import RespondentExportResource


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1

    def get_max_num(self, request, obj=None, **kwargs):
        if obj and obj.type == Question.QuestionTypeChoices.MIXED:
            return 11
        return 12


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Poll)
class PollAdmin(MarkdownxModelAdmin):
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
    change_list_template = "polls/respondents_export_filter.html"  # шаблон для кнопки (см. ниже)

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('export-custom/', self.admin_site.admin_view(self.export_custom_view), name='respondent_export_custom')
        ] + urls

    def export_custom_view(self, request):
        if request.method == "POST":
            form = PollFilterForm(request.POST)
            if form.is_valid():
                poll = form.cleaned_data["poll"]
                include_unfinished = form.cleaned_data["include_unfinished"]
                print(f"📝 Export request received for poll: {poll.id}, include_unfinished={include_unfinished}")

                resource = RespondentExportResource(poll=poll, include_unfinished=include_unfinished)
                queryset = resource.get_export_queryset(request)
                export_fields = resource.get_export_fields()

                dataset = Dataset(headers=[f.column_name for f in export_fields])
                for respondent in queryset:
                    row = resource.export_resource(respondent)
                    dataset.append([row.get(f.attribute or f.column_name, "") for f in export_fields])

                print(f"✅ Exported {len(dataset)} rows with {len(export_fields)} fields")

                try:
                    response = HttpResponse(dataset.xlsx,
                                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    response["Content-Disposition"] = f'attachment; filename=respondents_poll_{poll.id}.xlsx'
                    return response
                except Exception as e:
                    print("❌ XLSX export error:", e)
                    raise
        else:
            form = PollFilterForm()

        context = {
            "opts": self.model._meta,
            "form": form,
            "title": "Экспорт респондентов с фильтрами",
        }
        return TemplateResponse(request, "polls/respondents_export_form.html", context)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('respondent', 'question')
    list_filter = ('question__poll',)
