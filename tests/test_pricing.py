from backend.app.core.pricing import get_payment_options, get_payment_plan, PAYMENT_PLANS


def test_get_payment_options_includes_subscription_plans():
    options = get_payment_options()
    plan_keys = [o["key"] for o in options]
    assert "starter_monthly" in plan_keys
    assert "pro_monthly" in plan_keys
    assert "label_monthly" in plan_keys


def test_subscription_plans_have_plan_type():
    options = get_payment_options()
    sub_options = [o for o in options if o["key"].endswith("_monthly")]
    assert len(sub_options) == 3
    for opt in sub_options:
        assert opt["plan_type"] == "subscription"


def test_one_time_plans_have_plan_type():
    options = get_payment_options()
    one_time = [o for o in options if not o["key"].endswith("_monthly")]
    assert len(one_time) == 3
    for opt in one_time:
        assert opt["plan_type"] == "one_time"


def test_get_payment_plan_subscription_returns_plan_type():
    plan = get_payment_plan("pro_monthly")
    assert plan["plan_type"] == "subscription"
    assert plan["credits"] == 15
    assert plan["amount_cents"] == 2900


def test_get_payment_plan_unknown_raises_key_error():
    try:
        get_payment_plan("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
