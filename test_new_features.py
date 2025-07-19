#!/usr/bin/env python3
"""Interactive test script for new daily/monthly view features."""

import os
import subprocess
import sys


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def run_command(cmd):
    """Run a command and handle interruption."""
    try:
        # Change to src directory
        original_dir = os.getcwd()
        src_dir = os.path.join(os.path.dirname(__file__), 'src')
        os.chdir(src_dir)
        
        # Run the command
        subprocess.run(cmd, shell=True)
        
        # Change back
        os.chdir(original_dir)
    except KeyboardInterrupt:
        print("\n\nReturning to menu...")
    except Exception as e:
        print(f"\nError: {e}")
    
    input("\nPress Enter to continue...")


def main_menu():
    """Display main menu and handle user choice."""
    while True:
        clear_screen()
        print("=" * 60)
        print("Claude Code Usage Monitor - New Features Test")
        print("=" * 60)
        print("\nThis runs from source code without modifying system installation")
        print("\nAvailable options:")
        print("\n1. Show Daily Statistics")
        print("2. Show Monthly Statistics")
        print("3. Show Realtime Monitoring (default)")
        print("4. Show Daily with Dark Theme")
        print("5. Show Monthly with Light Theme")
        print("6. Show Help")
        print("7. Exit")
        print("\n" + "=" * 60)
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == '1':
            print("\nShowing daily statistics... (Press Ctrl+C to stop)")
            run_command("python3 -m claude_monitor --view daily")
        
        elif choice == '2':
            print("\nShowing monthly statistics... (Press Ctrl+C to stop)")
            run_command("python3 -m claude_monitor --view monthly")
        
        elif choice == '3':
            print("\nShowing realtime monitoring... (Press Ctrl+C to stop)")
            run_command("python3 -m claude_monitor")
        
        elif choice == '4':
            print("\nShowing daily statistics with dark theme... (Press Ctrl+C to stop)")
            run_command("python3 -m claude_monitor --view daily --theme dark")
        
        elif choice == '5':
            print("\nShowing monthly statistics with light theme... (Press Ctrl+C to stop)")
            run_command("python3 -m claude_monitor --view monthly --theme light")
        
        elif choice == '6':
            print("\nShowing help...")
            run_command("python3 -m claude_monitor --help")
        
        elif choice == '7':
            print("\nExiting...")
            break
        
        else:
            print("\nInvalid choice. Please try again.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        # Check if we're in the right directory
        if not os.path.exists('src/claude_monitor'):
            print("Error: Please run this script from the Claude-Code-Usage-Monitor directory")
            sys.exit(1)
        
        main_menu()
        
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)