import pytest
from risk_rules import label_risk, score_transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def base_tx(**overrides):
    """Minimal safe transaction — all signals at lowest risk."""
    tx = {
        "device_risk_score": 5,
        "is_international": 0,
        "amount_usd": 10.0,
        "velocity_24h": 1,
        "failed_logins_24h": 0,
        "prior_chargebacks": 0,
    }
    tx.update(overrides)
    return tx


# ---------------------------------------------------------------------------
# label_risk
# ---------------------------------------------------------------------------

class TestLabelRisk:
    def test_low_boundary(self):
        assert label_risk(0) == "low"
        assert label_risk(29) == "low"

    def test_medium_boundary(self):
        assert label_risk(30) == "medium"
        assert label_risk(59) == "medium"

    def test_high_boundary(self):
        assert label_risk(60) == "high"
        assert label_risk(100) == "high"

    def test_exact_thresholds(self):
        assert label_risk(10) == "low"
        assert label_risk(35) == "medium"
        assert label_risk(75) == "high"


# ---------------------------------------------------------------------------
# score_transaction — score bounds
# ---------------------------------------------------------------------------

class TestScoreBounds:
    def test_score_never_below_zero(self):
        # All signals at minimum — score must not go negative
        assert score_transaction(base_tx()) >= 0

    def test_score_never_above_100(self):
        # All signals at maximum — score must not exceed 100
        tx = base_tx(
            device_risk_score=90,
            is_international=1,
            amount_usd=5000,
            velocity_24h=10,
            failed_logins_24h=10,
            prior_chargebacks=3,
        )
        assert score_transaction(tx) <= 100


# ---------------------------------------------------------------------------
# Device risk score
# ---------------------------------------------------------------------------

class TestDeviceRiskScore:
    def test_high_device_risk_increases_score(self):
        """A device score >=70 is a compromise signal — must add risk."""
        low_device = score_transaction(base_tx(device_risk_score=5))
        high_device = score_transaction(base_tx(device_risk_score=80))
        assert high_device > low_device

    def test_medium_device_risk_increases_score(self):
        """A device score in 40-69 range should add moderate risk."""
        low_device = score_transaction(base_tx(device_risk_score=5))
        medium_device = score_transaction(base_tx(device_risk_score=50))
        assert medium_device > low_device

    def test_high_device_risk_scores_higher_than_medium(self):
        """A score >=70 should be riskier than a score in the 40-69 range."""
        medium_device = score_transaction(base_tx(device_risk_score=50))
        high_device = score_transaction(base_tx(device_risk_score=80))
        assert high_device > medium_device

    def test_very_high_device_risk_adds_significant_points(self):
        """A device score >=70 contributes 25 points — meaningful on its own."""
        score = score_transaction(base_tx(device_risk_score=90))
        assert score >= 25


# ---------------------------------------------------------------------------
# International transactions
# ---------------------------------------------------------------------------

class TestInternational:
    def test_international_increases_score(self):
        """International flag must add risk, not subtract it."""
        domestic = score_transaction(base_tx(is_international=0))
        international = score_transaction(base_tx(is_international=1))
        assert international > domestic

    def test_international_combined_with_high_device_risk(self):
        """Both signals present should compound the risk score."""
        neither = score_transaction(base_tx())
        both = score_transaction(base_tx(is_international=1, device_risk_score=80))
        assert both > neither


# ---------------------------------------------------------------------------
# Transaction velocity
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_high_velocity_increases_score(self):
        """>=6 transactions in 24h is a card-testing pattern — must add risk."""
        low_vel = score_transaction(base_tx(velocity_24h=1))
        high_vel = score_transaction(base_tx(velocity_24h=8))
        assert high_vel > low_vel

    def test_medium_velocity_increases_score(self):
        """3-5 transactions in 24h should also add some risk."""
        low_vel = score_transaction(base_tx(velocity_24h=1))
        med_vel = score_transaction(base_tx(velocity_24h=4))
        assert med_vel > low_vel

    def test_high_velocity_riskier_than_medium_velocity(self):
        """>=6 should score higher than 3-5."""
        med_vel = score_transaction(base_tx(velocity_24h=4))
        high_vel = score_transaction(base_tx(velocity_24h=8))
        assert high_vel > med_vel

    def test_card_testing_pattern_labels_high(self):
        """Classic card-testing combo (high velocity + international) must be high risk."""
        score = score_transaction(base_tx(
            velocity_24h=8,
            is_international=1,
            device_risk_score=75,
        ))
        assert label_risk(score) == "high"


