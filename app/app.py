import os
from datetime import datetime
from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func
from app.models import Transaction, db


def create_app(test_config=None):
    app = Flask(__name__)

    # Default configuration with PostgreSQL in mind, falling back to SQLite
    database_url = os.environ.get(
        'DATABASE_URL',
        'sqlite:///expense_tracker.db'
    )
    # Handle SQLAlchemy PostgreSQL URI format (postgres:// vs postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception:
            # On serverless (Vercel), database may not be available at
            # cold start. Tables should be pre-created in production.
            pass

    @app.route('/')
    def index():
        category_filter = request.args.get('category', '').strip()
        query = Transaction.query
        if category_filter:
            query = query.filter_by(category=category_filter)

        transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()

        # Unique categories for filter dropdown
        categories_query = db.session.query(Transaction.category).distinct().all()
        categories = sorted([c[0] for c in categories_query if c[0]])

        return render_template(
            'index.html',
            transactions=transactions,
            categories=categories,
            selected_category=category_filter
        )

    @app.route('/add', methods=['POST'])
    def add_transaction():
        # Handle both JSON payloads and Form submissions
        if request.is_json:
            data = request.get_json() or {}
            amount = data.get('amount')
            category = data.get('category')
            date_str = data.get('date')
            note = data.get('note', '')
        else:
            amount = request.form.get('amount')
            category = request.form.get('category')
            date_str = request.form.get('date')
            note = request.form.get('note', '')

        if not amount or not category:
            return jsonify({'error': 'Amount and category are required'}), 400

        try:
            amount_val = float(amount)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount value'}), 400

        tx_date = datetime.today().date()
        if date_str:
            try:
                tx_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Date must be in YYYY-MM-DD format'}), 400

        new_tx = Transaction(
            amount=amount_val,
            category=category.strip(),
            date=tx_date,
            note=note.strip() if note else None
        )
        db.session.add(new_tx)
        db.session.commit()

        if request.is_json:
            return jsonify({
                'message': 'Transaction added successfully',
                'transaction': new_tx.to_dict()
            }), 201
        return redirect(url_for('index'))

    @app.route('/summary', methods=['GET'])
    def summary():
        # Calculate summary statistics
        total_spent = db.session.query(func.sum(Transaction.amount)).scalar() or 0.0
        tx_count = db.session.query(func.count(Transaction.id)).scalar() or 0

        # Category breakdown
        category_breakdown = (
            db.session.query(Transaction.category, func.sum(Transaction.amount))
            .group_by(Transaction.category)
            .all()
        )

        categories = {cat: float(total) for cat, total in category_breakdown}

        return jsonify({
            'total_amount': round(float(total_spent), 2),
            'transaction_count': tx_count,
            'by_category': categories
        }), 200

    @app.route('/chart-data', methods=['GET'])
    def chart_data():
        # Returns aggregated spending by category formatted specifically for Chart.js
        results = (
            db.session.query(Transaction.category, func.sum(Transaction.amount))
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )

        labels = [row[0] for row in results]
        data = [round(float(row[1]), 2) for row in results]

        return jsonify({
            'labels': labels,
            'datasets': [{
                'label': 'Spending by Category ($)',
                'data': data
            }]
        }), 200

    @app.route('/delete/<int:tx_id>', methods=['POST', 'DELETE'])
    def delete_transaction(tx_id):
        tx = Transaction.query.get_or_404(tx_id)
        db.session.delete(tx)
        db.session.commit()
        if request.is_json or request.method == 'DELETE':
            return jsonify({'message': 'Transaction deleted successfully'}), 200
        return redirect(url_for('index'))

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
