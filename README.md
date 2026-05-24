etcd Diagnostics
===========================================

DESCRIPTION
------------

The purpose of this script is to quickly search logs for known etcd issues in an OpenShift Must-Gather. This tool provides both command-line and interactive modes for analyzing etcd performance and errors, with professional Python standards compliance.

INSTALLATION
------------

### Standard Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd etcd-ocp-diag
   ```

2. Ensure Python 3.8+ is available:
   ```bash
   python3 --version
   ```

### Legacy Installation
* Copy etcd-ocp-diag.py to a location inside of your $PATH

USAGE
------------

### Run the Script

Run directly with Python:
```bash
# Show help
python3 etcd-ocp-diag.py --help

# Interactive mode
python3 etcd-ocp-diag.py -i

# Analyze errors
python3 etcd-ocp-diag.py --path /path/to/must-gather --errors

# Check specific error types
python3 etcd-ocp-diag.py --path /path/to/must-gather --ttl --pod etcd-master-1
```

Or run the script directly:
```bash
./etcd-ocp-diag.py --help
```

### Interactive Mode

The tool now supports an enhanced interactive mode with folder navigation and command execution:

```bash
python3 etcd-ocp-diag.py -i
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
usage: etcd-ocp-diag [-h] --path PATH [--ttl] [--heartbeat] [--election] [--lost_leader] [--fdatasync] [--buffer] [--overloaded] [--slow_network] [--etcd_timeout] [--request_stats] [--pod POD] [--date DATE]
                     [--compare] [--errors] [--stats] [--previous] [--rotated] [-i]

Process etcd logs and gather statistics.

options:
  -h, --help           show this help message and exit
  --path PATH          Path to the must-gather
  --ttl                Check apply request took too long
  --heartbeat          Check failed to send out heartbeat
  --election           Checks for leader elections messages
  --lost_leader        Checks for lost leader errors
  --fdatasync          Check slow fdatasync
  --buffer             Check sending buffer is full
  --overloaded         Check leader is overloaded likely from slow disk
  --slow_network       Check local node might have slow network
  --etcd_timeout       Check etcdserver: request timed out
  --request_stats      Check request stats
  --pod POD            Specify the pod to analyze
  --date DATE          Specify date for error search in YYYY-MM-DD format
  --compare            Display only dates or times that happen in all pods
  --errors             Display etcd errors
  --stats              Display etcd stats
  --previous           Use previous logs
  --rotated            Use rotated logs
  -i, --interactive    Run in interactive mode
```

#### Enhanced Date Analysis

When using `--ttl` or `--request_stats` with `--date`, the output includes an additional **MAX_TIME** column showing the highest latency observed within each minute. This helps identify peak performance issues within specific time windows.

- `--ttl` reads the `took` field from `apply request took too long` log lines.
- `--request_stats` reads the `time spent` field from `request stats` log lines.

**Example:**
```bash
python3 etcd-ocp-diag.py --path /path/to/must-gather --ttl --date 2024-12-09
python3 etcd-ocp-diag.py --path /path/to/must-gather --request_stats --date 2024-12-09
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
- **Cross-Platform**: Works on Unix, macOS, and Windows with proper path handling

### 📦 Project Structure

```
etcd-ocp-diag/
├── etcd-ocp-diag.py         # Main script with full functionality
├── pyproject.toml           # Project configuration and dependencies
├── README.md                # Documentation
└── .gitignore               # Git ignore patterns
```

The codebase is production-ready with comprehensive error handling, clear documentation, and maintainable single-script architecture suitable for enterprise environments.