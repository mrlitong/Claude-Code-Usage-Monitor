"""Simplified CLI entry point using pydantic-settings."""

import argparse
import contextlib
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, NoReturn, Optional, Union

from rich.console import Console

from claude_monitor import __version__
from claude_monitor.cli.bootstrap import (
    ensure_directories,
    init_timezone,
    setup_environment,
    setup_logging,
)
from claude_monitor.core.plans import Plans, PlanType, get_token_limit
from claude_monitor.core.settings import Settings
from claude_monitor.data.aggregator import UsageAggregator
from claude_monitor.data.analysis import analyze_usage
from claude_monitor.error_handling import report_error
from claude_monitor.monitoring.orchestrator import MonitoringOrchestrator
from claude_monitor.terminal.manager import (
    enter_alternate_screen,
    handle_cleanup_and_exit,
    handle_error_and_exit,
    restore_terminal,
    setup_terminal,
)
from claude_monitor.terminal.themes import get_themed_console, print_themed
from claude_monitor.ui.display_controller import DisplayController
from claude_monitor.ui.table_views import TableViewsController

# Type aliases for CLI callbacks
DataUpdateCallback = Callable[[Dict[str, Any]], None]
SessionChangeCallback = Callable[[str, str, Optional[Dict[str, Any]]], None]


def get_standard_claude_paths() -> List[str]:
    """Get list of standard Claude data directory paths to check."""
    return ["~/.claude/projects", "~/.config/claude/projects"]


