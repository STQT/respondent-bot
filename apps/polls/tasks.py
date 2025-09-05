import os
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone
from django.core.files.base import ContentFile
from tablib import Dataset

from .models import ExportFile, Respondent
from .resources import RespondentExportResource


@shared_task(bind=True, soft_time_limit=1800, time_limit=2100)  # 30 min soft, 35 min hard
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
    except SoftTimeLimitExceeded:
        # Обработка таймаута
        try:
            export_file = ExportFile.objects.get(id=export_file_id)
            export_file.status = 'failed'
            export_file.error_message = 'Task timed out - export took too long'
            export_file.save()
        except ExportFile.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': 'Task timed out - export took too long'
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


@shared_task(bind=True, soft_time_limit=1800, time_limit=2100)  # 30 min soft, 35 min hard
def start_notification_campaign_task(self, campaign_id):
    """
    Основная задача для запуска кампании уведомлений.
    Разбивает пользователей на группы по 100 и запускает дочерние задачи.
    """
    try:
        from .models import NotificationCampaign, Poll
        from apps.users.models import TGUser
        
        campaign = NotificationCampaign.objects.get(id=campaign_id)
        campaign.status = 'processing'
        campaign.save()
        
        # Получаем всех пользователей, которые не прошли опрос по данной теме
        topic = campaign.topic
        users_who_completed = Respondent.objects.filter(
            poll=topic,
            finished_at__isnull=False
        ).values_list('tg_user_id', flat=True).distinct()
        
        # Получаем всех пользователей, которые НЕ прошли опрос по данной теме
        all_users = TGUser.objects.filter(is_active=True)
        users_to_notify = all_users.exclude(id__in=users_who_completed)
        
        campaign.total_users = users_to_notify.count()
        campaign.save()
        
        if campaign.total_users == 0:
            campaign.status = 'completed'
            campaign.completed_at = timezone.now()
            campaign.save()
            return {
                'status': 'success',
                'message': 'No users to notify for this topic'
            }
        
        # Разбиваем пользователей на группы по 100
        user_ids = list(users_to_notify.values_list('id', flat=True))
        chunk_size = 100
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
        
        # Запускаем дочерние задачи последовательно
        for i, chunk in enumerate(user_chunks):
            # Запускаем задачу с задержкой для последовательности
            send_notifications_chunk_task.apply_async(
                args=[campaign_id, chunk, i],
                countdown=i * 2  # 2 секунды между запусками
            )
        
        return {
            'status': 'success',
            'message': f'Started notification campaign for {campaign.total_users} users in {len(user_chunks)} chunks'
        }
        
    except NotificationCampaign.DoesNotExist:
        return {
            'status': 'error',
            'message': f'NotificationCampaign with id {campaign_id} not found'
        }
    except SoftTimeLimitExceeded:
        # Обработка таймаута
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.error_message = 'Task timed out - campaign took too long'
            campaign.save()
        except NotificationCampaign.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': 'Task timed out - campaign took too long'
        }
    except Exception as e:
        # Обновляем статус на "ошибка"
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.error_message = str(e)
            campaign.save()
        except NotificationCampaign.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task(bind=True, soft_time_limit=300, time_limit=360)  # 5 min soft, 6 min hard
