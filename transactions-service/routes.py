from flask import Blueprint, request, jsonify
from models import db, Transaction, TransactionEvent, WalletTransaction
from datetime import datetime
from sqlalchemy import or_, and_

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@bp.get("/")
def health():
    return {"service": "transactions", "status": "ok"}


def _transaction_json(t: Transaction):
    """Serialize transaction object"""
    return {
        "id": t.id,
        "transaction_code": t.transaction_code,
        "transaction_type": t.transaction_type,
        "user_id": t.user_id,
        "partner_id": t.partner_id,
        "order_id": t.order_id,
        "item": {
            "type": t.item_type,
            "id": t.item_id,
            "name": t.item_name,
            "image": t.item_image
        } if t.item_id else None,
        "amount": t.amount,
        "fee": t.fee,
        "net_amount": t.net_amount,
        "payment_method": t.payment_method,
        "status": t.status,
        "description": t.description,
        # Expose as 'metadata' in API while model stores 'extra_data'
        "metadata": t.extra_data,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None
    }


@bp.post("")
def create_transaction():
    """Tạo giao dịch mới (được gọi từ orders-service hoặc payment gateway)
    Idempotent-by-keys: (order_id) OR (transaction_type, user_id, partner_id, item_id, amount, status)
    Nếu tìm thấy giao dịch trùng khóa, trả về bản ghi cũ thay vì tạo mới.
    """
    d = request.get_json(force=True)

    # Idempotency guard
    existing = None
    try:
        if d.get("order_id") is not None:
            existing = Transaction.query.filter(
                Transaction.order_id == d.get("order_id"),
                Transaction.transaction_type == d.get("transaction_type"),
                Transaction.user_id == d.get("user_id"),
            ).order_by(Transaction.id.desc()).first()
        if existing is None:
            existing = Transaction.query.filter(
                Transaction.transaction_type == d.get("transaction_type"),
                Transaction.user_id == d.get("user_id"),
                Transaction.partner_id == d.get("partner_id"),
                Transaction.item_id == d.get("item_id"),
                Transaction.amount == d.get("amount"),
                Transaction.status == (d.get("status") or "pending"),
            ).order_by(Transaction.id.desc()).first()
    except Exception:
        existing = None

    if existing is not None:
        return _transaction_json(existing), 200

    # Generate unique transaction code
    import random
    transaction_code = f"TXN{datetime.utcnow().strftime('%Y%m%d')}{random.randint(100000, 999999)}"

    t = Transaction(
        transaction_code=transaction_code,
        transaction_type=d.get("transaction_type"),
        user_id=d.get("user_id"),
        partner_id=d.get("partner_id"),
        order_id=d.get("order_id"),
        item_type=d.get("item_type"),
        item_id=d.get("item_id"),
        item_name=d.get("item_name"),
        item_image=d.get("item_image"),
        amount=d.get("amount"),
        fee=d.get("fee", 0),
        net_amount=d.get("net_amount", d.get("amount")),
        payment_method=d.get("payment_method"),
        status=d.get("status", "pending"),
        description=d.get("description"),
        extra_data=d.get("metadata")
    )
    db.session.add(t)
    db.session.flush()

    # Tạo event đầu tiên
    event = TransactionEvent(
        transaction_id=t.id,
        event_type="created",
        actor_type="system",
        description="Giao dịch được tạo"
    )
    db.session.add(event)
    db.session.commit()

    return _transaction_json(t), 201


@bp.get("/user/<int:user_id>")
def get_user_transactions(user_id: int):
    """Lấy tất cả giao dịch của user - dùng cho tab Mua hàng + Bán hàng"""
    # Filters
    tab = request.args.get("tab", "purchase")  # purchase, sale, all
    status = request.args.get("status")
    transaction_type = request.args.get("type")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    keyword = request.args.get("keyword", "")
    
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    
    # Base query
    query = Transaction.query
    
    # Tab filter
    if tab == "purchase":
        # User là người mua - tìm giao dịch order_purchase của user
        query = query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type.in_(["order_purchase", "refund"])
        )
    elif tab == "sale":
        # User là người bán - tìm giao dịch order_sale hoặc partner_id = user
        query = query.filter(
            or_(
                and_(Transaction.user_id == user_id, Transaction.transaction_type == "order_sale"),
                and_(Transaction.partner_id == user_id, Transaction.transaction_type == "order_purchase")
            )
        )
    else:
        # All - cả mua lẫn bán
        query = query.filter(
            or_(Transaction.user_id == user_id, Transaction.partner_id == user_id)
        )
    
    # Status filter
    if status:
        query = query.filter(Transaction.status == status)
    
    # Type filter
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    # Date range
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            query = query.filter(Transaction.created_at >= from_dt)
        except:
            pass
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            query = query.filter(Transaction.created_at <= to_dt)
        except:
            pass
    
    # Keyword search
    if keyword:
        query = query.filter(
            or_(
                Transaction.transaction_code.ilike(f"%{keyword}%"),
                Transaction.item_name.ilike(f"%{keyword}%"),
                Transaction.description.ilike(f"%{keyword}%")
            )
        )
    
    # Order by newest first
    query = query.order_by(Transaction.created_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        "data": [_transaction_json(t) for t in pagination.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages
        }
    }


