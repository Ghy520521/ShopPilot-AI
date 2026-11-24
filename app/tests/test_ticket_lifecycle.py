"""工单状态机：合法流转、非法流转拒绝、操作日志落库。"""
from app.tests.conftest import auth, register_and_login


def test_ticket_full_lifecycle(client):
    token = register_and_login(client, "life_user")
    created = client.post(
        "/api/tickets",
        json={"title": "物流慢", "description": "包裹三天没有物流更新", "priority": "high"},
        headers=auth(token),
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    r = client.post(
        f"/api/tickets/{ticket_id}/transition",
        json={"to_status": "in_progress", "note": "开始处理"},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"

    r = client.post(
        f"/api/tickets/{ticket_id}/transition",
        json={"to_status": "resolved"},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"

    r = client.post(
        f"/api/tickets/{ticket_id}/transition",
        json={"to_status": "closed"},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


def test_illegal_transition_rejected(client):
    token = register_and_login(client, "life_user2")
    created = client.post(
        "/api/tickets",
        json={"title": "退款失败", "description": "重复扣款", "priority": "medium"},
        headers=auth(token),
    )
    ticket_id = created.json()["id"]
    # open 不能直接到 resolved
    r = client.post(
        f"/api/tickets/{ticket_id}/transition",
        json={"to_status": "resolved"},
        headers=auth(token),
    )
    assert r.status_code == 409


def test_logs_recorded(client):
    token = register_and_login(client, "life_user3")
    created = client.post(
        "/api/tickets",
        json={"title": "账号异常", "description": "无法登录", "priority": "low"},
        headers=auth(token),
    )
    ticket_id = created.json()["id"]
    client.post(
        f"/api/tickets/{ticket_id}/transition",
        json={"to_status": "in_progress"},
        headers=auth(token),
    )
    detail = client.get(f"/api/tickets/{ticket_id}", headers=auth(token)).json()
    statuses = [log["to_status"] for log in detail["logs"]]
    assert "open" in statuses
    assert "in_progress" in statuses
