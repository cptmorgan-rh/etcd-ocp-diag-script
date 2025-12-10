etcd Diagnostics
===========================================

DESCRIPTION
------------

The purpose of this script is to quickly search logs for known etcd issues in an OpenShift Must-Gather. This tool provides both command-line and interactive modes for analyzing etcd performance and errors, with professional Python standards compliance.

INSTALLATION
------------

### Using uv (Recommended)

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

1. Install uv if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone the repository and sync dependencies:
   ```bash
   git clone <repository-url>
   cd etcd-ocp-diag
   uv sync
   ```

### Legacy Installation
* Copy etcd-ocp-diag.py to a location inside of your $PATH

USAGE
------------

### With uv (Recommended)

Run directly with uv:
```bash
# Show help
uv run etcd-ocp-diag --help

# Interactive mode
uv run etcd-ocp-diag -i

# Analyze errors
uv run etcd-ocp-diag --path /path/to/must-gather --errors

# Check specific error types
uv run etcd-ocp-diag --path /path/to/must-gather --ttl --pod etcd-master-1
```

Or run as a Python module:
```bash
uv run python -m etcd_ocp_diag --help
```

### Interactive Mode

The tool now supports an enhanced interactive mode with folder navigation and command execution:

```bash
uv run etcd-ocp-diag -i
```

#### Folder Navigation Phase

When you start interactive mode, you'll first enter folder navigation:
- The tool lists all directories in your current location
- Type a number to navigate into that directory
- **Previous Directory**: The last numbered option goes back to your previously visited directory
- Use `..` to go up one directory level
- Use `ls` to refresh the directory listing
- Use `pwd` to show the current path
- Type `run commands` when you've navigated to your must-gather directory

##### Enhanced Navigation Features:
- **Smart History**: Automatically tracks your last visited directory
- **Previous Directory**: Use the last numbered option to return to previous directory
- **Bidirectional Movement**: Switch back and forth between current and previous locations
- **Clear Labels**: Previous directory shows as "Previous Directory (dirname)" for easy identification
- **Multiple Return Options**: From command mode, use `back`, `navigate`, `directories`, `dirs`, or `nav`
- **Screen Clearing**: Clean interface with automatic screen clearing between operations
- **Visual Guidance**: Emoji hints and clear prompts guide users through each step

#### Command Execution Phase

After selecting "run commands", you can:
- Run analysis commands without specifying `--path` (uses current directory)
- **No need for `--` prefixes** - just type `errors`, `ttl pod my-pod`, etc.
- Press Enter with no command to **show help**
- **Screen clears automatically** after each command for better readability
- **Multiple ways to return to navigation**: `back`, `navigate`, `directories`, `dirs`, or `nav`
- Type `help` to see available commands
- Enter commands like `errors`, `ttl pod etcd-master-1`, `stats`
- Type `exit` or `quit` to exit
- Press Ctrl+C to exit

#### Interactive Flow Example

```
=== etcd-ocp-diag Folder Navigation ===
Current directory: /home/user

Available directories:
   1. must-gather-2024
   2. logs
   3. backup

navigate> 1
Current directory: /home/user/must-gather-2024

Available directories:
   1. etcd-logs
   2. api-server
   3. Previous Directory (user)

navigate> 1
Current directory: /home/user/must-gather-2024/etcd-logs

Available directories:
   1. pod-logs
   2. Previous Directory (must-gather-2024)

navigate> 2
Current directory: /home/user/must-gather-2024
...
navigate> run commands

=== etcd-ocp-diag Command Mode ===
Working directory: /home/user/must-gather-2024

💡 Navigation: Type 'back', 'navigate', or 'dirs' to return to folder navigation
💡 Help: Type 'help' for commands, 'exit' to quit
💡 Commands: No '--' prefixes needed (e.g., 'errors', 'ttl pod my-pod')

etcd-diag> errors
etcd-diag> ttl pod etcd-master-1
etcd-diag> stats
etcd-diag> dirs     # Return to navigation
```

### Command Reference

```bash
usage: etcd-ocp-diag [-h] --path PATH [--ttl] [--heartbeat] [--election] [--lost_leader] [--fdatasync] [--buffer] [--overloaded] [--etcd_timeout] [--pod POD] [--date DATE]
                     [--compare] [--errors] [--stats] [--previous] [--rotated] [-i]

Process etcd logs and gather statistics.

options:
  -h, --help         show this help message and exit
  --path PATH        Path to the must-gather
  --ttl              Check apply request took too long
  --heartbeat        Check failed to send out heartbeat
  --election         Checks for leader elections messages
  --lost_leader      Checks for lost leader errors
  --fdatasync        Check slow fdatasync
  --buffer           Check sending buffer is full
  --overloaded       Check leader is overloaded likely from slow disk
  --etcd_timeout     Check etcdserver: request timed out
  --pod POD          Specify the pod to analyze
  --date DATE        Specify date for error search in YYYY-MM-DD format
  --compare          Display only dates or times that happen in all pods
  --errors           Display etcd errors
  --stats            Display etcd stats
  --previous         Use previous logs
  --rotated          Use rotated logs
  -i, --interactive  Run in interactive mode
```

#### Enhanced Date Analysis

When using `--ttl` with `--date`, the output includes an additional **MAX_TIME** column that shows the highest "took" time observed for that minute. This helps identify peak performance issues within specific time windows.

**Example:**
```bash
uv run etcd-ocp-diag --path /path/to/must-gather --ttl --date 2024-12-09
```

**Output:**
```
POD                            DATE     COUNT  MAX_TIME
etcd-master-0                  14:30    45     2500.1234ms
etcd-master-0                  14:31    67     3200.5678ms
etcd-master-1                  14:30    42     2450.9876ms
```

This feature provides insight into the worst-case performance during high-activity periods, similar to the statistics shown by the `--stats` command.

## Code Quality and Standards

This project follows professional Python development standards:

### ✅ Python Standards Compliance

- **PEP 484 Type Annotations**: Full type safety with `Optional`, `Iterator`, and generic types
- **PEP 8 Style Guidelines**: Consistent formatting and naming conventions
- **Professional Documentation**: Standardized docstrings with proper Args/Returns/Yields sections
- **Modern Python Features**: Uses `pathlib`, proper exception handling, and EAFP patterns
- **Quality Assurance**: Zero linting errors with ruff, full code standards compliance

### 🔧 Development Tools

- **Linting**: Configured with `ruff` for comprehensive code quality checks
- **Type Checking**: Full type annotations for better IDE support and error prevention
- **Package Management**: Modern `uv` for fast, reliable dependency management
- **Cross-Platform**: Works on Unix, macOS, and Windows with proper path handling

### 📦 Project Structure

```
etcd-ocp-diag/
├── etcd_ocp_diag/           # Main package
│   ├── __init__.py          # Core functionality with type annotations
│   └── __main__.py          # Module entry point
├── etcd-ocp-diag.py         # Standalone script (for legacy usage)
├── pyproject.toml           # Project configuration and dependencies
├── README.md                # Documentation
└── .gitignore               # Git ignore patterns
```

The codebase is production-ready with comprehensive error handling, clear documentation, and maintainable architecture suitable for enterprise environments.