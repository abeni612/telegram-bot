from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String, default='')
    full_name = Column(String, default='')
    subscription_end = Column(DateTime)
    is_approved = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    payment_proof_path = Column(String, default='')
    created_at = Column(DateTime, default=datetime.now)
    
    def is_subscription_active(self):
        if not self.is_approved or self.is_banned:
            return False
        if not self.subscription_end:
            return False
        return self.subscription_end > datetime.now()

class Database:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def add_user(self, user_data):
        try:
            user = User(**user_data)
            self.session.add(user)
            self.session.commit()
            return user
        except:
            self.session.rollback()
            return None
    
    def get_user(self, user_id):
        try:
            return self.session.query(User).filter_by(user_id=user_id).first()
        except:
            return None
    
    def update_user(self, user_id, update_data):
        try:
            user = self.get_user(user_id)
            if user:
                for key, value in update_data.items():
                    setattr(user, key, value)
                self.session.commit()
                return user
            return None
        except:
            self.session.rollback()
            return None
    
    def get_all_users(self):
        try:
            return self.session.query(User).all()
        except:
            return []
    
    def get_pending_approvals(self):
        try:
            return self.session.query(User).filter_by(is_approved=False).all()
        except:
            return []

db = Database()