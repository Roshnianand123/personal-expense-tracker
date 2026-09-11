import logging
import os
from datetime import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user
)
from sqlalchemy import func, inspect, text
from app.models import Transaction, User, db

logger = logging.getLogger(__name__)


def _migrate_database(app):
    """Ensure the database schema is up-to-date.

    Handles the case where the 'transactions' table was created before
    the auth feature and is missing the 'user_id' column.
    """
    try:
        inspector = inspect(db.engine)

        if 'transactions' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('transactions')]
            if 'user_id' not in columns:
                logger.info("Migrating: adding 'user_id' column to 'transactions'")
                with db.engine.connect() as conn:
                    conn.execute(text(
                        'ALTER TABLE transactions '
                        'ADD COLUMN user_id INTEGER REFERENCES users(id)'
                    ))
                    conn.commit()
                logger.info("Migration complete: 'user_id' column added.")
    except Exception as exc:
        logger.warning("Auto-migration check failed: %s", exc)


def create_app(test_config=None):
    app = Flask(__name__)

    # Secret key for session encryption
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 'dev-secret-key-change-in-production'
    )

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

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        try:
            db.create_all()
            _migrate_database(app)
        except Exception as exc:
            # Log the error so it surfaces in Vercel / container logs
            logger.error("Database initialisation failed: %s", exc)

    # ── Error Handler ────────────────────────────────────────────

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("500 Internal Server Error: %s", error)
        db.session.rollback()
        return (
            "<h1>Internal Server Error</h1>"
            "<p>Something went wrong. Check the application logs.</p>"
        ), 500

    # ── Diagnostic Route ─────────────────────────────────────────

    @app.route('/health')
    def health():
        """Quick health check — verifies DB connectivity and schema."""
        info = {'status': 'ok', 'database': 'unknown', 'tables': []}
        try:
            inspector = inspect(db.engine)
            info['tables'] = inspector.get_table_names()
            if 'transactions' in info['tables']:
                cols = [c['name'] for c in inspector.get_columns('transactions')]
                info['transactions_columns'] = cols
            if 'users' in info['tables']:
                cols = [c['name'] for c in inspector.get_columns('users')]
                info['users_columns'] = cols
            info['database'] = 'connected'
        except Exception as exc:
            info['status'] = 'error'
            info['database'] = str(exc)
        return jsonify(info)

    # ── Auth Routes ──────────────────────────────────────────────

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')

            if not username or not email or not password:
                flash('All fields are required.', 'error')
                return redirect(url_for('register'))

            if password != confirm:
                flash('Passwords do not match.', 'error')
                return redirect(url_for('register'))

            if len(password) < 6:
                flash('Password must be at least 6 characters.', 'error')
                return redirect(url_for('register'))

            if User.query.filter_by(email=email).first():
                flash('Email already registered. Please login.', 'error')
                return redirect(url_for('register'))

            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('index'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next')
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(next_page or url_for('index'))

            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    # ── Dashboard Routes ─────────────────────────────────────────

    @app.route('/')
    @login_required
    def index():
        category_filter = request.args.get('category', '').strip()
        query = Transaction.query.filter_by(user_id=current_user.id)
        if category_filter:
            query = query.filter_by(category=category_filter)

        transactions = query.order_by(
            Transaction.date.desc(), Transaction.id.desc()
        ).all()

        # Unique categories for filter dropdown (user's own)
        categories_query = (
            db.session.query(Transaction.category)
            .filter_by(user_id=current_user.id)
            .distinct()
            .all()
        )
        categories = sorted([c[0] for c in categories_query if c[0]])

        return render_template(
            'index.html',
            transactions=transactions,
            categories=categories,
            selected_category=category_filter
        )

    @app.route('/add', methods=['POST'])
    @login_required
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
            note=note.strip() if note else None,
            user_id=current_user.id
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
    @login_required
    def summary():
        # Calculate summary statistics (user's own data only)
        user_txns = Transaction.query.filter_by(user_id=current_user.id)
        total_spent = (
            db.session.query(func.sum(Transaction.amount))
            .filter_by(user_id=current_user.id)
            .scalar() or 0.0
        )
        tx_count = user_txns.count()

        # Category breakdown
        category_breakdown = (
            db.session.query(
                Transaction.category, func.sum(Transaction.amount)
            )
            .filter_by(user_id=current_user.id)
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
    @login_required
    def chart_data():
        # Returns aggregated spending by category for Chart.js (user's own)
        results = (
            db.session.query(
                Transaction.category, func.sum(Transaction.amount)
            )
            .filter_by(user_id=current_user.id)
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
    @login_required
    def delete_transaction(tx_id):
        tx = Transaction.query.get_or_404(tx_id)
        # Ensure users can only delete their own transactions
        if tx.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        db.session.delete(tx)
        db.session.commit()
        if request.is_json or request.method == 'DELETE':
            return jsonify({'message': 'Transaction deleted successfully'}), 200
        return redirect(url_for('index'))

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
