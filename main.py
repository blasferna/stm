import argparse
import os
import sys
import glob
import fnmatch

# Heuristic to skip common binary file types
BINARY_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico',
    # Archives
    '.zip', '.tar', '.gz', '.rar', '.7z', '.whl',
    # Executables/compiled
    '.exe', '.dll', '.so', '.dylib', '.o', '.a', '.pyc', '.pyo', '.class', '.jar',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # Media
    '.mp3', '.wav', '.ogg', '.mp4', '.mkv', '.avi', '.mov',
    # Databases
    '.db', '.sqlite', '.sqlite3',
    # Fonts
    '.ttf', '.otf', '.woff', '.woff2',
    # Other
    '.lock' # e.g. package-lock.json, Pipfile.lock (content not useful code)
}

# Specific files to always ignore by name
# (often not in .gitignore but good to skip for LLM context)
# For example, lock files' content is usually not what you want.
# Their existence might be, but not their verbose content.
ALWAYS_IGNORE_FILENAMES = {
    'package-lock.json', 'yarn.lock', 'Pipfile.lock', 'poetry.lock',
    '.DS_Store'
}


def get_language_from_extension(filepath):
    """
    Determines a language string from file extension for Markdown code blocks.
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
        '.cs': 'csharp', '.go': 'go', '.rb': 'ruby', '.php': 'php',
        '.rs': 'rust', '.kt': 'kotlin', '.swift': 'swift',
        '.md': 'markdown', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
        '.html': 'html', '.htm': 'html', '.css': 'css',
        '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh',
        '.sql': 'sql', '.r': 'r', '.pl': 'perl', '.lua': 'lua',
        '.scala': 'scala', '.hs': 'haskell', '.clj': 'clojure',
        '.f90': 'fortran', '.f95': 'fortran',
        '.txt': 'text',
    }
    return lang_map.get(ext, '')


def load_gitignore_patterns(gitignore_path):
    """
    Loads patterns from a .gitignore file.
    Strips comments and empty lines.
    """
    patterns = []
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    return patterns


def is_file_ignored(filepath_abs, project_root_abs, gitignore_patterns_by_dir):
    """
    Checks if a file should be ignored based on .gitignore patterns.
    This is a simplified implementation.
    - `filepath_abs`: Absolute path to the file.
    - `project_root_abs`: Absolute path to the project root (where global .gitignore might be).
    - `gitignore_patterns_by_dir`: Dict mapping directory path to its gitignore patterns.
    """
    if os.path.basename(filepath_abs) in ALWAYS_IGNORE_FILENAMES:
        return True

    # Always ignore .git directory contents
    # Check if filepath_abs is inside any .git directory
    path_parts = filepath_abs.split(os.sep)
    if ".git" in path_parts:
        # More precise check: ensure '.git' is a directory component, not part of a filename
        try:
            git_index = path_parts.index(".git")
            git_dir_path = os.sep.join(path_parts[:git_index+1])
            if os.path.isdir(git_dir_path) and filepath_abs.startswith(git_dir_path + os.sep):
                 return True
        except ValueError:
            pass # .git not in path

    current_dir = os.path.dirname(filepath_abs)
    ignored = False
    negated = False # For handling !pattern

    # Iterate from file's directory up to project root
    # Rules in .gitignore closer to the file take precedence for the same pattern,
    # but later rules within the same file for the same path also take precedence.
    # Negation rules can override ignore rules.
    # This simplified version checks all ignore patterns first, then negation.
    # A more correct implementation is complex.

    # Traverse from project root down to file's directory to apply rules hierarchically
    # This isn't perfect but captures some of the cascading nature.
    # A better way is to check from file's dir upwards.
    
    path_components = os.path.relpath(filepath_abs, project_root_abs).split(os.sep)
    
    # Check against .gitignore in parent directories, starting from project_root
    # and going down to the file's own directory.
    # This means patterns in deeper .gitignore files can override those in higher ones
    # if they match. We will apply them in order.
    
    # Create a list of relevant .gitignore files from project root down to file's dir.
    # And then check patterns from the deepest .gitignore first (highest precedence).
    
    # Path from project root to file, using standard '/' separators
    filepath_relative_to_project_root = os.path.relpath(filepath_abs, project_root_abs).replace(os.sep, '/')


    # Check all .gitignore files from the file's directory up to the project root
    temp_dir = os.path.dirname(filepath_abs)
    relevant_gitignore_dirs = []
    while True:
        if temp_dir in gitignore_patterns_by_dir:
            relevant_gitignore_dirs.append(temp_dir)
        if temp_dir == project_root_abs or not temp_dir or temp_dir == os.path.dirname(temp_dir):
            break
        temp_dir = os.path.dirname(temp_dir)
    
    # Process patterns from most specific (.gitignore in same dir) to least specific (project root)
    for gitignore_dir_abs in relevant_gitignore_dirs:
        patterns = gitignore_patterns_by_dir[gitignore_dir_abs]
        # Path relative to the directory containing the current .gitignore file
        path_relative_to_gitignore_dir = os.path.relpath(filepath_abs, gitignore_dir_abs).replace(os.sep, '/')

        for pattern in patterns:
            is_negation = pattern.startswith('!')
            if is_negation:
                pattern = pattern[1:]

            # fnmatch pattern rules for .gitignore:
            # 1. If pattern ends with '/', it only matches directories.
            #    We match if path_relative_to_gitignore_dir starts with pattern.
            # 2. If pattern contains no '/', it matches name in any subdir.
            #    fnmatch(os.path.basename(path_relative_to_gitignore_dir), pattern)
            # 3. Otherwise, it's a path relative to .gitignore file's location.
            #    fnmatch(path_relative_to_gitignore_dir, pattern)

            matched = False
            if pattern.endswith('/'):
                # Directory pattern
                # e.g. "logs/" should match "logs/error.txt"
                # path_relative_to_gitignore_dir must be "logs/error.txt"
                # pattern.rstrip('/') would be "logs"
                if (path_relative_to_gitignore_dir + '/').startswith(pattern):
                    matched = True
            elif '/' not in pattern:
                # File/dir name pattern, matches at any level relative to .gitignore
                # For a file: check its basename
                if fnmatch.fnmatch(os.path.basename(path_relative_to_gitignore_dir), pattern):
                    matched = True
                # For a directory: check if any path component matches
                # This is harder; git's behavior is that 'foo' matches 'foo' and 'foo/bar'
                # If path_relative_to_gitignore_dir is 'a/foo/b.txt' and pattern 'foo'
                # This is complicated. fnmatch alone isn't enough for full "match anywhere" semantics of plain names.
                # Let's simplify: if it's a plain name, also check if the path starts with it as a directory.
                if fnmatch.fnmatch(path_relative_to_gitignore_dir, pattern + '/*') or \
                   fnmatch.fnmatch(path_relative_to_gitignore_dir, pattern):
                    matched = True
            else:
                # Path pattern relative to .gitignore file's directory
                if fnmatch.fnmatch(path_relative_to_gitignore_dir, pattern):
                    matched = True
            
            if matched:
                if is_negation:
                    negated = True # This file is specifically un-ignored
                    ignored = False # Reset ignore status if previously ignored by a broader rule
                elif not negated: # Only ignore if not specifically un-ignored by a later rule
                    ignored = True
                    # If a deeper .gitignore's !rule un-ignored it, a shallower ignore rule shouldn't re-ignore it
                    # This logic needs refinement for perfect precedence.
                    # For now, if any rule ignores it, and no specific negation for THIS rule match, it's ignored.
                    # If a negation rule matches, it becomes unignored.
    
    # Final decision based on whether it was last ignored or unignored.
    # If `negated` is true, it means a `!` rule was the last one to match for this file.
    return ignored if not negated else False


def collect_gitignore_patterns(start_paths_abs, project_root_abs):
    """
    Collects all .gitignore patterns from project_root and any .gitignore
    found within the directory trees of start_paths_abs.
    Returns a dict: {absolute_dir_path: [patterns]}
    """
    patterns_by_dir = {}
    
    # First, load .gitignore from project_root if it exists
    root_gitignore_path = os.path.join(project_root_abs, ".gitignore")
    if os.path.isfile(root_gitignore_path):
        patterns_by_dir[project_root_abs] = load_gitignore_patterns(root_gitignore_path)

    # Then, search for .gitignore files in the specified paths and their subdirectories
    # Use a set to avoid processing the same .gitignore multiple times
    # if start_paths_abs overlap.
    gitignores_found = {root_gitignore_path} if os.path.isfile(root_gitignore_path) else set()

    dirs_to_scan = set()
    for p_abs in start_paths_abs:
        if os.path.isdir(p_abs):
            dirs_to_scan.add(p_abs)
        elif os.path.isfile(p_abs):
            dirs_to_scan.add(os.path.dirname(p_abs))
            
    for current_search_dir in dirs_to_scan:
        for root, _, _ in os.walk(current_search_dir):
            # Ensure we only go as deep as project_root_abs allows if path is outside
            if not root.startswith(project_root_abs) and project_root_abs not in root:
                # This case can happen if a start_path is outside project_root_abs
                # For simplicity, we'll assume start_paths are within or at project_root_abs
                # or that project_root_abs is the ultimate boundary.
                pass

            gitignore_path = os.path.join(root, ".gitignore")
            if os.path.isfile(gitignore_path) and gitignore_path not in gitignores_found:
                patterns_by_dir[root] = load_gitignore_patterns(gitignore_path)
                gitignores_found.add(gitignore_path)
    return patterns_by_dir


def main():
    parser = argparse.ArgumentParser(
        description="Convert a codebase to a Markdown file for LLM context, respecting .gitignore.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'paths',
        nargs='*',
        default=['.'],
        help="Paths to process (files, directories, or glob patterns like 'src/**/*.py'). "
             "Default: current directory '.'"
    )
    parser.add_argument(
        '-o', '--output',
        help="Output Markdown file. If not specified, prints to stdout."
    )
    parser.add_argument(
        '--project-root',
        default=os.getcwd(),
        help="Specify the project root directory. .gitignore files are processed relative to this. "
             "Default: current working directory."
    )
    parser.add_argument(
        '--no-gitignore',
        action='store_true',
        help="Disable .gitignore file processing."
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Print verbose output, like skipped files."
    )

    args = parser.parse_args()

    project_root_abs = os.path.abspath(args.project_root)
    if args.verbose:
        print(f"Project root set to: {project_root_abs}", file=sys.stderr)

    # --- 1. Collect all files based on input paths and globs ---
    candidate_files_abs = set()
    for path_arg in args.paths:
        # Ensure path_arg is absolute for consistent globbing if it's relative
        # However, glob works fine with relative paths from CWD.
        # If path_arg is already absolute, os.path.join(os.getcwd(), path_arg) might be wrong.
        # Let glob handle it.
        
        # Handle if path_arg is like `.` or `src` vs `src/*`
        # If it's an existing directory, glob needs a wildcard to go inside.
        path_to_glob = path_arg
        if os.path.isdir(path_arg) and not path_arg.endswith(os.sep + '*') and not path_arg.endswith(os.sep + '**' + os.sep + '*'):
             # Add a recursive wildcard to search inside the directory
             path_to_glob = os.path.join(path_arg, '**', '*')
        
        # Use glob to expand patterns and find files
        # recursive=True allows `**` to match directories recursively
        expanded_paths = glob.glob(path_to_glob, recursive=True)
        
        if not expanded_paths and os.path.exists(path_arg): # Handle single existing file/dir not caught by glob
             expanded_paths = [path_arg]

        for item_path in expanded_paths:
            abs_item_path = os.path.abspath(item_path)
            if os.path.isfile(abs_item_path):
                candidate_files_abs.add(abs_item_path)
            elif os.path.isdir(abs_item_path) and path_to_glob == path_arg : # if user specified dir explicitly, walk it
                for root, _, files_in_dir in os.walk(abs_item_path):
                    for f_name in files_in_dir:
                        file_path_abs = os.path.abspath(os.path.join(root, f_name))
                        candidate_files_abs.add(file_path_abs)
                        
    if args.verbose:
        print(f"Found {len(candidate_files_abs)} candidate files before filtering.", file=sys.stderr)

    # --- 2. Load .gitignore patterns ---
    gitignore_patterns_by_dir = {}
    if not args.no_gitignore:
        start_paths_for_gitignore_search_abs = [os.path.abspath(p) for p in args.paths]
        gitignore_patterns_by_dir = collect_gitignore_patterns(start_paths_for_gitignore_search_abs, project_root_abs)
        if args.verbose:
            found_gitignores = len(gitignore_patterns_by_dir)
            print(f"Loaded .gitignore patterns from {found_gitignores} .gitignore file(s).", file=sys.stderr)
            # for d, pats in gitignore_patterns_by_dir.items():
            #     print(f"  {os.path.relpath(d, project_root_abs)}: {len(pats)} patterns", file=sys.stderr)
    else:
        if args.verbose:
            print("Skipping .gitignore processing due to --no-gitignore.", file=sys.stderr)


    # --- 3. Filter files ---
    processed_files_content = []
    processed_files_paths_relative = []

    # Sort for consistent output order
    sorted_candidate_files_abs = sorted(list(candidate_files_abs))

    for filepath_abs in sorted_candidate_files_abs:
        # Make path relative to project_root for display and .gitignore logic
        # Ensure it's truly within project_root for sensible relative paths
        if not filepath_abs.startswith(project_root_abs):
            if args.verbose:
                print(f"Skipping file outside project root: {filepath_abs}", file=sys.stderr)
            continue
            
        filepath_relative = os.path.relpath(filepath_abs, project_root_abs)
        # Normalize path separators for cross-platform consistency in output
        filepath_relative_std = filepath_relative.replace(os.sep, '/')

        # Basic binary file check by extension
        if os.path.splitext(filepath_abs)[1].lower() in BINARY_EXTENSIONS:
            if args.verbose:
                print(f"Skipping likely binary file (by extension): {filepath_relative_std}", file=sys.stderr)
            continue

        # .gitignore check
        if not args.no_gitignore and is_file_ignored(filepath_abs, project_root_abs, gitignore_patterns_by_dir):
            if args.verbose:
                print(f"Skipping ignored file (by .gitignore): {filepath_relative_std}", file=sys.stderr)
            continue
        
        try:
            with open(filepath_abs, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Additional check for binary files that might have slipped through extension check
            # or text files with too many replacement characters (bad decoding)
            if content.count('\ufffd') > len(content) * 0.1 and len(content) > 100: # Heuristic
                 if args.verbose:
                    print(f"Skipping file with many Unicode replacement characters (likely binary or wrong encoding): {filepath_relative_std}", file=sys.stderr)
                 continue

            lang = get_language_from_extension(filepath_relative_std)
            
            md_block = []
            md_block.append(f"```{lang} name={filepath_relative_std}")
            md_block.append(content.strip()) # Strip trailing newlines from content itself
            md_block.append("```")
            
            processed_files_content.append("\n".join(md_block))
            processed_files_paths_relative.append(filepath_relative_std)

        except UnicodeDecodeError:
            if args.verbose:
                print(f"Skipping file with encoding error (likely binary): {filepath_relative_std}", file=sys.stderr)
        except Exception as e:
            print(f"Error processing file {filepath_relative_std}: {e}", file=sys.stderr)

    # --- 4. Output ---
    final_output = "\n\n".join(processed_files_content) # Two newlines between file blocks

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(final_output)
            if args.verbose:
                print(f"\nSuccessfully wrote {len(processed_files_paths_relative)} files to {args.output}", file=sys.stderr)
            else:
                # Non-verbose success message to stdout if not piping, stderr if piping
                # This is tricky. Let's just print to stderr to avoid mixing with piped output.
                if sys.stdout.isatty():
                     print(f"Markdown content for {len(processed_files_paths_relative)} file(s) written to {args.output}")
        except IOError as e:
            print(f"Error writing to output file {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Output to stdout (for piping)
        # Ensure final output ends with a newline if it's not empty
        if final_output:
            sys.stdout.write(final_output + "\n")
        if args.verbose and sys.stderr.isatty(): # Only print summary if stderr is a tty
            print(f"\nProcessed {len(processed_files_paths_relative)} files.", file=sys.stderr)

if __name__ == "__main__":
    main()
