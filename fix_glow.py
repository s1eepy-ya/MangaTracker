from app import app
from models import db, AvatarFrame

with app.app_context():
    frame = AvatarFrame.query.filter_by(code='dark_rose').first()
    if frame:
        frame.glow_class = 'glow-red'
        db.session.commit()
        print(f'✅ dark_rose → glow-red')
    
    frame2 = AvatarFrame.query.filter_by(code='blue_crystal').first()
    if frame2:
        frame2.glow_class = 'glow-blue'
        db.session.commit()
        print(f'✅ blue_crystal → glow-blue')