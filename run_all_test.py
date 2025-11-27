"""
Master Test Runner
Runs all test suites and generates comprehensive report
"""
import sys
import os
import time
import json
from contextlib import contextmanager

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'tests'))


class TeeStream:
    """Duplicate writes to multiple streams."""
    def __init__(self, *streams):
        self.streams = streams
    
    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()
    
    def flush(self):
        for stream in self.streams:
            stream.flush()


@contextmanager
def tee_output_to_file(log_path: str):
    """Mirror stdout/stderr to file while keeping console output."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    with open(log_path, "w", encoding="utf-8") as log_file:
        stdout_tee = TeeStream(original_stdout, log_file)
        stderr_tee = TeeStream(original_stderr, log_file)
        try:
            sys.stdout = stdout_tee
            sys.stderr = stderr_tee
            yield log_file
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

def run_test_suite(test_module_name, test_function_name):
    """Run a test suite and return results"""
    print(f"\n{'='*80}")
    print(f"Running {test_module_name}")
    print(f"{'='*80}")
    
    try:
        module = __import__(test_module_name)
        test_function = getattr(module, test_function_name)
        
        start_time = time.time()
        exit_code = test_function()
        duration = time.time() - start_time
        
        return {
            "suite": test_module_name,
            "passed": exit_code == 0,
            "duration": duration
        }
    except Exception as e:
        print(f"Error running {test_module_name}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "suite": test_module_name,
            "passed": False,
            "duration": 0,
            "error": str(e)
        }

def main():
    """Run all test suites"""
    print("\n" + "="*80)
    print("BLOCKCHAIN LAYER 1 - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print()
    
    start_time = time.time()
    
    # Define test suites
    test_suites = [
        ("test_crypto", "run_all_crypto_tests"),
        ("test_execution", "run_all_execution_tests"),
        ("test_consensus", "run_all_consensus_tests"),
        ("test_network", "run_all_network_tests"),
        ("test_e2e", "run_all_tests")
    ]
    
    results = []
    
    # Run each test suite
    for module_name, function_name in test_suites:
        result = run_test_suite(module_name, function_name)
        results.append(result)
    
    total_duration = time.time() - start_time
    
    # Generate report
    print("\n" + "="*80)
    print("FINAL TEST REPORT")
    print("="*80)
    print()
    
    all_passed = True
    for result in results:
        status = "PASSED" if result["passed"] else "FAILED"
        duration = result["duration"]
        suite = result["suite"]
        
        print(f"{status} - {suite:<20} ({duration:.2f}s)")
        
        if not result["passed"]:
            all_passed = False
            if "error" in result:
                print(f"         Error: {result['error']}")
    
    print()
    print("="*80)
    print(f"Total Duration: {total_duration:.2f}s")
    print("="*80)
    
    if all_passed:
        print("\nALL TEST SUITES PASSED!")
        print("\nThe blockchain implementation meets all requirements:")
        print("   • Cryptography: Key management, signatures, domain separation")
        print("   • Execution: State management, transactions, determinism")
        print("   • Consensus: Two-phase voting, finality guarantees")
        print("   • Network: Unreliable network simulation")
        print("   • End-to-End: Safety, liveness, fault tolerance")
        
        # Save report
        report = {
            "timestamp": time.time(),
            "total_duration": total_duration,
            "all_passed": True,
            "results": results
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("\nTest report saved to logs/test_report.json")
        
        return 0
    else:
        print("\nSOME TEST SUITES FAILED")
        print("\nPlease review the errors above and fix the issues.")
        
        # Save report
        report = {
            "timestamp": time.time(),
            "total_duration": total_duration,
            "all_passed": False,
            "results": results
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        return 1

if __name__ == "__main__":
    log_txt_path = os.path.join("logs", "run_all_test_output.txt")
    with tee_output_to_file(log_txt_path):
        print(f"[run_all_test] Writing console output to {log_txt_path}")
        exit_code = main()
        print(f"\nText output saved to {log_txt_path}")
        sys.exit(exit_code)