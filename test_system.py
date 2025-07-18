#!/usr/bin/env python3
"""
Test script for the Coding Agent System
"""

import requests
import time
import sys
import json

BASE_URL = "http://localhost:8000"

def test_system():
    print("🧪 Testing Coding Agent System")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Health check passed")
            stats = response.json().get('stats', {})
            print(f"   System stats: {stats}")
        else:
            print("❌ Health check failed")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test 2: Schedule a simple task
    print("\n2. Scheduling a todo app task...")
    try:
        task_data = {
            "task": "Build me a todo app in React",
            "priority": 1,
            "timeout": 1800
        }
        
        response = requests.post(f"{BASE_URL}/schedule", json=task_data)
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data['job_id']
            print(f"✅ Task scheduled successfully")
            print(f"   Job ID: {job_id}")
        else:
            print(f"❌ Failed to schedule task: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to schedule task: {e}")
        return False
    
    # Test 3: Monitor job progress
    print(f"\n3. Monitoring job {job_id}...")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{BASE_URL}/status/{job_id}")
            if response.status_code == 200:
                status_data = response.json()
                status = status_data['status']
                
                print(f"   Status: {status}")
                
                if status_data.get('vnc_url'):
                    print(f"   VNC URL: {status_data['vnc_url']}")
                
                if status_data.get('progress'):
                    latest_progress = status_data['progress'][-1]
                    print(f"   Latest: {latest_progress['message']}")
                
                if status == 'completed':
                    print("✅ Job completed successfully!")
                    if status_data.get('download_url'):
                        print(f"   Download URL: {BASE_URL}{status_data['download_url']}")
                    if status_data.get('result'):
                        print(f"   Result: {json.dumps(status_data['result'], indent=2)}")
                    break
                elif status == 'failed':
                    print(f"❌ Job failed: {status_data.get('error', 'Unknown error')}")
                    return False
                elif status == 'running':
                    print("   Job is running...")
                else:
                    print(f"   Job status: {status}")
                
                time.sleep(10)
            else:
                print(f"❌ Failed to get status: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Failed to get status: {e}")
            return False
    
    if time.time() - start_time >= max_wait:
        print("⏰ Test timed out")
        return False
    
    # Test 4: List jobs
    print("\n4. Testing job listing...")
    try:
        response = requests.get(f"{BASE_URL}/jobs")
        if response.status_code == 200:
            jobs_data = response.json()
            print(f"✅ Found {jobs_data['total']} jobs")
            for job in jobs_data['jobs'][:3]:  # Show first 3
                print(f"   - {job['job_id']}: {job['status']} - {job['task'][:50]}...")
        else:
            print(f"❌ Failed to list jobs: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to list jobs: {e}")
        return False
    
    # Test 5: Get system stats
    print("\n5. Testing system stats...")
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            stats = response.json()
            print("✅ System stats retrieved")
            print(f"   Total jobs: {stats.get('total_jobs', 0)}")
            print(f"   Running jobs: {stats.get('running_jobs', 0)}")
            print(f"   Completed jobs: {stats.get('completed_jobs', 0)}")
        else:
            print(f"❌ Failed to get stats: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to get stats: {e}")
        return False
    
    print("\n🎉 All tests passed!")
    return True

def main():
    print("Starting system tests...")
    print("Make sure the orchestrator is running on http://localhost:8000")
    print("You can start it with: python -m orchestrator.main")
    print()
    
    # Wait for user confirmation
    input("Press Enter when ready to start tests...")
    
    success = test_system()
    
    if success:
        print("\n✅ System is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ System tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()