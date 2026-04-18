#!/usr/bin/env python3
"""
Test script to verify idle startup and compile/run functionality
"""
import sys
import os
import subprocess
import time

def test_idle_startup():
    """Test that idle starts without errors"""
    print("Testing idle startup...")
    try:
        # Start idle in the background
        proc = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'idle_pyqt.py')],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for startup
        time.sleep(2)
        
        # Check if process is still running
        if proc.poll() is None:
            print("✓ Idle started successfully")
            proc.terminate()
            proc.wait(timeout=5)
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"✗ Idle failed to start")
            print(f"stdout: {stdout}")
            print(f"stderr: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_compile_run_simple_code():
    """Test compiling and running simple H# code"""
    print("\nTesting compile and run with simple code...")
    
    # Create a simple test file
    test_code = """let x = 10;
print(x);
"""
    
    test_file = os.path.join(os.path.dirname(__file__), 'test_idle_simple.hto')
    try:
        with open(test_file, 'w') as f:
            f.write(test_code)
        
        # Run the code using hsharp.py
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), test_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and '10' in result.stdout:
            print("✓ Compile and run test passed")
            return True
        else:
            print(f"✗ Compile and run test failed")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test file
        if os.path.exists(test_file):
            os.unlink(test_file)

if __name__ == '__main__':
    results = []
    results.append(test_idle_startup())
    results.append(test_compile_run_simple_code())
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
