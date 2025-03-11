#!/bin/bash

# Set the directory to search (default to current directory if not provided)
SEARCH_DIR="${1:-.}"

# Function to extract and find the highest custom_port_prefix
find_highest_port_prefix() {
    local highest=0

    # Find all YAML files and extract custom_port_prefix values
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            # Extract custom_port_prefix values using grep and awk
            while IFS= read -r line; do
                value=$(echo "$line" | awk -F ': ' '{print $2}' | tr -d '[:space:]')
                if [[ "$value" =~ ^[0-9]+$ ]]; then
                    (( value > highest )) && highest=$value
                fi
            done < <(grep -E '^\s*custom_port_prefix\s*:' "$file")
        fi
    done < <(find "$SEARCH_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \))

    echo "$highest"
}

# Get the highest custom_port_prefix value
highest_port=$(find_highest_port_prefix)

# Increment by 1
new_port=$((highest_port + 1))

echo "Highest custom_port_prefix found: $highest_port"
echo "Next available custom_port_prefix: $new_port"
