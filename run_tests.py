#!/usr/bin/env python3
"""
Python script to run all tests with one command
Supports Windows/Linux/macOS
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import List, Optional

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_colored(text: str, color: str = RESET) -> None:
    """Print colored text"""
    print(f"{color}{text}{RESET}")


def check_pytest_installed() -> bool:
    """Check if pytest is installed"""
    try:
        subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def install_pytest() -> bool:
    """Install pytest and pytest-cov"""
    print_colored("Installing pytest and pytest-cov...", YELLOW)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", 
                       "pytest", "pytest-cov"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def run_tests(mode: str = "standard") -> int:
    """Run tests"""
    # Set environment variables
    env = os.environ.copy()
    src_path = Path(__file__).parent / "src"
    env["PYTHONPATH"] = str(src_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    
    # Base command
    cmd = [sys.executable, "-m", "pytest", "src/tests/", "-v", "--tb=short"]
    
    if mode == "coverage":
        # Full coverage test
        print_colored("📊 Running full coverage test...", BLUE)
        cmd.extend([
            "--cov=src/claude_monitor",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ])
    elif mode == "quick":
        # Quick test
        print_colored("⚡ Running quick test...", BLUE)
        # Don't add coverage parameters
    elif mode == "new":
        # Test new features only
        print_colored("🆕 Running new feature tests only...", BLUE)
        cmd = [sys.executable, "-m", "pytest", 
               "src/tests/test_aggregator.py",
               "src/tests/test_table_views.py", 
               "-v", "--tb=short"]
    else:
        # Standard test
        print_colored("🚀 Running standard test...", BLUE)
        cmd.extend([
            "--cov=src/claude_monitor/data",
            "--cov=src/claude_monitor/ui",
            "--cov-report=term",
        ])
    
    # Add color support
    if sys.platform != "win32":
        cmd.append("--color=yes")
    
    # Run tests
    try:
        result = subprocess.run(cmd, env=env)
        return result.returncode
    except Exception as e:
        print_colored(f"Error running tests: {e}", RED)
        return 1


def show_menu() -> str:
    """Show interactive menu"""
    print_colored("\n🧪 Claude Code Usage Monitor - Test Runner", BOLD)
    print("=" * 50)
    print("\nPlease select test mode:")
    print("1. Standard test (with basic coverage)")
    print("2. Full coverage test (generate HTML report)")
    print("3. Quick test (no coverage)")
    print("4. Test new features only")
    print("5. Exit")
    
    choice = input("\nPlease enter option (1-5) [default: 1]: ").strip() or "1"
    return choice


def main():
    """Main function"""
    # Check pytest
    if not check_pytest_installed():
        print_colored("❌ pytest not found", RED)
        response = input("Install pytest? (y/n) [y]: ").strip().lower()
        if response in ["", "y", "yes"]:
            if install_pytest():
                print_colored("✅ pytest installed successfully!", GREEN)
            else:
                print_colored("❌ pytest installation failed, please install manually:", RED)
                print("   pip install pytest pytest-cov")
                sys.exit(1)
        else:
            print("Please install pytest before running tests")
            sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["--help", "-h"]:
            print("Usage: python run_tests.py [options]")
            print("\nOptions:")
            print("  --coverage, -c    Run full coverage test")
            print("  --quick, -q       Run quick test (no coverage)")
            print("  --new, -n         Run new feature tests only")
            print("  --help, -h        Show help information")
            print("\nEnter interactive mode when no arguments provided")
            sys.exit(0)
        elif arg in ["--coverage", "-c"]:
            exit_code = run_tests("coverage")
        elif arg in ["--quick", "-q"]:
            exit_code = run_tests("quick")
        elif arg in ["--new", "-n"]:
            exit_code = run_tests("new")
        else:
            print_colored(f"❌ Unknown argument: {arg}", RED)
            print("Use --help for help")
            sys.exit(1)
    else:
        # Interactive mode
        choice = show_menu()
        if choice == "1":
            exit_code = run_tests("standard")
        elif choice == "2":
            exit_code = run_tests("coverage")
        elif choice == "3":
            exit_code = run_tests("quick")
        elif choice == "4":
            exit_code = run_tests("new")
        elif choice == "5":
            print_colored("👋 Exit", YELLOW)
            sys.exit(0)
        else:
            print_colored("❌ Invalid option", RED)
            sys.exit(1)
    
    # Show results
    if exit_code == 0:
        print_colored("\n✅ All tests passed!", GREEN)
        if Path("htmlcov/index.html").exists():
            print_colored("\n📊 Coverage report generated:", YELLOW)
            print(f"   {Path('htmlcov/index.html').absolute()}")
    else:
        print_colored("\n❌ Tests failed!", RED)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()