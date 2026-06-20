from app import app
from models import db, AvatarFrame

FRAMES = [
    {
        'code': 'blue_crystal',
        'name': 'Ледяной кристалл',
        'description': 'Магическая рамка с синими кристаллами и цветами',
        'image': 'img/frames/blue_crystal.png',
        'rarity': 'epic',
        'is_premium': False,
        'sort_order': 10,
    },
        {
        'code': 'dark_rose',
        'name': 'Тёмная роза',
        'description': 'Загадочная рамка с тёмными розами и готическим узором',
        'image': 'img/frames/dark_rose.png',
        'rarity': 'legendary',
        'is_premium': False,
        'sort_order': 20,
    },
    # сюда добавляй новые рамки
]

with app.app_context():
    for data in FRAMES:
        frame = AvatarFrame.query.filter_by(code=data['code']).first()
        if frame:
            # Обновляем существующую
            for key, value in data.items():
                setattr(frame, key, value)
            print(f"🔄 Обновлено: {frame.name}")
        else:
            # Создаём новую
            frame = AvatarFrame(**data)
            db.session.add(frame)
            print(f"✅ Создано: {data['name']}")
    
    db.session.commit()
    print(f"\n🎉 Готово! Всего рамок в БД: {AvatarFrame.query.count()}")