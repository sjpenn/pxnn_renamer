
import sys
import os

# Add the project root to sys.path
sys.path.append('/Users/sjpenn/DEV-SITES/DEMOS/music_renamer')

from backend.app.database.session import SessionLocal, Base, engine
from backend.app.database.models import User
from backend.app.core.security import hash_password

def test_registration_logic():
    print("Testing registration logic...")
    db = SessionLocal()
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        username = "testuser_debug"
        password = "testpassword123"
        
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            db.delete(existing)
            db.commit()
            print(f"Deleted existing user {username}")
            
        user = User(
            username=username,
            password_hash=hash_password(password)
        )
        db.add(user)
        db.flush()
        print(f"User flushed. ID: {user.id}")
        
        db.commit()
        print("User committed successfully.")
        
    except Exception as e:
        print(f"Error during registration logic: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_registration_logic()
