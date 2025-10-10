from flask import Blueprint, request
from models import db, Review

bp = Blueprint("reviews", __name__, url_prefix="/reviews")


@bp.get("/")
def health():
    return {"service": "reviews", "status": "ok"}


@bp.post("")
def create_review():
    d = request.get_json(force=True)
    r = Review(
        reviewer_id=d.get("reviewer_id"),
        target_user_id=d.get("target_user_id"),
        rating=d.get("rating"),
        comment=d.get("comment"),
        approved=True,
    )
    db.session.add(r)
    db.session.commit()
    return {"id": r.id}, 201


@bp.get("/user/<int:user_id>")
def list_reviews(user_id: int):
    q = Review.query.filter_by(target_user_id=user_id, approved=True)
    data = [{
        "id": r.id,
        "reviewer_id": r.reviewer_id,
        "rating": r.rating,
        "comment": r.comment,
        "created_at": r.created_at.isoformat(),
    } for r in q.order_by(Review.created_at.desc()).all()]
    return {"data": data}