# ---------------------------------------------------------------------------
# Prior chargebacks
# ---------------------------------------------------------------------------

class TestPriorChargebacks:
    def test_one_prior_chargeback_increases_score(self):
        """Any prior chargeback history must raise risk."""
        no_cb = score_transaction(base_tx(prior_chargebacks=0))
        one_cb = score_transaction(base_tx(prior_chargebacks=1))
        assert one_cb > no_cb

    def test_two_or_more_chargebacks_increases_score_more(self):
        """Repeat offenders must score higher than single-chargeback accounts."""
        one_cb = score_transaction(base_tx(prior_chargebacks=1))
        two_cb = score_transaction(base_tx(prior_chargebacks=2))
        assert two_cb > one_cb

    def test_repeat_offender_adds_significant_points(self):
        """2+ prior chargebacks contributes 20 points — meaningful on its own."""
        score = score_transaction(base_tx(prior_chargebacks=2))
        assert score >= 20


# ---------------------------------------------------------------------------
# Purchase amount
# ---------------------------------------------------------------------------

class TestAmount:
    def test_large_amount_adds_risk(self):
        small = score_transaction(base_tx(amount_usd=10))
        large = score_transaction(base_tx(amount_usd=1200))
        assert large > small

    def test_medium_amount_adds_moderate_risk(self):
        small = score_transaction(base_tx(amount_usd=10))
        medium = score_transaction(base_tx(amount_usd=600))
        assert medium > small

    def test_large_amount_riskier_than_medium_amount(self):
        medium = score_transaction(base_tx(amount_usd=600))
        large = score_transaction(base_tx(amount_usd=1200))
        assert large > medium


# ---------------------------------------------------------------------------
# Failed logins
# ---------------------------------------------------------------------------

class TestFailedLogins:
    def test_high_failed_logins_increases_score(self):
        clean = score_transaction(base_tx(failed_logins_24h=0))
        suspicious = score_transaction(base_tx(failed_logins_24h=6))
        assert suspicious > clean

    def test_moderate_failed_logins_increases_score(self):
        clean = score_transaction(base_tx(failed_logins_24h=0))
        moderate = score_transaction(base_tx(failed_logins_24h=3))
        assert moderate > clean


# ---------------------------------------------------------------------------
# End-to-end: known fraud profiles from the dataset
# ---------------------------------------------------------------------------

class TestKnownFraudProfiles:
    def test_account_1006_txn_50006(self):
        """Account 1006 (NG, 3 prior CB, 12 days old): $400 international, 7 velocity, 6 failed logins."""
        score = score_transaction({
            "device_risk_score": 77,
            "is_international": 1,
            "amount_usd": 399.99,
            "velocity_24h": 7,
            "failed_logins_24h": 6,
            "prior_chargebacks": 3,
        })
        assert label_risk(score) == "high", f"Expected high, got {label_risk(score)} (score={score})"

    def test_account_1011_txn_50011(self):
        """Account 1011 (RU, 1 prior CB): $1400 crypto, 8 velocity, 7 failed logins."""
        score = score_transaction({
            "device_risk_score": 85,
            "is_international": 1,
            "amount_usd": 1400.0,
            "velocity_24h": 8,
            "failed_logins_24h": 7,
            "prior_chargebacks": 1,
        })
        assert label_risk(score) == "high", f"Expected high, got {label_risk(score)} (score={score})"

    def test_account_1003_txn_50003(self):
        """Account 1003 (PH, new account): $1250 gift cards, 6 velocity, 5 failed logins."""
        score = score_transaction({
            "device_risk_score": 81,
            "is_international": 1,
            "amount_usd": 1250.0,
            "velocity_24h": 6,
            "failed_logins_24h": 5,
            "prior_chargebacks": 0,
        })
        assert label_risk(score) == "high", f"Expected high, got {label_risk(score)} (score={score})"

    def test_safe_transaction_stays_low(self):
        """A clean domestic low-amount transaction must not be flagged."""
        score = score_transaction({
            "device_risk_score": 8,
            "is_international": 0,
            "amount_usd": 45.20,
            "velocity_24h": 1,
            "failed_logins_24h": 0,
            "prior_chargebacks": 0,
        })
        assert label_risk(score) == "low", f"Expected low, got {label_risk(score)} (score={score})"
