"""AI 自然语言工单检索：结构化过滤、权限隔离、语义召回、安全边界。"""
from app.schemas.ticket import SearchPlan
from app.tests.conftest import auth, register_and_login


def test_structured_filter_excludes_other_users_and_unmatched(client):
    token_a = register_and_login(client, "alice_search")
    token_b = register_and_login(client, "bob_search")

    client.post(
        "/api/tickets",
        json={"title": "物流工单", "description": "快递长时间未更新，需要催件", "priority": "high"},
        headers=auth(token_a),
    )
    client.post(
        "/api/tickets",
        json={"title": "支付咨询", "description": "已经解决的老问题", "priority": "low"},
        headers=auth(token_a),
    )
    client.post(
        "/api/tickets",
        json={"title": "B的私密工单", "description": "不允许被 A 检索到", "priority": "high"},
        headers=auth(token_b),
    )

    resp = client.post(
        "/api/tickets/search",
        json={
            "question": "查一下最近7天还没有解决的高优先级物流工单",
            "page": 1,
            "page_size": 10,
        },
        headers=auth(token_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = [t["title"] for t in body["items"]]
    assert "物流工单" in titles
    # 低优先级 / 已解决类不命中
    assert "支付咨询" not in titles
    # 权限隔离：看不到 B 的工单
    assert "B的私密工单" not in titles

    plan = body["debug"]["plan"]
    assert plan["priority"] == "high"
    assert set(plan["statuses"]) == {"open", "in_progress"}


def test_semantic_recall_finds_similar_history_ticket(client):
    token = register_and_login(client, "sem_user")
    client.post(
        "/api/tickets",
        json={
            "title": "耳机断连",
            "description": "蓝牙耳机频繁断开连接，重新配对也没有用",
            "priority": "medium",
        },
        headers=auth(token),
    )
    resp = client.post(
        "/api/tickets/search",
        json={"question": "找出所有提到耳机断连、但尚未处理完成的案例", "page": 1, "page_size": 10},
        headers=auth(token),
    )
    body = resp.json()
    assert body["total"] >= 1
    assert any("耳机断连" in t["title"] for t in body["items"])
    # 调试信息同时给出结构化与语义两路命中数
    assert "structured_count" in body["debug"]
    assert "semantic_count" in body["debug"]


def test_search_plan_has_no_raw_sql_field():
    """安全边界：SearchPlan 白名单字段中不存在任何可承载原始 SQL 的字段。"""
    allowed = set(SearchPlan.model_fields.keys())
    assert "sql" not in allowed
    assert "query" not in allowed  # 通用 query 字段也不开放，防止被塞入原始语句
    assert allowed == {
        "statuses",
        "priority",
        "since",
        "until",
        "keywords",
        "order_no",
        "semantic_query",
    }
