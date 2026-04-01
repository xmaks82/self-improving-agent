#!/bin/bash
set -e

# Create symlinks for current prompts if they don't exist
for agent in main_agent analyzer versioner; do
    prompt_dir="/app/data/prompts/$agent"
    current="$prompt_dir/current.yaml"
    initial="$prompt_dir/v001_initial.yaml"

    if [ ! -e "$current" ] && [ -f "$initial" ]; then
        ln -sf v001_initial.yaml "$current"
        echo "Created symlink: $current -> v001_initial.yaml"
    fi
done

# Run the agent
exec agent "$@"
