from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
from config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String)
    full_name = Column(String)
    phone_number = Column(String)
    subscription_end = Column(DateTime)
    is_approved = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    payment_proof_path = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    
    def is_subscription_active(self):
        return self.is_approved and not self.is_banned and self.subscription_end and self.subscription_end > datetime.now()

class PaymentHistory(Base):
    __tablename__ = 'payment_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Float, default=0.0)
    payment_date = Column(DateTime, default=datetime.now)
    approved = Column(Boolean, default=False)
    approved_by = Column(Integer)  # Admin ID who approved
    approved_date = Column(DateTime)

class Database:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def add_user(self, user_data):
        user = User(**user_data)
        self.session.add(user)
        self.session.commit()
        return user
    
    def get_user(self, user_id):
        return self.session.query(User).filter_by(user_id=user_id).first()
    
    def update_user(self, user_id, update_data):
        user = self.get_user(user_id)
        if user:
            for key, value in update_data.items():
                setattr(user, key, value)
            self.session.commit()
        return user
    
    def get_all_users(self):
        return self.session.query(User).all()
    
    def get_pending_approvals(self):
        return self.session.query(User).filter_by(is_approved=False).all()
    
    def get_banned_users(self):
        return self.session.query(User).filter_by(is_banned=True).all()
    
    def add_payment_history(self, payment_data):
        payment = PaymentHistory(**payment_data)
        self.session.add(payment)
        self.session.commit()
        return payment
    
    def get_user_payments(self, user_id):
        return self.session.query(PaymentHistory).filter_by(user_id=user_id).all()

db = Database()