from models import db, User, Manga, Genre, Comment
from werkzeug.security import generate_password_hash

def seed_database():
    # Проверяем, есть ли уже данные в базе
    if User.query.first() is not None or Manga.query.first() is not None:
        return

    print("Сидинг базы данных...")

    # Создание жанров
    shonen = Genre(name="Сёнен")
    drama = Genre(name="Драма")
    action = Genre(name="Боевик")
    fantasy = Genre(name="Фэнтези")
    mystery = Genre(name="Мистика")
    horror = Genre(name="Ужасы")

    db.session.add_all([shonen, drama, action, fantasy, mystery, horror])
    db.session.commit()

    # Создание манги с привязкой к нашим обложкам
    manga1 = Manga(
        title="Убийца Акаси (Akashin Shounen)",
        original_title="악신소년",
        description="Главный герой оказывается вовлечен в битву с темными силами древних демонов. Обретя таинственную силу, он вынужден сражаться ради спасения своей жизни и раскрытия правды о мире.",
        cover_image="block1.jpg",
        release_year=2023,
        status="ONGOING",
        rating=8.2,
        chapters_count=52,
        volumes_count=2
    )
    manga1.genres.extend([action, mystery])

    manga2 = Manga(
        title="Магическая битва (Jujutsu Kaisen)",
        original_title="呪術廻戦",
        description="Юдзи Итадори — старшеклассник с выдающимися физическими способностями. Ради спасения друзей он съедает проклятый палец могущественного Двуликого Сукуны, становясь его сосудом, и оказывается затянут в мир шаманов и проклятий.",
        cover_image="block2.jpg",
        release_year=2018,
        status="COMPLETED",
        rating=9.4,
        chapters_count=271,
        volumes_count=28
    )
    manga2.genres.extend([shonen, action, mystery])

    manga3 = Manga(
        title="Атака титанов (Attack on Titan)",
        original_title="進撃の巨人",
        description="В течение ста лет человечество мирно живет внутри гигантских стен, защищающих от людоедов-титанов. Мир рушится, когда Колоссальный титан пробивает внешнюю стену. Эрен Йегер дает клятву истребить всех титанов.",
        cover_image="block3.png",
        release_year=2009,
        status="COMPLETED",
        rating=9.7,
        chapters_count=139,
        volumes_count=34
    )
    manga3.genres.extend([shonen, action, drama, fantasy])

    manga4 = Manga(
        title="Человек-бензопила (Chainsaw Man)",
        original_title="チェンソーマン",
        description="Дэндзи вынужден выплачивать гигантский долг своего покойного отца якудза. Он живет в нищете и охотится на демонов с помощью своего пса-демона Почиты. Погибнув, Дэндзи заключает контракт с Почитой и становится Человеком-бензопилой.",
        cover_image="block4.png",
        release_year=2018,
        status="ONGOING",
        rating=8.8,
        chapters_count=160,
        volumes_count=17
    )
    manga4.genres.extend([shonen, action, mystery, horror])

    manga5 = Manga(
        title="Берсерк (Berserk)",
        original_title="ベルセルク",
        description="История о наемнике Гатсе, родившемся от повешенной женщины. Он живет на поле боя и ищет цель своей жизни. Встретив харизматичного Гриффита, командира Отряда Сокола, Гатс оказывается втянут в интриги великих королевств.",
        cover_image="block5.png",
        release_year=1989,
        status="ONGOING",
        rating=9.9,
        chapters_count=376,
        volumes_count=42
    )
    manga5.genres.extend([action, drama, fantasy])

    manga6 = Manga(
        title="Токийский гуль (Tokyo Ghoul)",
        original_title="東京喰種",
        description="Канеки Кен — обычный студент университета. Он знакомится с девушкой Ридзэ, которая оказывается гулем — существом, питающимся человеческой плотью. После нападения Ридзэ Канеки оказывается в больнице, где ему пересаживают её органы.",
        cover_image="block6.png",
        release_year=2011,
        status="COMPLETED",
        rating=8.5,
        chapters_count=143,
        volumes_count=14
    )
    manga6.genres.extend([action, drama, mystery, horror])

    db.session.add_all([manga1, manga2, manga3, manga4, manga5, manga6])
    
    # Создание демо-комментария
    demo_comment = Comment(
        user_id=1,
        manga_id=2,
        content="Это просто шедевральное произведение! Развязка сюжета 10/10.",
    )
    
    # Создание администратора
    admin_user = User(
        username="admin",
        email="admin@manga.ru",
        password_hash=generate_password_hash("admin", method="scrypt"),
        role="ADMIN"
    )

    db.session.add(admin_user)
    db.session.commit()
    
    # Добавление демо-комментария после коммита пользователя
    db.session.add(demo_comment)
    db.session.commit()
    
    print("База данных успешно инициализирована!")
