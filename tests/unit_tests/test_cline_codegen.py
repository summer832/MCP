"""
Test script for the Cline-based code generation implementation.

This script tests the integration of Cline with the code generation agent.
It sends a sample requirement to the agent and verifies that the code is generated,
checked, and revised using Cline.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Add the cline4py module to the Python path
cline4py_path = Path(__file__).parent.parent / "src" / "cline4py"
if str(cline4py_path) not in sys.path:
    sys.path.append(str(cline4py_path))

from agent.generate_agent.graph import graph
from agent.generate_agent.state import InputState
from langchain_core.messages import HumanMessage

# Import from cline4py package to ensure it's loaded
from cline4py import ClineClient, FolderManager


async def test_cline_codegen():
    """Test the Cline-based code generation implementation."""
    
    # Sample requirement for testing
    sample_requirement = {
        "requirement_type": "general",
        "requirement": """
        Create a simple MCP server that provides a tool to convert temperatures between Celsius and Fahrenheit.
        The server should:
        1. Implement a tool named 'convert_temperature' that takes a temperature value and unit ('C' or 'F')
        2. Return the converted temperature in the other unit
        3. Handle invalid inputs gracefully
        """
    }
    
    # Convert the requirement to JSON
    requirement_json = json.dumps(sample_requirement, ensure_ascii=False)
    
    # Create the input state with the requirement
    input_state = InputState(messages=[HumanMessage(content=requirement_json)])
    
    # Ensure the result folder exists
    result_folder = os.path.abspath("result")
    os.makedirs(result_folder, exist_ok=True)
    
    print(f"Starting code generation with requirement: {requirement_json}")
    
    try:
        # Run the graph with the input state
        result = await graph.ainvoke(input_state)
        
        # Check if the code was generated
        if hasattr(result, "code") and result.code:
            print("Code generation successful!")
            print(f"Generated code length: {len(result.code)} characters")
            
            # Check if the code is valid
            if hasattr(result, "is_valid"):
                print(f"Code validity: {result.is_valid}")
            
            # Check the file in the result folder
            index_ts_path = os.path.join(result_folder, "index.ts")
            if os.path.exists(index_ts_path):
                print(f"index.ts file created at: {index_ts_path}")
                with open(index_ts_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                print(f"File content length: {len(file_content)} characters")
                
                # Verify the file content matches the code in the result
                if file_content == result.code:
                    print("File content matches the code in the result.")
                else:
                    print("Warning: File content does not match the code in the result.")
            else:
                print(f"Warning: index.ts file not found at {index_ts_path}")
        else:
            print("Error: Code generation failed or code is empty.")
            
        # Print the conversation turns
        if hasattr(result, "conversation_turn"):
            print(f"Conversation turns: {result.conversation_turn}")
            
        return result
    except Exception as e:
        print(f"Error during code generation: {str(e)}")
        raise


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_cline_codegen())
