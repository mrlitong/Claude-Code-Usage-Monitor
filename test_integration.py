#!/usr/bin/env python3
"""Test script for the integrated daily/monthly view features."""

import subprocess
import sys
import time


def test_view_modes():
    """Test different view modes."""
    print("Testing Claude Code Usage Monitor with new view modes...")
    print("=" * 60)
    
    # Test commands
    test_commands = [
        # Default realtime view
        ["python3", "-m", "claude_monitor", "--help"],
        
        # Daily view
        ["python3", "-m", "claude_monitor", "--view", "daily"],
        
        # Monthly view
        ["python3", "-m", "claude_monitor", "--view", "monthly"],
    ]
    
    for i, cmd in enumerate(test_commands):
        print(f"\nTest {i+1}: Running {' '.join(cmd[2:])}")
        print("-" * 40)
        
        try:
            # Run the command with timeout
            if "--help" in cmd:
                # Help command should complete immediately
                result = subprocess.run(
                    cmd,
                    cwd="src",
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                print("Exit code:", result.returncode)
                if result.stdout:
                    print("Output preview:")
                    print(result.stdout[:500])
                if result.stderr:
                    print("Errors:", result.stderr[:500])
            else:
                # View commands need manual interruption
                print("Starting view mode (press Ctrl+C to stop)...")
                proc = subprocess.Popen(
                    cmd,
                    cwd="src",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Let it run for 3 seconds
                time.sleep(3)
                
                # Terminate the process
                proc.terminate()
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    if stdout:
                        print("Output preview:")
                        print(stdout[:500])
                    if stderr:
                        print("Errors:", stderr[:500])
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print("Process killed after timeout")
                
        except subprocess.TimeoutExpired:
            print("Command timed out")
        except Exception as e:
            print(f"Error running command: {e}")
        
        print("-" * 40)


def main():
    """Main test function."""
    print("Claude Code Usage Monitor Integration Test")
    print("=" * 60)
    print("This script will test the new daily and monthly view modes.")
    print("Make sure you're in the Claude-Code-Usage-Monitor directory.")
    print()
    
    try:
        test_view_modes()
        print("\n✅ All tests completed!")
        print("\nTo use the new features:")
        print("  claude-monitor --view daily    # Show daily statistics")
        print("  claude-monitor --view monthly  # Show monthly statistics")
        print("  claude-monitor                 # Default realtime view")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())