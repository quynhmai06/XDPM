from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, index=True)  # Link to specific order
    reviewer_id = db.Column(db.Integer, index=True, nullable=False)
    target_user_id = db.Column(db.Integer, index=True, nullable=False)
    reviewer_role = db.Column(db.String(20))  # 'buyer' or 'seller'
    
    # Multi-criteria ratings (1-5 each)
    rating_professionalism = db.Column(db.Integer)  # Tác phong giao dịch
    rating_payment = db.Column(db.Integer)          # Thanh toán (buyer only)
    rating_product = db.Column(db.Integer)          # Sản phẩm (seller only) 
    rating_cooperation = db.Column(db.Integer)      # Hợp tác khi có vấn đề
    rating_overall = db.Column(db.Integer, nullable=False)  # Tổng thể (1-5)
    
    comment = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=True)
    reported = db.Column(db.Boolean, default=False)
    helpful_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewHelpful(db.Model):
    """Track who voted a review as helpful"""
    __tablename__ = "review_helpful"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('review_id', 'user_id', name='_review_user_uc'),
    )


class ReviewReport(db.Model):
    """Track review abuse reports"""
    __tablename__ = "review_reports"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    reporter_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
