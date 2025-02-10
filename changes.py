#!/usr/bin/env python3

import os
import subprocess
import argparse
from collections import defaultdict
def get_commit_touch_counts(repo_path, relative_path=None, days=None):
    """
    Returns a dictionary mapping filename -> number of commits that touched the file.
    It does this by running 'git log --pretty=format: --name-only', which lists
    every file changed in each commit (without commit messages).
    
    :param repo_path: Path to the git repository
    :param relative_path: Relative path within the repository to filter files
    :param days: Number of days to look back in history (None for entire history)
    """
    # Verify the path exists and is a directory
    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory")
        return {}

    # Store current directory
    original_dir = os.getcwd()
    
    try:
        # Change to repository directory
        os.chdir(repo_path)
        
        # Verify it's a git repository
        if not os.path.isdir('.git'):
            print(f"Error: {repo_path} is not a git repository")
            return {}
        # Build git command with optional time filter
        git_cmd = ["git", "log", "--pretty=format:", "--name-only"]
        if days is not None:
            git_cmd.extend(["--since", f"{days}.days.ago"])
            
        # Run the git command
        output = subprocess.check_output(git_cmd, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print("Error running git log:", e)
        return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}
    finally:
        # Always return to original directory
        os.chdir(original_dir)

    # Count how many times each file path appears
    changes_count = defaultdict(int)
    
    for line in output.splitlines():
        file_path = line.strip()
        # Skip empty lines
        if not file_path:
            continue
            
        # If relative_path is specified, only include files under that path
        if relative_path:
            if not file_path.startswith(relative_path):
                continue
            # Remove the relative path prefix to show proper tree structure
            file_path = file_path[len(relative_path):].lstrip('/')
            
        if file_path:  # Only count if there's still a path after stripping
            changes_count[file_path] += 1
    
    return changes_count


def build_repo_tree(base_path, touch_counts):
    """
    Build an in-memory tree of the repository starting at base_path.
    
    The result is a nested dict structure:
    
        {
          "name": "folder_name",
          "count": 0,               # Will hold sum of changes for this folder
          "children": [
             { "name": "subfolder", "count": 0, "children": [...] },
             { "name": "file.txt",  "count": 12, "children": [] },
             ...
          ]
        }

    We populate only the tracked files/folders that appear in `touch_counts`
    (plus any parent directories). If you want to include *all* folders/files,
    you'd walk the filesystem or use `git ls-tree -r HEAD --name-only` to get a
    complete listing of tracked files.
    """

    # 1) Turn the flat dictionary of file -> count into a nested path structure
    # 2) We'll keep the final structure in a root node with name="."
    
    # Step 1: Build a tree node structure
    tree = {
        "name": base_path,
        "count": 0,   # Will hold aggregated count later
        "children": {}
    }

    for file_path, ccount in touch_counts.items():
        parts = file_path.split('/')
        current_node = tree

        # Traverse or create each subfolder node
        for i, part in enumerate(parts):
            if part not in current_node["children"]:
                # Create a node
                current_node["children"][part] = {
                    "name": part,
                    "count": 0,
                    "children": {}
                }
            current_node = current_node["children"][part]

        # The final node in the path is the file itself
        # We store the per-file count in this node
        current_node["count"] += ccount

    # Step 2: Recursively sum up counts from children
    def aggregate_counts(node):
        total = node["count"]
        for child_name, child_node in node["children"].items():
            total += aggregate_counts(child_node)
        node["count"] = total
        return total

    aggregate_counts(tree)
    return tree


def print_tree(node, prefix="", is_last=True):
    """
    Recursively print the tree structure in a "tree-like" format,
    similar to the UNIX `tree` command, along with the aggregated
    change count in parentheses.
    
    :param node: A tree node as returned by build_repo_tree
    :param prefix: The prefix string used for indentation (lines, spaces)
    :param is_last: Whether this node is the last child of its parent
    """
    # We don't print the root node itself if it's just "."
    # but you can adapt that as needed.
    node_name = node["name"]
    node_count = node["count"]

    # Skip printing the pseudo-root if name is "."
    if node_name != ".":
        # Print the current node
        connector = "└──" if is_last else "├──"
        print(f"{prefix}{connector} {node_name} ({node_count})")

    # Determine the prefix for children
    new_prefix = prefix + ("    " if is_last else "│   ")

    # Collect children, sorted so that folders appear first if you prefer
    # but for simplicity, we just sort by name
    children_keys = sorted(node["children"].keys())
    
    # We'll iterate through children in sorted order
    for i, child_key in enumerate(children_keys):
        child_node = node["children"][child_key]
        child_is_last = (i == len(children_keys) - 1)
        print_tree(child_node, prefix=new_prefix, is_last=child_is_last)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Display git repository changes tree')
    parser.add_argument('path', nargs='?', default='.',
                      help='Path to the repository (default: current directory)')
    parser.add_argument('--relative-path',
                      help='Relative path within the repository to show changes for')
    parser.add_argument('--days', type=int,
                      help='Number of days to look back in history (default: entire history)')
    args = parser.parse_args()

    # Convert to absolute path
    repo_path = os.path.abspath(args.path)

    # 1) Count how many commits touched each file
    counts = get_commit_touch_counts(repo_path, args.relative_path, args.days)

    # Only proceed if we got valid data
    if counts:
        # 2) Build an in-memory tree of the repo
        repo_tree = build_repo_tree(".", counts)

        # 3) Print out the tree
        if args.relative_path:
            print(f"Changes Tree for \n{repo_path}/{args.relative_path}:")
        else:
            print(f"Changes Tree for {repo_path}:")
        print_tree(repo_tree, prefix="", is_last=True)
    else:
        print("No changes to display")


if __name__ == "__main__":
    main()