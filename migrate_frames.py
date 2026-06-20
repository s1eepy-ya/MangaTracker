"""
Миграция: добавляет поле active_frame_id в users и создаёт таблицы avatar_frames + user_unlocked_frames
"""
from sqlalchemy import inspect, text
from app import app
from models import db, AvatarFrame


def column_exists(table_name, column_name):
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name):
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()


with app.app_context():
    print("🔧 Запуск миграции системы рамок...\n")

    # 1. Создаём новые таблицы (avatar_frames, user_unlocked_frames)
    db.create_all()
    print("✅ Таблицы avatar_frames и user_unlocked_frames созданы (или уже есть)")

    # 2. Добавляем колонку active_frame_id в users
    if not column_exists('users', 'active_frame_id'):
        with db.engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN active_frame_id INTEGER REFERENCES avatar_frames(id)"
            ))
            conn.commit()
        print("✅ Колонка users.active_frame_id добавлена")
    else:
        print("ℹ️  Колонка users.active_frame_id уже существует")

    # 3. Сидим стартовую рамку
    if not AvatarFrame.query.filter_by(code='blue_crystal').first():
        frame = AvatarFrame(
            code='blue_crystal',
            name='Ледяной кристалл',
            description='Магическая рамка с синими кристаллами и цветами',
            image='img/frames/blue_crystal.png',
            rarity='epic',
            is_premium=False,
            sort_order=10,
        )
        db.session.add(frame)
        db.session.commit()
        print("✅ Стартовая рамка 'blue_crystal' добавлена")
    else:
        print("ℹ️  Стартовая рамка уже есть")

    print("\n🎉 Миграция завершена!")