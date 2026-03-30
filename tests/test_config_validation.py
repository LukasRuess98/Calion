"""Tests for energis.config.validation — config validation dataclasses."""

from energis.config.validation import ValidationError, ValidationResult


class TestValidationError:
    def test_creation(self):
        ve = ValidationError(
            severity="error",
            category="component",
            message="Missing capacity",
            location="heat_pumps.HP1",
        )
        assert ve.severity == "error"
        assert ve.location == "heat_pumps.HP1"


class TestValidationResult:
    def test_initial_state(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        assert vr.valid is True

    def test_add_error(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_error("component", "bad value", "HP1.capacity")
        assert vr.valid is False
        assert len(vr.errors) == 1
        assert vr.errors[0].severity == "error"
        assert vr.errors[0].location == "HP1.capacity"

    def test_add_warning(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_warning("network", "high velocity")
        assert vr.valid is True  # warnings don't invalidate
        assert len(vr.warnings) == 1

    def test_add_info(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_info("scenario", "using defaults")
        assert len(vr.info) == 1

    def test_multiple_errors(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_error("a", "msg1")
        vr.add_error("b", "msg2")
        vr.add_warning("c", "msg3")
        assert len(vr.errors) == 2
        assert len(vr.warnings) == 1
        assert vr.valid is False

    def test_print_summary_valid(self, caplog):
        import logging
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_info("scenario", "some note")
        with caplog.at_level(logging.INFO):
            vr.print_summary()  # must not raise

    def test_print_summary_invalid_with_location(self, caplog):
        import logging
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_error("component", "bad value", location="HP1.capacity")
        vr.add_warning("network", "check velocity")
        with caplog.at_level(logging.INFO):
            vr.print_summary()  # must not raise

    def test_add_error_no_location(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_error("component", "some error")
        assert vr.errors[0].location is None

    def test_add_warning_with_location(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_warning("network", "check flow", "N1")
        assert vr.warnings[0].location == "N1"

    def test_add_info_with_location(self):
        vr = ValidationResult(valid=True, errors=[], warnings=[], info=[])
        vr.add_info("scenario", "note", "section.field")
        assert vr.info[0].location == "section.field"
