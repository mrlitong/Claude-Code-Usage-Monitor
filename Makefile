# Makefile for Claude Code Usage Monitor

.PHONY: test test-coverage test-quick test-new install-test clean help

# Default target
help:
	@echo "Claude Code Usage Monitor - Test Commands"
	@echo "========================================"
	@echo "make test          - Run standard tests"
	@echo "make test-coverage - Run full coverage tests"
	@echo "make test-quick    - Run quick tests (no coverage)"
	@echo "make test-new      - Test new features only"
	@echo "make install-test  - Install test dependencies"
	@echo "make clean         - Clean test files"

# Run standard tests
test:
	@python3 run_tests.py

# Run full coverage tests
test-coverage:
	@python3 run_tests.py --coverage

# Run quick tests
test-quick:
	@python3 run_tests.py --quick

# Test new features only
test-new:
	@python3 run_tests.py --new

# Install test dependencies
install-test:
	@echo "Installing test dependencies..."
	@pip3 install pytest pytest-cov

# Clean test generated files
clean:
	@echo "Cleaning test files..."
	@rm -rf htmlcov/
	@rm -rf .coverage
	@rm -rf .pytest_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"