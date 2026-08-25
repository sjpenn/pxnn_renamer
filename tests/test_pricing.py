from backend.app.core.pricing import get_payment_options, get_payment_plan, PAYMENT_PLANS


def test_only_two_plans_are_offered():
    assert set(PAYMENT_PLANS.keys()) == {"single_export", "monthly_unlimited"}


def test_get_payment_options_returns_both_plans():
    options = get_payment_options()
    plan_keys = {o["key"] for o in options}
    assert plan_keys == {"single_export", "monthly_unlimited"}


def test_single_export_is_one_dollar_pay_per_turn():
    plan = get_payment_plan("single_export")
    assert plan["plan_type"] == "one_time"
    assert plan["amount_cents"] == 100
    assert plan["credits"] == 1
    assert plan["amount_label"] == "$1"
    assert plan.get("unlimited") is False


def test_monthly_unlimited_is_seven_ninety_nine_subscription():
    plan = get_payment_plan("monthly_unlimited")
    assert plan["plan_type"] == "subscription"
    assert plan["amount_cents"] == 799
    assert plan["amount_label"] == "$7.99"
    assert plan.get("unlimited") is True


def test_payment_options_carry_unlimited_flag():
    options = {o["key"]: o for o in get_payment_options()}
    assert options["single_export"]["unlimited"] is False
    assert options["monthly_unlimited"]["unlimited"] is True


def test_get_payment_plan_unknown_raises_key_error():
    try:
        get_payment_plan("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
