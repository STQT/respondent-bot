import os
from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
from tablib import Dataset

from .models import ExportFile, Respondent
from .resources import RespondentExportResource


@shared_task(bind=True)
def export_respondents_task(self, export_file_id):
    """
    Celery task для экспорта респондентов в файл
    
    Args:
        export_file_id: ID записи ExportFile
    """
    try:
        # Получаем запись экспорта
        export_file = ExportFile.objects.get(id=export_file_id)
        
        # Обновляем статус на "обрабатывается"
        export_file.status = 'processing'
        export_file.save()
        
        # Создаем ресурс для экспорта
        resource = RespondentExportResource(
            poll=export_file.poll,
            include_unfinished=export_file.include_unfinished
        )
        
        # Получаем queryset
        queryset = resource.get_export_queryset(None)
        export_fields = resource.get_export_fields()
        
        # Создаем dataset
        dataset = Dataset(headers=[f.column_name for f in export_fields])
        
        # Добавляем данные
        for respondent in queryset:
            row = resource.export_resource(respondent)
            dataset.append([row.get(f.attribute or f.column_name, "") for f in export_fields])
        
        # Генерируем имя файла
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        poll_id = export_file.poll.id if export_file.poll else "all"
        filename = f"respondents_poll_{poll_id}_{timestamp}.xlsx"
        
        # Сохраняем файл
        file_content = dataset.xlsx
        export_file.file.save(filename, ContentFile(file_content), save=False)
        export_file.filename = filename
        export_file.status = 'completed'
        export_file.completed_at = timezone.now()
        export_file.save()
        
        return {
            'status': 'success',
            'export_file_id': export_file_id,
            'rows_exported': len(dataset),
            'filename': filename
        }
        
    except ExportFile.DoesNotExist:
        return {
            'status': 'error',
            'message': f'ExportFile with id {export_file_id} not found'
        }
    except Exception as e:
        # Обновляем статус на "ошибка"
        try:
            export_file = ExportFile.objects.get(id=export_file_id)
            export_file.status = 'failed'
            export_file.error_message = str(e)
            export_file.save()
        except ExportFile.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task
def cleanup_old_exports():
    """
    Удаляет старые файлы экспорта (старше 30 дней)
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    old_exports = ExportFile.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['completed', 'failed']
    )
    
    count = old_exports.count()
    old_exports.delete()
    
    return {
        'status': 'success',
        'deleted_count': count
    } 