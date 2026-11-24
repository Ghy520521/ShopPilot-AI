"""订单与库存：事务扣减、幂等键、库存不足回滚。"""
from app.models.product import Category, Product
from app.tests.conftest import auth, register_and_login


def _seed_category_and_product(db_session, stock: int = 10) -> Product:
    cat = Category(name="数码")
    db_session.add(cat)
    db_session.commit()
    product = Product(name="耳机 Pro", sku="HP-001", price=199.0, stock=stock, category_id=cat.id)
    db_session.add(product)
    db_session.commit()
    return product


def _login_user(client, username="user1"):
    return register_and_login(client, username)


def test_order_deducts_stock_and_idempotency_returns_same_order(client, db_session, admin_token):
    product = _seed_category_and_product(db_session, stock=5)
    token = _login_user(client)

    # 加购物车 -> 下单
    client.post("/api/cart", json={"product_id": product.id, "quantity": 2}, headers=auth(token))
    payload = {"idempotency_key": "idem-key-0001-uuid", "use_cart": True}
    resp = client.post("/api/orders", json=payload, headers=auth(token))
    assert resp.status_code == 201
    first = resp.json()
    assert first["status"] == "pending_payment"

    # 同一幂等键重复请求：返回同一订单，不重复扣库存
    resp2 = client.post("/api/orders", json=payload, headers=auth(token))
    assert resp2.status_code == 201
    assert resp2.json()["id"] == first["id"]

    db_session.refresh(product)
    assert product.stock == 5 - 2  # 只扣一次


def test_insufficient_stock_rolls_back(client, db_session):
    product = _seed_category_and_product(db_session, stock=1)
    token = _login_user(client, "user2")

    payload = {
        "idempotency_key": "idem-key-0002-uuid",
        "use_cart": False,
        "items": [{"product_id": product.id, "quantity": 3}],
    }
    resp = client.post("/api/orders", json=payload, headers=auth(token))
    assert resp.status_code == 409
    # 事务已回滚，重新查询商品实例确认库存未变
    fresh = db_session.get(Product, product.id)
    assert fresh.stock == 1
