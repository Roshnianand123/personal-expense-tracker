import pytest
from app.app import create_app
from app.models import Transaction, db


@pytest.fixture
def client():
    # Configure app with isolated in-memory SQLite database for unit tests
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    })

    with test_app.test_client() as test_client:
        with test_app.app_context():
            db.create_all()
            yield test_client
            db.session.remove()
            db.drop_all()


def test_add_transaction(client):
    """Test 1: Verify POST /add saves a new transaction."""
    payload = {
        'amount': 55.75,
        'category': 'Groceries',
        'date': '2026-09-10',
        'note': 'Weekly food supplies'
    }
    response = client.post('/add', json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == 'Transaction added successfully'
    assert data['transaction']['amount'] == 55.75
    assert data['transaction']['category'] == 'Groceries'
    assert data['transaction']['note'] == 'Weekly food supplies'

    # Verify directly from database
    tx = Transaction.query.first()
    assert tx is not None
    assert tx.amount == 55.75
    assert tx.category == 'Groceries'


def test_summary_endpoint(client):
    """Test 2: Verify GET /summary calculates accurate totals and category breakdown."""
    # Add multiple transactions across different categories
    client.post('/add', json={'amount': 100.0, 'category': 'Rent', 'date': '2026-09-01'})
    client.post('/add', json={'amount': 50.0, 'category': 'Food', 'date': '2026-09-02'})
    client.post('/add', json={'amount': 25.5, 'category': 'Food', 'date': '2026-09-03'})

    response = client.get('/summary')
    assert response.status_code == 200
    data = response.get_json()

    assert data['total_amount'] == 175.50
    assert data['transaction_count'] == 3
    assert data['by_category']['Rent'] == 100.0
    assert data['by_category']['Food'] == 75.5


def test_chart_data_endpoint(client):
    """Test 3: Verify GET /chart-data formats JSON payload correctly for Chart.js."""
    client.post('/add', json={'amount': 200.0, 'category': 'Electronics', 'date': '2026-09-01'})
    client.post('/add', json={'amount': 80.0, 'category': 'Utilities', 'date': '2026-09-02'})

    response = client.get('/chart-data')
    assert response.status_code == 200
    data = response.get_json()

    assert 'labels' in data
    assert 'datasets' in data
    assert len(data['datasets']) == 1
    assert data['labels'] == ['Electronics', 'Utilities']
    assert data['datasets'][0]['data'] == [200.0, 80.0]
    assert data['datasets'][0]['label'] == 'Spending by Category ($)'
