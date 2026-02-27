from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth.models import User
from datetime import datetime, timedelta
import pytz # Для работы с часовыми поясами, если БД использует UTC

# !!! ЗАМЕНИТЕ 'app' НА ИМЯ ВАШЕГО ПРИЛОЖЕНИЯ (например, 'barbag') !!!
APP_NAME = 'app'

# Импортируйте вашу модель InfTablo
try:
    from app.models import InfTablo
except ImportError:
    print(f"🚨 Ошибка импорта: Не удалось импортировать InfTablo из {APP_NAME}.models")
    exit()

class Command(BaseCommand):
    help = 'Проверяет LogEntry на предмет массовых удалений рейсов InfTablo через Django Admin за последний месяц.'

    def handle(self, *args, **options):
        # Устанавливаем часовой пояс. Используйте pytz.timezone('Europe/Moscow') или ваш часовой пояс.
        # Если вы уверены, что БД и Django настроены на UTC, можно использовать pytz.utc
        timezone = pytz.utc 
        
        # Определяем диапазон: с начала месяца до текущего момента
        end_date = datetime.now(timezone)
        start_date = end_date - timedelta(days=32) # Проверяем последние 32 дня
        
        self.stdout.write(self.style.NOTICE(f"Начало проверки логов удалений для модели InfTablo в приложении '{APP_NAME}'..."))
        self.stdout.write(self.style.NOTICE(f"Диапазон поиска: с {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}"))

        # 1. ПОИСК ID МОДЕЛИ
        try:
            inftablo_content_type = ContentType.objects.get(app_label=APP_NAME, model='inftablo')
            inftablo_id = inftablo_content_type.id
            self.stdout.write(self.style.SUCCESS(f"✅ ID модели InfTablo: {inftablo_id}"))
        except ContentType.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"🚨 Ошибка: ContentType для InfTablo не найден. Проверьте имя приложения ('{APP_NAME}')."))
            return

        # 2. ПОИСК ЗАПИСЕЙ ОБ УДАЛЕНИИ (СНЯТ ЛИМИТ)
        deletion_logs = LogEntry.objects.filter(
            content_type_id=inftablo_id,
            action_flag=DELETION,
            action_time__gte=start_date, # Фильтруем от начала периода
            action_time__lte=end_date    # Фильтруем до конца периода
        ).order_by('-action_time') 
        
        total_deleted = deletion_logs.count()

        if total_deleted > 0:
            self.stdout.write(self.style.WARNING(f"\n=== 🔴 НАЙДЕНО {total_deleted} УДАЛЕНИЙ РЕЙСОВ ЧЕРЕЗ DJANGO ADMIN (За последние 32 дня) ===\n"))
            
            # Показываем только первые 20 записей для примера, чтобы не забивать консоль
            for log in deletion_logs[:20]: 
                try:
                    username = User.objects.get(pk=log.user_id).username
                except User.DoesNotExist:
                    username = f"Неизвестный пользователь (ID: {log.user_id})"
                
                self.stdout.write(f"  Время: {log.action_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.stdout.write(f"  Пользователь: {username}")
                self.stdout.write(f"  Удалено: {log.object_repr}")
                self.stdout.write("-" * 40)
            
            if total_deleted > 20:
                 self.stdout.write(self.style.WARNING(f"..."))  
                 self.stdout.write(self.style.WARNING(f"Отображено только 20 записей. Всего удалений: {total_deleted}."))
                 self.stdout.write(self.style.WARNING(f"Все эти удаления произошли в момент: {deletion_logs.first().action_time.strftime('%Y-%m-%d %H:%M:%S')} пользователем: {User.objects.get(pk=deletion_logs.first().user_id).username}"))
            
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ Записи об удалении рейсов InfTablo через Django Admin не найдены за этот период."))
            self.stdout.write(self.style.NOTICE("Если рейсы действительно пропали, проблема, скорее всего, в скрипте синхронизации FIDS (который не использует LogEntry)."))