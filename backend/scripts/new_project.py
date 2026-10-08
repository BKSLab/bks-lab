"""Create a new project draft: python scripts/new_project.py <slug>"""

import sys

from common import create_content_file

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/new_project.py <slug>")
    path = create_content_file("project", sys.argv[1])
    print(f"Created {path}")