def send_notifications_chunk_task(self, campaign_id, user_ids, chunk_index):
    """
    Отправляет уведомления группе пользователей (до 100 человек).
    Учитывает интервал отправки для избежания блокировки.
    """
    try:
        from .models import NotificationCampaign, Poll
        from apps.users.models import TGUser
        from apps.bot.misc import get_bot_instance
        from django.utils.translation import gettext as _
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        import time
        
        campaign = NotificationCampaign.objects.get(id=campaign_id)
        topic = campaign.topic
        
        # Получаем пользователей для уведомления
        # В TGUser.id хранится telegram_id (chat_id для бота)
        users = TGUser.objects.filter(id__in=user_ids, is_active=True)
        
        sent_count = 0
        failed_count = 0
        
        for i, user in enumerate(users):
            try:
                # Создаем клавиатуру с кнопками
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔄 Давом этиш", callback_data=f"poll_continue:{topic.uuid}"),
                        InlineKeyboardButton(text="♻️ Қайта бошлаш", callback_data=f"poll_restart:{topic.uuid}")
                    ]
                ])
                
                # Текст уведомления
                message_text = str(_("Сиз сўровномани тўлиқ якунламагансиз. Давом этасизми ёки қайта бошлайсизми?"))
                
                # Отправляем сообщение синхронно
                bot = get_bot_instance()
                # Используем синхронный метод для отправки
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        bot.send_message(
                            chat_id=user.id,  # В TGUser.id хранится telegram_id
                            text=message_text,
                            reply_markup=markup
                        )
                    )
                finally:
                    # Правильно закрываем сессию бота
                    loop.run_until_complete(bot.session.close())
                    loop.close()
                
                sent_count += 1
                
                # Обновляем счетчик в кампании
                campaign.sent_users += 1
                campaign.save()
                
                # Пауза между отправками (1 секунда)
                if i < len(users) - 1:  # Не ждем после последнего пользователя
                    time.sleep(1)
                
            except Exception as e:
                failed_count += 1
                # Логируем ошибку, но продолжаем с другими пользователями
                print(f"Failed to send notification to user {user.id}: {e}")
                continue
        
        # Проверяем, завершена ли вся кампания
        if campaign.sent_users >= campaign.total_users:
            campaign.status = 'completed'
            campaign.completed_at = timezone.now()
            campaign.save()
        
        return {
            'status': 'success',
            'chunk_index': chunk_index,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Chunk {chunk_index}: sent {sent_count}, failed {failed_count}'
        }
        
    except NotificationCampaign.DoesNotExist:
        return {
            'status': 'error',
            'message': f'NotificationCampaign with id {campaign_id} not found'
        }
    except SoftTimeLimitExceeded:
        return {
            'status': 'error',
            'message': f'Chunk {chunk_index} timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'chunk_index': chunk_index,
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


@shared_task(bind=True, soft_time_limit=1800, time_limit=2100)  # 30 min soft, 35 min hard
def start_broadcast_task(self, broadcast_id):
    """
    Основная задача для запуска рассылки поста.
    Разбивает пользователей на группы по 100 и запускает дочерние задачи.
    """
    try:
        from .models import BroadcastPost
        from apps.users.models import TGUser
        
        broadcast = BroadcastPost.objects.get(id=broadcast_id)
        broadcast.status = 'sending'
        broadcast.started_at = timezone.now()
        broadcast.save()
        
        # Получаем всех активных пользователей
        all_users = TGUser.objects.filter(is_active=True)
        broadcast.total_users = all_users.count()
        broadcast.save()
        
        if broadcast.total_users == 0:
            broadcast.status = 'sent'
            broadcast.completed_at = timezone.now()
            broadcast.save()
            return {
                'status': 'success',
                'message': 'No active users to send broadcast to'
            }
        
        # Разбиваем пользователей на группы по 100
        user_ids = list(all_users.values_list('id', flat=True))
        chunk_size = 100
        user_chunks = [user_ids[i:i + chunk_size] for i in range(0, len(user_ids), chunk_size)]
        
        # Запускаем дочерние задачи последовательно
        for i, chunk in enumerate(user_chunks):
            # Запускаем задачу с задержкой для последовательности
            send_broadcast_chunk_task.apply_async(
                args=[broadcast_id, chunk, i],
                countdown=i * 2  # 2 секунды между запусками
            )
        
        return {
            'status': 'success',
            'message': f'Started broadcast for {broadcast.total_users} users in {len(user_chunks)} chunks'
        }
        
    except BroadcastPost.DoesNotExist:
        return {
            'status': 'error',
            'message': f'BroadcastPost with id {broadcast_id} not found'
        }
    except SoftTimeLimitExceeded:
        # Обработка таймаута
        try:
            broadcast = BroadcastPost.objects.get(id=broadcast_id)
            broadcast.status = 'failed'
            broadcast.error_message = 'Task timed out - broadcast took too long'
            broadcast.save()
        except BroadcastPost.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': 'Task timed out - broadcast took too long'
        }
    except Exception as e:
        # Обновляем статус на "ошибка"
        try:
            broadcast = BroadcastPost.objects.get(id=broadcast_id)
            broadcast.status = 'failed'
            broadcast.error_message = str(e)
            broadcast.save()
        except BroadcastPost.DoesNotExist:
            pass
        
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task(bind=True, soft_time_limit=300, time_limit=360)  # 5 min soft, 6 min hard
def send_broadcast_chunk_task(self, broadcast_id, user_ids, chunk_index):
    """
    Отправляет пост группе пользователей (до 100 человек).
    Учитывает интервал отправки для избежания блокировки.
    """
    try:
        from .models import BroadcastPost
        from apps.users.models import TGUser
        from apps.bot.misc import get_bot_instance
        from aiogram.types import InputFile
        import time
        
        broadcast = BroadcastPost.objects.get(id=broadcast_id)
        
        # Получаем пользователей для рассылки
        users = TGUser.objects.filter(id__in=user_ids, is_active=True)
        
        sent_count = 0
        failed_count = 0
        
        for i, user in enumerate(users):
            try:
                # Отправляем сообщение синхронно
                bot = get_bot_instance()
                # Используем синхронный метод для отправки
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    if broadcast.image:
                        # Отправляем с изображением
                        photo = InputFile(broadcast.image.path)
                        loop.run_until_complete(
                            bot.send_photo(
                                chat_id=user.id,
                                photo=photo,
                                caption=f"<b>{broadcast.title}</b>\n\n{broadcast.content}",
                                parse_mode="HTML"
                            )
                        )
                    else:
                        # Отправляем только текст
                        loop.run_until_complete(
                            bot.send_message(
                                chat_id=user.id,
                                text=f"<b>{broadcast.title}</b>\n\n{broadcast.content}",
                                parse_mode="HTML"
                            )
                        )
                finally:
                    # Правильно закрываем сессию бота
                    loop.run_until_complete(bot.session.close())
                    loop.close()
                
                sent_count += 1
                
                # Обновляем счетчик в рассылке
                broadcast.sent_users += 1
                broadcast.save()
                
                # Пауза между отправками (1 секунда)
                if i < len(users) - 1:  # Не ждем после последнего пользователя
                    time.sleep(1)
                
            except Exception as e:
                failed_count += 1
                # Обновляем счетчик ошибок в рассылке
                broadcast.failed_users += 1
                broadcast.save()
                # Логируем ошибку, но продолжаем с другими пользователями
                print(f"Failed to send broadcast to user {user.id}: {e}")
                continue
        
        # Счетчики ошибок уже обновлены в цикле
        
        # Проверяем, завершена ли вся рассылка
        if broadcast.sent_users + broadcast.failed_users >= broadcast.total_users:
            broadcast.status = 'sent'
            broadcast.completed_at = timezone.now()
            broadcast.save()
        
        return {
            'status': 'success',
            'chunk_index': chunk_index,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'message': f'Chunk {chunk_index}: sent {sent_count}, failed {failed_count}'
        }
        
    except BroadcastPost.DoesNotExist:
        return {
            'status': 'error',
            'message': f'BroadcastPost with id {broadcast_id} not found'
        }
    except SoftTimeLimitExceeded:
        return {
            'status': 'error',
            'message': f'Chunk {chunk_index} timed out'
        }
    except Exception as e:
        return {
            'status': 'error',
            'chunk_index': chunk_index,
            'message': str(e)
        } 