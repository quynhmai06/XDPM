from flask import jsonify
from db import db

def ok(data=None, code=200):  return jsonify(data or {}), code
def err(msg, code=400):       return jsonify({"error": msg}), code

def commit_or_rollback():
    try: db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e