@bp.get("/wallet/<int:user_id>")
def get_wallet_transactions(user_id: int):
    """Lấy lịch sử ví điện tử của user"""
    wallet_type = request.args.get("wallet_type", "main")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    
    query = WalletTransaction.query.filter_by(user_id=user_id)
    
    if wallet_type:
        query = query.filter_by(wallet_type=wallet_type)
    
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            query = query.filter(WalletTransaction.created_at >= from_dt)
        except:
            pass
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            query = query.filter(WalletTransaction.created_at <= to_dt)
        except:
            pass
    
    query = query.order_by(WalletTransaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    data = []
    for wt in pagination.items:
        data.append({
            "id": wt.id,
            "transaction_id": wt.transaction_id,
            "wallet_type": wt.wallet_type,
            "transaction_type": wt.transaction_type,
            "amount": wt.amount,
            "balance_before": wt.balance_before,
            "balance_after": wt.balance_after,
            "description": wt.description,
            "status": wt.status,
            "created_at": wt.created_at.isoformat()
        })
    
    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages
        }
    }


@bp.get("/<int:transaction_id>")
def get_transaction_detail(transaction_id: int):
    """Lấy chi tiết giao dịch + timeline events"""
    t = Transaction.query.get_or_404(transaction_id)
    
    # Get timeline events
    events = TransactionEvent.query.filter_by(transaction_id=transaction_id)\
        .order_by(TransactionEvent.created_at.asc()).all()
    
    timeline = []
    for e in events:
        timeline.append({
            "id": e.id,
            "event_type": e.event_type,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "description": e.description,
            "metadata": e.extra_data,
            "created_at": e.created_at.isoformat()
        })
    
    result = _transaction_json(t)
    result["timeline"] = timeline
    
    return result


@bp.post("/<int:transaction_id>/events")
def add_transaction_event(transaction_id: int):
    """Thêm event vào timeline (khi có cập nhật trạng thái)"""
    t = Transaction.query.get_or_404(transaction_id)
    d = request.get_json(force=True)
    
    event = TransactionEvent(
        transaction_id=transaction_id,
        event_type=d.get("event_type"),
        actor_type=d.get("actor_type", "system"),
        actor_id=d.get("actor_id"),
        description=d.get("description"),
        extra_data=d.get("metadata")
    )
    db.session.add(event)
    
    # Update transaction status if provided
    if d.get("update_status"):
        t.status = d.get("update_status")
        t.updated_at = datetime.utcnow()
        
        if d.get("update_status") == "completed":
            t.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return {"ok": True, "event_id": event.id}


@bp.patch("/<int:transaction_id>")
def update_transaction_status(transaction_id: int):
    """Cập nhật trạng thái giao dịch"""
    t = Transaction.query.get_or_404(transaction_id)
    d = request.get_json(force=True)
    
    if "status" in d:
        t.status = d["status"]
        
        if d["status"] == "completed" and not t.completed_at:
            t.completed_at = datetime.utcnow()
    
    if "payment_method" in d:
        t.payment_method = d["payment_method"]
    
    if "metadata" in d:
        t.extra_data = d["metadata"]
    
    t.updated_at = datetime.utcnow()
    db.session.commit()
    
    return _transaction_json(t)


@bp.get("/admin/all")
def admin_get_all_transactions():
    """Admin xem tất cả giao dịch hệ thống"""
    # Filters
    user_id = request.args.get("user_id", type=int)
    status = request.args.get("status")
    transaction_type = request.args.get("type")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    keyword = request.args.get("keyword", "")
    
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    
    query = Transaction.query
    
    if user_id:
        query = query.filter(
            or_(Transaction.user_id == user_id, Transaction.partner_id == user_id)
        )
    
    if status:
        query = query.filter(Transaction.status == status)
    
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            query = query.filter(Transaction.created_at >= from_dt)
        except:
            pass
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            query = query.filter(Transaction.created_at <= to_dt)
        except:
            pass
    
    if keyword:
        query = query.filter(
            or_(
                Transaction.transaction_code.ilike(f"%{keyword}%"),
                Transaction.item_name.ilike(f"%{keyword}%")
            )
        )
    
    query = query.order_by(Transaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        "data": [_transaction_json(t) for t in pagination.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages
        }
    }


@bp.post("/wallet/deposit")
def create_wallet_deposit():
    """Tạo giao dịch nạp tiền vào ví"""
    d = request.get_json(force=True)
    user_id = d.get("user_id")
    amount = int(d.get("amount", 0))
    
    if amount <= 0:
        return {"error": "Invalid amount"}, 400
    
    # TODO: Get current balance from wallet service
    balance_before = 0  # Should query from wallet service
    balance_after = balance_before + amount
    
    # Create main transaction
    import random
    transaction_code = f"DEP{datetime.utcnow().strftime('%Y%m%d')}{random.randint(100000, 999999)}"
    
    t = Transaction(
        transaction_code=transaction_code,
        transaction_type="wallet_deposit",
        user_id=user_id,
        amount=amount,
        fee=0,
        net_amount=amount,
        payment_method=d.get("payment_method", "bank_transfer"),
        status="pending",
        description=f"Nạp tiền vào ví"
    )
    db.session.add(t)
    db.session.flush()
    
    # Create wallet transaction
    wt = WalletTransaction(
        transaction_id=t.id,
        user_id=user_id,
        wallet_type="main",
        transaction_type="deposit",
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        description=f"Nạp {amount:,} VND vào ví",
        status="pending"
    )
    db.session.add(wt)
    db.session.commit()
    
    return {"ok": True, "transaction_id": t.id, "transaction_code": transaction_code}, 201