def discover_claude_data_paths(custom_paths: Optional[List[str]] = None) -> List[Path]:
    """Discover all available Claude data directories.

    Args:
        custom_paths: Optional list of custom paths to check instead of standard ones

    Returns:
        List of Path objects for existing Claude data directories
    """
    paths_to_check: List[str] = (
        [str(p) for p in custom_paths] if custom_paths else get_standard_claude_paths()
    )

    discovered_paths: List[Path] = []

    for path_str in paths_to_check:
        path = Path(path_str).expanduser().resolve()
        if path.exists() and path.is_dir():
            discovered_paths.append(path)

    return discovered_paths


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point with direct pydantic-settings integration."""
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        print(f"claude-monitor {__version__}")
        return 0

    try:
        settings = Settings.load_with_last_used(argv)

        setup_environment()
        ensure_directories()

        if settings.log_file:
            setup_logging(settings.log_level, settings.log_file, disable_console=True)
        else:
            setup_logging(settings.log_level, disable_console=True)

        init_timezone(settings.timezone)

        args = settings.to_namespace()

        _run_monitoring(args)

        return 0

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        return 0
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Monitor failed: {e}", exc_info=True)
        traceback.print_exc()
        return 1


def _run_monitoring(args: argparse.Namespace) -> None:
    """Main monitoring implementation without facade."""
    view_mode = getattr(args, "view", "realtime")
    if hasattr(args, "theme") and args.theme:
        console = get_themed_console(force_theme=args.theme.lower())
    else:
        console = get_themed_console()

    old_terminal_settings = setup_terminal()
    live_display_active: bool = False

    try:
        data_paths: List[Path] = discover_claude_data_paths()
        if not data_paths:
            print_themed("No Claude data directory found", style="error")
            return

        data_path: Path = data_paths[0]
        logger = logging.getLogger(__name__)
        logger.info(f"Using data path: {data_path}")

        # Handle different view modes
        if view_mode in ["daily", "monthly"]:
            _run_table_view(args, data_path, view_mode, console)
            return

        token_limit: int = _get_initial_token_limit(args, str(data_path))

        display_controller = DisplayController()
        display_controller.live_manager._console = console

        refresh_per_second: float = getattr(args, "refresh_per_second", 0.75)
        logger.info(
            f"Display refresh rate: {refresh_per_second} Hz ({1000 / refresh_per_second:.0f}ms)"
        )
        logger.info(f"Data refresh rate: {args.refresh_rate} seconds")

        live_display = display_controller.live_manager.create_live_display(
            auto_refresh=True, console=console, refresh_per_second=refresh_per_second
        )

        loading_display = display_controller.create_loading_display(
            args.plan, args.timezone
        )

        enter_alternate_screen()

        live_display_active = False

        try:
            # Enter live context and show loading screen immediately
            live_display.__enter__()
            live_display_active = True
            live_display.update(loading_display)

            orchestrator = MonitoringOrchestrator(
                update_interval=args.refresh_rate
                if hasattr(args, "refresh_rate")
                else 10,
                data_path=str(data_path),
            )
            orchestrator.set_args(args)

            # Setup monitoring callback
            def on_data_update(monitoring_data: Dict[str, Any]) -> None:
                """Handle data updates from orchestrator."""
                try:
                    data: Dict[str, Any] = monitoring_data.get("data", {})
                    blocks: List[Dict[str, Any]] = data.get("blocks", [])

                    logger.debug(f"Display data has {len(blocks)} blocks")
                    if blocks:
                        active_blocks: List[Dict[str, Any]] = [
                            b for b in blocks if b.get("isActive")
                        ]
                        logger.debug(f"Active blocks: {len(active_blocks)}")
                        if active_blocks:
                            total_tokens: int = active_blocks[0].get("totalTokens", 0)
                            logger.debug(f"Active block tokens: {total_tokens}")

                    renderable = display_controller.create_data_display(
                        data, args, monitoring_data.get("token_limit", token_limit)
                    )

                    if live_display:
                        live_display.update(renderable)

                except Exception as e:
                    logger.error(f"Display update error: {e}", exc_info=True)
                    report_error(
                        exception=e,
                        component="cli_main",
                        context_name="display_update_error",
                    )

            # Register callbacks
            orchestrator.register_update_callback(on_data_update)

            # Optional: Register session change callback
            def on_session_change(
                event_type: str, session_id: str, session_data: Optional[Dict[str, Any]]
            ) -> None:
                """Handle session changes."""
                if event_type == "session_start":
                    logger.info(f"New session detected: {session_id}")
                elif event_type == "session_end":
                    logger.info(f"Session ended: {session_id}")

            orchestrator.register_session_callback(on_session_change)

            # Start monitoring
            orchestrator.start()

            # Wait for initial data
            logger.info("Waiting for initial data...")
            if not orchestrator.wait_for_initial_data(timeout=10.0):
                logger.warning("Timeout waiting for initial data")

            # Main loop - live display is already active
            while True:
                import time

                time.sleep(1)
        finally:
            # Stop monitoring first
            if "orchestrator" in locals():
                orchestrator.stop()

            # Exit live display context if it was activated
            if live_display_active:
                with contextlib.suppress(Exception):
                    live_display.__exit__(None, None, None)

    except KeyboardInterrupt:
        # Clean exit from live display if it's active
        if "live_display" in locals():
            with contextlib.suppress(Exception):
                live_display.__exit__(None, None, None)
        handle_cleanup_and_exit(old_terminal_settings)
    except Exception as e:
        # Clean exit from live display if it's active
        if "live_display" in locals():
            with contextlib.suppress(Exception):
                live_display.__exit__(None, None, None)
        handle_error_and_exit(old_terminal_settings, e)
    finally:
        restore_terminal(old_terminal_settings)


def _get_initial_token_limit(
    args: argparse.Namespace, data_path: Union[str, Path]
) -> int:
    """Get initial token limit for the plan."""
    logger = logging.getLogger(__name__)
    plan: str = getattr(args, "plan", PlanType.PRO.value)

    # For custom plans, check if custom_limit_tokens is provided first
    if plan == "custom":
        # If custom_limit_tokens is explicitly set, use it
        if hasattr(args, "custom_limit_tokens") and args.custom_limit_tokens:
            custom_limit = int(args.custom_limit_tokens)
            print_themed(
                f"Using custom token limit: {custom_limit:,} tokens",
                style="info",
            )
            return custom_limit

        # Otherwise, analyze usage data to calculate P90
        print_themed("Analyzing usage data to determine cost limits...", style="info")

        try:
            # Use quick start mode for faster initial load
            usage_data: Optional[Dict[str, Any]] = analyze_usage(
                hours_back=96 * 2,
                quick_start=False,
                use_cache=False,
                data_path=str(data_path),
            )

            if usage_data and "blocks" in usage_data:
                blocks: List[Dict[str, Any]] = usage_data["blocks"]
                token_limit: int = get_token_limit(plan, blocks)

                print_themed(
                    f"P90 session limit calculated: {token_limit:,} tokens",
                    style="info",
                )

                return token_limit

        except Exception as e:
            logger.warning(f"Failed to analyze usage data: {e}")

        # Fallback to default limit
        print_themed("Using default limit as fallback", style="warning")
        return Plans.DEFAULT_TOKEN_LIMIT

    # For standard plans, just get the limit
    return get_token_limit(plan)


def handle_application_error(
    exception: Exception,
    component: str = "cli_main",
    exit_code: int = 1,
) -> NoReturn:
    """Handle application-level errors with proper logging and exit.

    Args:
        exception: The exception that occurred
        component: Component where the error occurred
        exit_code: Exit code to use when terminating
    """
    logger = logging.getLogger(__name__)

    # Log the error with traceback
    logger.error(f"Application error in {component}: {exception}", exc_info=True)

    # Report to error handling system
    from claude_monitor.error_handling import report_application_startup_error

    report_application_startup_error(
        exception=exception,
        component=component,
        additional_context={
            "exit_code": exit_code,
            "args": sys.argv,
        },
    )

    # Print user-friendly error message
    print(f"\nError: {exception}", file=sys.stderr)
    print("For more details, check the log files.", file=sys.stderr)

    sys.exit(exit_code)


def validate_cli_environment() -> Optional[str]:
    """Validate the CLI environment and return error message if invalid.

    Returns:
        Error message if validation fails, None if successful
    """
    try:
        # Check Python version compatibility
        if sys.version_info < (3, 8):
            return f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}"

        # Check for required dependencies
        required_modules = ["rich", "pydantic", "watchdog"]
        missing_modules: List[str] = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        if missing_modules:
            return f"Missing required modules: {', '.join(missing_modules)}"

        return None

    except Exception as e:
        return f"Environment validation failed: {e}"


def _run_table_view(
    args: argparse.Namespace, data_path: Path, view_mode: str, console: Console
) -> None:
    """Run table view mode (daily or monthly) with enhanced error handling.

    Args:
        args: Command line arguments
        data_path: Path to Claude data directory
        view_mode: View mode ('daily' or 'monthly')
        console: Rich console instance
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running {view_mode} view mode")

    # Validate inputs
    if view_mode not in ["daily", "monthly"]:
        logger.error(f"Invalid view mode: {view_mode}")
        print_themed(f"Invalid view mode: {view_mode}. Must be 'daily' or 'monthly'", style="error")
        return

    if not data_path.exists():
        logger.error(f"Data path does not exist: {data_path}")
        print_themed(f"Data path does not exist: {data_path}", style="error")
        return

    if not data_path.is_dir():
        logger.error(f"Data path is not a directory: {data_path}")
        print_themed(f"Data path is not a directory: {data_path}", style="error")
        return

    try:
        # Analyze usage data with specific error handling
        try:
            usage_data = analyze_usage(
                hours_back=96 * 30,  # 30 days of data
                quick_start=False,
                use_cache=True,
                data_path=str(data_path),
            )
        except FileNotFoundError as e:
            logger.error(f"Data file not found: {e}")
            print_themed("No Claude usage data files found. Please use Claude Code to generate some data.", style="warning")
            return
        except PermissionError as e:
            logger.error(f"Permission denied accessing data: {e}")
            print_themed("Permission denied accessing usage data. Check file permissions.", style="error")
            return
        except Exception as e:
            logger.error(f"Failed to analyze usage data: {e}", exc_info=True)
            print_themed(f"Failed to analyze usage data: {e}", style="error")
            return

        if not usage_data:
            logger.info("No usage data returned from analysis")
            print_themed(f"No usage data found for {view_mode} view", style="warning")
            return

        if "blocks" not in usage_data:
            logger.warning("Usage data missing 'blocks' key")
            print_themed("Usage data format is invalid (missing blocks)", style="error")
            return

        # Create aggregator
        aggregator = UsageAggregator()

        # Extract entries from blocks with error handling
        from claude_monitor.core.models import UsageEntry
        from claude_monitor.utils.time_utils import TimezoneHandler

        entries = []
        blocks = usage_data.get("blocks", [])

        if not blocks:
            logger.info("No blocks found in usage data")
            print_themed("No usage blocks found in the data", style="warning")
            return

        # Initialize timezone handler once
        tz_handler = TimezoneHandler()

        for block_idx, block in enumerate(blocks):
            try:
                # Skip gap blocks
                if block.get("isGap", False):
                    continue

                block_entries = block.get("entries", [])
                for entry_idx, entry_data in enumerate(block_entries):
                    try:
                        # Parse timestamp with error handling
                        timestamp_str = entry_data.get("timestamp", "")
                        if not timestamp_str:
                            logger.warning(f"Missing timestamp in block {block_idx}, entry {entry_idx}")
                            continue

                        timestamp = tz_handler.parse_timestamp(timestamp_str)

                        # Create entry with validation
                        entry = UsageEntry(
                            timestamp=timestamp,
                            input_tokens=max(0, int(entry_data.get("inputTokens", 0))),
                            output_tokens=max(0, int(entry_data.get("outputTokens", 0))),
                            cache_creation_tokens=max(0, int(entry_data.get("cacheCreationTokens", 0))),
                            cache_read_tokens=max(0, int(entry_data.get("cacheReadTokens", 0))),
                            cost_usd=max(0.0, float(entry_data.get("costUSD", 0.0))),
                            model=str(entry_data.get("model", "")),
                            message_id=str(entry_data.get("messageId", "")),
                            request_id=str(entry_data.get("requestId", "")),
                        )
                        entries.append(entry)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid entry data in block {block_idx}, entry {entry_idx}: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error processing entry: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error processing block {block_idx}: {e}")
                continue

        if not entries:
            logger.info("No valid entries extracted from blocks")
            print_themed("No valid usage entries found in the data", style="warning")
            return

        # Log entry count for debugging
        logger.info(f"Extracted {len(entries)} valid entries")

        # Aggregate data based on view type
        try:
            if view_mode == "daily":
                aggregated_data = aggregator.aggregate_daily(entries)
            else:  # monthly
                aggregated_data = aggregator.aggregate_monthly(entries)
        except Exception as e:
            logger.error(f"Failed to aggregate data: {e}", exc_info=True)
            print_themed(f"Failed to aggregate {view_mode} data: {e}", style="error")
            return

        if not aggregated_data:
            print_themed(f"No {view_mode} data to display after aggregation", style="warning")
            return

        # Calculate totals
        try:
            totals = aggregator.calculate_totals(aggregated_data)
        except Exception as e:
            logger.error(f"Failed to calculate totals: {e}", exc_info=True)
            print_themed(f"Failed to calculate totals: {e}", style="error")
            return

        # Create table view controller
        table_controller = TableViewsController()

        # Get timezone with validation
        timezone = getattr(args, "timezone", "UTC")
        if not timezone:
            timezone = "UTC"

        # Create and display table with error handling
        try:
            if view_mode == "daily":
                table = table_controller.create_daily_table(aggregated_data, totals, timezone)
            else:
                table = table_controller.create_monthly_table(aggregated_data, totals, timezone)

            # Display summary panel
            period = f"Last {len(aggregated_data)} {view_mode[:-2]}{'y' if view_mode == 'daily' else ''} entries"
            summary = table_controller.create_summary_panel(view_mode, totals, period)

            # Clear screen and display
            console.clear()
            console.print(summary)
            console.print()
            console.print(table)

            # Add instructions
            console.print()
            console.print(
                "[dim]Press Ctrl+C to exit[/dim]", justify="center", style="dim"
            )

            # Keep the display active
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("User interrupted table view")

        except Exception as e:
            logger.error(f"Failed to render {view_mode} view: {e}", exc_info=True)
            print_themed(f"Failed to render {view_mode} view: {e}", style="error")
            return

    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        logger.info("User interrupted table view")
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in {view_mode} view: {e}", exc_info=True)
        print_themed(f"Unexpected error displaying {view_mode} data: {e}", style="error")
if __name__ == "__main__":
    sys.exit(main())
