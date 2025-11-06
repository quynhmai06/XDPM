from flask import Blueprint, request
from models import db, Review, ReviewHelpful, ReviewReport
from datetime import datetime, timedelta

bp = Blueprint("reviews", __name__, url_prefix="/reviews")


@bp.get("/")
def health():
    return {"service": "reviews", "status": "ok"}


def _review_json(r: Review):
    return {
        "id": r.id,
        "order_id": r.order_id,
        "reviewer_id": r.reviewer_id,
        "target_user_id": r.target_user_id,
        "reviewer_role": r.reviewer_role,
        "ratings": {
            "professionalism": r.rating_professionalism,
            "payment": r.rating_payment,
            "product": r.rating_product,
            "cooperation": r.rating_cooperation,
            "overall": r.rating_overall,
        },
        "comment": r.comment,
        "helpful_count": r.helpful_count,
        "reported": r.reported,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "can_edit": (datetime.utcnow() - r.created_at) < timedelta(hours=24),
    }


@bp.post("")
def create_review():
    """Create a new review (buyer→seller or seller→buyer)"""
    d = request.get_json(force=True)
    
    # Check if review already exists for this order+reviewer+role
    order_id = d.get("order_id")
    reviewer_id = d.get("reviewer_id")
    reviewer_role = d.get("reviewer_role")  # 'buyer' or 'seller'
    
    if order_id and reviewer_id and reviewer_role:
        existing = Review.query.filter_by(
            order_id=order_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role
        ).first()
        if existing:
            return {"error": "already_reviewed"}, 400
    
    r = Review(
        order_id=order_id,
        reviewer_id=reviewer_id,
        target_user_id=d.get("target_user_id"),
        reviewer_role=reviewer_role,
        rating_professionalism=d.get("rating_professionalism"),
        rating_payment=d.get("rating_payment") if reviewer_role == 'buyer' else None,
        rating_product=d.get("rating_product") if reviewer_role == 'seller' else None,
        rating_cooperation=d.get("rating_cooperation"),
        rating_overall=d.get("rating_overall"),
        comment=d.get("comment", ""),
        approved=True,
    )
    db.session.add(r)
    db.session.commit()
    return _review_json(r), 201


@bp.get("/user/<int:user_id>")
def list_reviews(user_id: int):
    """Get all approved reviews about this user"""
    q = Review.query.filter_by(target_user_id=user_id, approved=True, reported=False)
    data = [_review_json(r) for r in q.order_by(Review.created_at.desc()).all()]
    
    # Calculate average ratings
    if data:
        avg_overall = sum(r['ratings']['overall'] for r in data) / len(data)
        avg_prof = sum(r['ratings']['professionalism'] for r in data if r['ratings']['professionalism']) / len([r for r in data if r['ratings']['professionalism']]) if any(r['ratings']['professionalism'] for r in data) else None
    else:
        avg_overall = 0
        avg_prof = None
    
    return {
        "data": data,
        "summary": {
            "total_reviews": len(data),
            "average_overall": round(avg_overall, 2) if data else 0,
            "average_professionalism": round(avg_prof, 2) if avg_prof else None,
        }
    }


@bp.get("/by-reviewer/<int:reviewer_id>")
def list_by_reviewer(reviewer_id: int):
    """Get all reviews written BY this user"""
    q = Review.query.filter_by(reviewer_id=reviewer_id)
    data = [_review_json(r) for r in q.order_by(Review.created_at.desc()).all()]
    return {"data": data}


@bp.get("/pending/<int:user_id>")
def pending_reviews(user_id: int):
    """Get orders where user needs to submit review
    This requires checking orders-service for completed orders without reviews
    For now, return empty - implement when integrating with orders
    """
    # TODO: Query orders-service for completed orders by user_id
    # TODO: Check which ones don't have reviews yet
    return {"data": [], "message": "Implement after orders integration"}


@bp.patch("/<int:review_id>")
def update_review(review_id: int):
    """Update review within 24h window"""
    r = Review.query.get_or_404(review_id)
    
    # Check 24h edit window
    if (datetime.utcnow() - r.created_at) > timedelta(hours=24):
        return {"error": "edit_window_expired"}, 400
    
    d = request.get_json(force=True)
    requester_id = d.get("requester_id")
    
    # Verify ownership
    if r.reviewer_id != requester_id:
        return {"error": "not_authorized"}, 403
    
    # Update ratings
    if "rating_professionalism" in d:
        r.rating_professionalism = d["rating_professionalism"]
    if "rating_payment" in d:
        r.rating_payment = d["rating_payment"]
    if "rating_product" in d:
        r.rating_product = d["rating_product"]
    if "rating_cooperation" in d:
        r.rating_cooperation = d["rating_cooperation"]
    if "rating_overall" in d:
        r.rating_overall = d["rating_overall"]
    if "comment" in d:
        r.comment = d["comment"]
    
    r.updated_at = datetime.utcnow()
    db.session.commit()
    return _review_json(r)


@bp.delete("/<int:review_id>")
def delete_review(review_id: int):
    """Delete review within 24h window"""
    r = Review.query.get_or_404(review_id)
    
    requester_id = request.args.get("requester_id", type=int)
    
    # Verify ownership
    if r.reviewer_id != requester_id:
        return {"error": "not_authorized"}, 403
    
    # Check 24h window
    if (datetime.utcnow() - r.created_at) > timedelta(hours=24):
        return {"error": "delete_window_expired"}, 400
    
    db.session.delete(r)
    db.session.commit()
    return {"ok": True}


@bp.post("/<int:review_id>/helpful")
def mark_helpful(review_id: int):
    """Vote review as helpful"""
    r = Review.query.get_or_404(review_id)
    d = request.get_json(force=True)
    user_id = d.get("user_id")
    
    # Check if already voted
    existing = ReviewHelpful.query.filter_by(
        review_id=review_id,
        user_id=user_id
    ).first()
    
    if existing:
        return {"error": "already_voted"}, 400
    
    vote = ReviewHelpful(review_id=review_id, user_id=user_id)
    db.session.add(vote)
    r.helpful_count += 1
    db.session.commit()
    return {"ok": True, "helpful_count": r.helpful_count}


@bp.post("/<int:review_id>/report")
def report_review(review_id: int):
    """Report review for violation"""
    r = Review.query.get_or_404(review_id)
    d = request.get_json(force=True)
    reporter_id = d.get("reporter_id")
    reason = d.get("reason", "")
    
    # Check if already reported by this user
    existing = ReviewReport.query.filter_by(
        review_id=review_id,
        reporter_id=reporter_id
    ).first()
    
    if existing:
        return {"error": "already_reported"}, 400
    
    report = ReviewReport(
        review_id=review_id,
        reporter_id=reporter_id,
        reason=reason
    )
    db.session.add(report)
    
    # Auto-flag if multiple reports (>= 3)
    report_count = ReviewReport.query.filter_by(review_id=review_id).count() + 1
    if report_count >= 3:
        r.reported = True
        r.approved = False  # Hide until admin reviews
    
    db.session.commit()
    return {"ok": True, "report_count": report_count}
