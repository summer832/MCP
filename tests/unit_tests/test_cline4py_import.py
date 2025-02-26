"""
Simple test script to verify that cline4py can be imported correctly.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Add the cline4py module to the Python path
cline4py_path = Path(__file__).parent.parent / "src" / "cline4py"
if str(cline4py_path) not in sys.path:
    sys.path.append(str(cline4py_path))

print(f"Python path: {sys.path}")
print(f"cline4py_path: {cline4py_path}")
print(f"cline4py_path exists: {os.path.exists(cline4py_path)}")

try:
    # Try to import from the cline4py package
    from cline4py import ClineClient, FolderManager
    print("Successfully imported ClineClient and FolderManager")
    print(f"ClineClient: {ClineClient}")
    print(f"FolderManager: {FolderManager}")
except ImportError as e:
    print(f"Import error: {e}")
    
    # Try to list the contents of the cline4py directory
    if os.path.exists(cline4py_path):
        print(f"Contents of {cline4py_path}:")
        for item in os.listdir(cline4py_path):
            print(f"  {item}")
            
        # Check if the cline4py subdirectory exists
        cline4py_subdir = os.path.join(cline4py_path, "cline4py")
        if os.path.exists(cline4py_subdir):
            print(f"Contents of {cline4py_subdir}:")
            for item in os.listdir(cline4py_subdir):
                print(f"  {item}")
        else:
            print(f"cline4py subdirectory does not exist: {cline4py_subdir}")
    else:
        print(f"cline4py_path does not exist: {cline4py_path}")

if __name__ == "__main__":
    print("Test completed")
