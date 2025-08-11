from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from import_export.admin import ExportMixin
from tablib import Dataset
from markdownx.admin import MarkdownxModelAdmin
from django.utils import timezone


from apps.polls.filters import PollFilterForm
from apps.polls.models import Poll, Question, Choice, Respondent, Answer, ExportFile, NotificationCampaign
from apps.polls.resources import RespondentExportResource
from apps.polls.tasks import export_respondents_task


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
class PollAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'deadline', 'is_active_status')
    inlines = [QuestionInline]

    def is_active_status(self, obj):
        return obj.is_active()

    is_active_status.boolean = True
    is_active_status.short_description = "Активен?"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'type', 'poll', 'max_choices', 'order')
    list_editable = ('order', 'max_choices')
    inlines = [ChoiceInline]
    list_filter = ('poll', 'type')


@admin.register(ExportFile)
class ExportFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'status', 'created_at', 'completed_at', 'created_by', 'poll')
    list_filter = ('status', 'created_at', 'poll')
    readonly_fields = ('created_at', 'completed_at', 'file', 'filename')
    search_fields = ('filename', 'error_message')
    
    def has_add_permission(self, request):
        return False  # Запрещаем создание через админку
    
    def has_change_permission(self, request, obj=None):
        return False  # Запрещаем редактирование через админку


@admin.register(Respondent)
class RespondentAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'poll', 'started_at', 'finished_at')
    list_filter = ('poll', 'finished_at')
    change_list_template = "polls/respondents_export_filter.html"  # шаблон для кнопки (см. ниже)

    def get_urls(self):
        urls = super().get_urls()
        return [
            path('export-custom/', self.admin_site.admin_view(self.export_custom_view), name='respondent_export_custom'),
            path('export-async/', self.admin_site.admin_view(self.export_async_view), name='respondent_export_async')
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

    def export_async_view(self, request):
        if request.method == "POST":
            form = PollFilterForm(request.POST)
            if form.is_valid():
                poll = form.cleaned_data["poll"]
                include_unfinished = form.cleaned_data["include_unfinished"]
                
                # Создаем запись экспорта
                export_file = ExportFile.objects.create(
                    poll=poll,
                    include_unfinished=include_unfinished,
                    created_by=request.user,
                    filename=f"respondents_poll_{poll.id if poll else 'all'}.xlsx"
                )
                
                # Запускаем Celery task
                export_respondents_task.delay(export_file.id)
                
                from django.contrib import messages
                messages.success(
                    request,
                    f"Экспорт запущен! Файл будет готов через несколько минут. "
                    f"ID экспорта: {export_file.id}"
                )
                
                return admin.utils.response.PostResponse(
                    request,
                    admin.utils.response.redirect_to_referer(request, default='..')
                )
        else:
            form = PollFilterForm()

        context = {
            "opts": self.model._meta,
            "form": form,
            "title": "Асинхронный экспорт респондентов",
        }
        return TemplateResponse(request, "polls/respondents_export_form.html", context)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('respondent', 'question')
    list_filter = ('question__poll',)


@admin.register(NotificationCampaign)
class NotificationCampaignAdmin(admin.ModelAdmin):
    list_display = ['topic', 'total_users', 'sent_users', 'status', 'created_at', 'started_at', 'completed_at']
    list_filter = ['status', 'topic', 'created_at']
    readonly_fields = ['total_users', 'sent_users', 'created_at', 'started_at', 'completed_at', 'get_progress_percentage']
    search_fields = ['topic__name']
    actions = ['start_notification_campaign']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('topic', 'status', 'error_message')
        }),
        ('Статистика', {
            'fields': ('total_users', 'sent_users', 'get_progress_percentage'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_progress_percentage(self, obj):
        """Отобразить процент выполнения"""
        return f"{obj.get_progress_percentage()}%"
    get_progress_percentage.short_description = 'Прогресс'
    
    def start_notification_campaign(self, request, queryset):
        """Запустить кампанию уведомлений"""
        from .tasks import start_notification_campaign_task
        
        for campaign in queryset:
            if campaign.status == 'pending':
                start_notification_campaign_task.delay(campaign.id)
                campaign.status = 'processing'
                campaign.started_at = timezone.now()
                campaign.save()
        
        self.message_user(request, f"Запущено {queryset.count()} кампаний уведомлений")
    start_notification_campaign.short_description = "Запустить кампанию уведомлений"
