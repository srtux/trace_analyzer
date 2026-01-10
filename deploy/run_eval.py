#!/usr/bin/env python3
import glob
import subprocess
import sys


def main():
    # Separate flags from positional arguments
    # Everything starting with '-' is a flag
    flags = [arg for arg in sys.argv[1:] if arg.startswith("-")]

    # Define our standard agent and eval files
    agent_path = "sre_agent"
    eval_files = glob.glob("eval/*.test.json")

    # Construct the command with flags BEFORE positional arguments
    # adk eval [FLAGS] [AGENT] [FILES]
    cmd = ["adk", "eval", *flags, agent_path, *eval_files]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
